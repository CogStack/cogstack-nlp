from typing import Iterable, Callable, Optional, Union, cast
import logging
from itertools import chain, repeat, islice
from tqdm import trange

from medcat.tokenizing.tokens import (MutableDocument, MutableEntity,
                                      MutableToken)
from medcat.cdb import CDB
from medcat.config.config import General, Preprocessing, CDBMaker
from medcat.utils.config_utils import temp_changed_config
from medcat.utils.data_utils import make_mc_train_test, get_false_positives
from medcat.utils.filters import project_filters
from medcat.data.mctexport import (
    MedCATTrainerExport, MedCATTrainerExportProject,
    MedCATTrainerExportDocument, count_all_annotations, iter_anns)
from medcat.preprocessors.cleaners import prepare_name, NameDescriptor
from medcat.components.types import CoreComponentType, TrainableComponent
from medcat.components.addons.addons import AddonComponent
from medcat.pipeline import Pipeline


logger = logging.getLogger(__name__)


# NOTE: this should be used for changing the CDB, both for training and for
#       unlinking concept/names.
class Trainer:
    strict_train: bool = False

    def __init__(self, cdb: CDB, caller: Callable[[str], MutableDocument],
                 pipeline: Pipeline):
        self.cdb = cdb
        self.config = cdb.config
        self.caller = caller
        self._pipeline = pipeline

    def train_unsupervised(self,
                           data_iterator: Iterable[str],
                           nepochs: int = 1,
                           fine_tune: bool = True,
                           progress_print: int = 1000,
                           #    checkpoint: Optional[Checkpoint] = None,
                           ) -> None:
        """Runs training on the data, note that the maximum length of a line
        or document is 1M characters. Anything longer will be trimmed.

        Args:
            data_iterator (Iterable):
                Simple iterator over sentences/documents, e.g. a open file
                or an array or anything that we can use in a for loop.
            nepochs (int):
                Number of epochs for which to run the training.
            fine_tune (bool):
                If False old training will be removed.
            progress_print (int):
                Print progress after N lines.
            checkpoint (Optional[medcat.utils.checkpoint.CheckpointUT]):
                The MedCAT checkpoint object
            is_resumed (bool):
                If True resume the previous training; If False, start a fresh
                new training.
        """
        with self.config.meta.prepare_and_report_training(
            data_iterator, nepochs, False
        ) as wrapped_iter:
            with temp_changed_config(self.config.components.linking,
                                     'train', True):
                self._train_unsupervised(wrapped_iter, nepochs, fine_tune,
                                         progress_print)

    def _train_unsupervised(self,
                            data_iterator: Iterable,
                            nepochs: int = 1,
                            fine_tune: bool = True,
                            progress_print: int = 1000,
                            #    checkpoint: Optional[Checkpoint] = None,
                            ) -> None:
        if not fine_tune:
            logger.info("Removing old training data!")
            self.cdb.reset_training()
        # checkpoint = self._init_ckpts(is_resumed, checkpoint)

        # latest_trained_step = checkpoint.count if checkpoint is
        # not None else 0
        latest_trained_step = 0  # TODO: add back checkpointing
        epochal_data_iterator = chain.from_iterable(repeat(data_iterator,
                                                           nepochs))
        for line in islice(epochal_data_iterator, latest_trained_step, None):
            if line is not None and line:
                # Convert to string
                line = str(line).strip()

                try:
                    _ = self.caller(line)
                except Exception as e:
                    logger.warning("LINE: '%s...' \t WAS SKIPPED", line[0:100])
                    logger.warning("BECAUSE OF:", exc_info=e)
            else:
                logger.warning("EMPTY LINE WAS DETECTED AND SKIPPED")

            latest_trained_step += 1
            if latest_trained_step % progress_print == 0:
                logger.info("DONE: %s", str(latest_trained_step))
            # if (checkpoint is not None and checkpoint.steps is not None
            #         and latest_trained_step % checkpoint.steps == 0):
            #     checkpoint.save(cdb=self.cdb, count=latest_trained_step)

    def _reset_cui_counts(self, train_set: MedCATTrainerExport,
                          reset_val: int = 100):
        # Get all CUIs
        cuis = []
        for project in train_set['projects']:
            for ann in (ann for doc in project['documents']
                        for ann in doc['annotations']):
                cuis.append(ann['cui'])
        for cui in set(cuis):
            if self.cdb.cui2info[cui]['count_train'] != 0:
                self.cdb.cui2info[cui]['count_train'] = reset_val

    def train_supervised_raw(self,
                             data: MedCATTrainerExport,
                             reset_cui_count: bool = False,
                             nepochs: int = 1,
                             print_stats: int = 0,
                             use_filters: bool = False,
                             terminate_last: bool = False,
                             use_overlaps: bool = False,
                             use_cui_doc_limit: bool = False,
                             test_size: float = 0,
                             devalue_others: bool = False,
                             use_groups: bool = False,
                             never_terminate: bool = False,
                             train_from_false_positives: bool = False,
                             extra_cui_filter: Optional[set[str]] = None,
                             #  checkpoint: Optional[Checkpoint] = None,
                             disable_progress: bool = False,
                             train_addons: bool = False,
                             ) -> tuple:
        """Train supervised based on the raw data provided.

        The raw data is expected in the following format:
        {'projects':
            [ # list of projects
                { # project 1
                    'name': '<some name>',
                    # list of documents
                    'documents': [{'name': '<some name>',  # document 1
                                    'text': '<text of the document>',
                                    # list of annotations
                                    'annotations': [# annotation 1
                                                    {'start': -1,
                                                    'end': 1,
                                                    'cui': 'cui',
                                                    'value': '<text value>'},
                                                    ...],
                                    }, ...]
                }, ...
            ]
        }

        Please take care that this is more a simulated online training then
        upervised.

        When filtering, the filters within the CAT model are used first,
        then the ones from MedCATtrainer (MCT) export filters,
        and finally the extra_cui_filter (if set).
        That is to say, the expectation is:
        extra_cui_filter ⊆ MCT filter ⊆ Model/config filter.

        Args:
            data (dict[str, list[dict[str, dict]]]):
                The raw data, e.g from MedCATtrainer on export.
            reset_cui_count (bool):
                Used for training with weight_decay (annealing). Each concept
                has a count that is there from the beginning of the CDB, that
                count is used for annealing. Resetting the count will
                significantly increase the training impact. This will reset
                the count only for concepts that exist in the the training
                data.
            nepochs (int):
                Number of epochs for which to run the training.
            print_stats (int):
                If > 0 it will print stats every print_stats epochs.
            use_filters (bool):
                Each project in medcattrainer can have filters, do we want to
                respect those filters
                when calculating metrics.
            terminate_last (bool):
                If true, concept termination will be done after all training.
            use_overlaps (bool):
                Allow overlapping entities, nearly always False as it is very
                difficult to annotate overlapping entities.
            use_cui_doc_limit (bool):
                If True the metrics for a CUI will be only calculated if that
                CUI appears in a document, in other words if the document was
                annotated for that CUI. Useful in very specific situations
                when during the annotation process the set of CUIs changed.
            test_size (float):
                If > 0 the data set will be split into train test based on
                this ration. Should be between 0 and 1. Usually 0.1 is fine.
            devalue_others(bool):
                Check add_name for more details.
            use_groups (bool):
                If True concepts that have groups will be combined and stats
                will be reported on groups.
            never_terminate (bool):
                If True no termination will be applied
            train_from_false_positives (bool):
                If True it will use false positive examples detected by medcat
                and train from them as negative examples.
            extra_cui_filter(Optional[set]):
                This filter will be intersected with all other filters, or if
                all others are not set then only this one will be used.
            checkpoint (Optional[Optional[medcat.utils.checkpoint.Checkpoint]):
                The MedCAT Checkpoint object
            disable_progress (bool):
                Whether to disable the progress output (tqdm). Defaults to
                False.
            train_addons (bool):
                Whether to also train the addons (e.g MetaCATs). Defaults
                to False.

        Returns:
            tuple: Consisting of the following parts
                fp (dict):
                    False positives for each CUI.
                fn (dict):
                    False negatives for each CUI.
                tp (dict):
                    True positives for each CUI.
                p (dict):
                    Precision for each CUI.
                r (dict):
                    Recall for each CUI.
                f1 (dict):
                    F1 for each CUI.
                cui_counts (dict):
                    Number of occurrence for each CUI.
                examples (dict):
                    FP/FN examples of sentences for each CUI.
        """
        # checkpoint = self._init_ckpts(is_resumed, checkpoint)

        # the config.linking.filters stuff is used directly in
# medcat.linking.context_based_linker and medcat.linking.vector_context_model
        # as such, they need to be kept up to date with per-project filters
        # However, the original state needs to be kept track of
        # so that it can be restored after training

        fp: dict[str, int] = {}
        fn: dict[str, int] = {}
        tp: dict[str, int] = {}
        p: dict[str, float] = {}
        r: dict[str, float] = {}
        f1: dict[str, float] = {}
        examples: dict[str, object] = {}

        cui_counts: dict[str, int] = {}

        if test_size == 0:
            logger.info("Running without a test set, or train==test")
            test_set = data
            train_set = data
        else:
            train_set, test_set, _, _ = make_mc_train_test(data, self.cdb,
                                                           test_size=test_size)

    # if print_stats > 0:
    #     fp, fn, tp, p, r, f1, cui_counts, examples = self._print_stats(
    #         test_set, use_project_filters=use_filters,
    #         use_cui_doc_limit=use_cui_doc_limit, use_overlaps=use_overlaps,
    #         use_groups=use_groups, extra_cui_filter=extra_cui_filter)
        if reset_cui_count:
            self._reset_cui_counts(train_set)

        # Remove entities that were terminated
        if not never_terminate:
            for ann in (ann for project in train_set['projects']
                        for doc in project['documents']
                        for ann in doc['annotations']):
                if ann.get('killed', False):
                    self.unlink_concept_name(ann['cui'], ann['value'], False)

        # latest_trained_step = (checkpoint.count if checkpoint is not None
        #                        else 0)
        # (current_epoch,
        #  current_project,
        #  current_document) = self._get_training_start(train_set,
        #                                               latest_trained_step)
        current_epoch = 0
        current_project = 0
        current_document = 0

        for epoch in trange(current_epoch, nepochs, initial=current_epoch,
                            total=nepochs, desc='Epoch', leave=False,
                            disable=disable_progress):
            self._perform_epoch(current_project, current_document, train_set,
                                disable_progress, extra_cui_filter,
                                use_filters, train_from_false_positives,
                                devalue_others, terminate_last,
                                never_terminate)

        # if print_stats > 0 and (epoch + 1) % print_stats == 0:
        #     fp, fn, tp, p, r, f1, cui_counts, examples = self._print_stats(
        #         test_set, epoch=epoch + 1, use_project_filters=use_filters,
        #         use_cui_doc_limit=use_cui_doc_limit,
        #         use_overlaps=use_overlaps, use_groups=use_groups,
        #         extra_cui_filter=extra_cui_filter)

        # # reset the state of filters
        # self.config.linking.filters = orig_filters

        if (train_addons and
                # NOTE if no annnotaitons, no point
                count_all_annotations(data) > 0):
            self._train_addons(data)

        return fp, fn, tp, p, r, f1, cui_counts, examples

    def _train_meta_cat(self, addon: AddonComponent,
                        data: MedCATTrainerExport) -> None:
        # NOTE: dynamic import to avoid circular imports
        from medcat.components.addons.meta_cat import MetaCATAddon
        _, _, ann0 = next(iter_anns(data))
        if not isinstance(addon, MetaCATAddon):
            raise TypeError(
                f"Expected MetaCATAddon, got {type(addon)}")
        if 'meta_anns' not in ann0:
            logger.info("No Meta Annotations found to train MetaCATs")
            return
        # only consider meta-cats that have been defined
        # for the category
        ann_names = ann0['meta_anns'].keys()  # type: ignore
        # adapt to alternative names if applicable
        cnf = addon.config
        cat_name = cnf.general.get_applicable_category_name(ann_names)
        if cat_name in ann_names:
            logger.debug("Training MetaCAT %s", cnf.general.category_name)
            # NOTE: this is a mypy quirk - the types are compatible
            addon.mc.train_raw(cast(dict, data))

    def _train_addons(self, data: MedCATTrainerExport):
        logger.info("Training addons within train_supervised_raw")
        for addon in self._pipeline._addons:
            if addon.addon_type == "meta_cat":
                self._train_meta_cat(addon, data)

    def _perform_epoch(self, current_project: int,
                       current_document: int,
                       train_set: MedCATTrainerExport,
                       disable_progress: bool,
                       extra_cui_filter: Optional[set[str]],
                       use_filters: bool,
                       train_from_false_positives: bool,
                       devalue_others: bool,
                       terminate_last: bool,
                       never_terminate: bool,
                       ) -> None:
        # Print acc before training
        for idx_project in trange(current_project,
                                  len(train_set['projects']),
                                  initial=current_project,
                                  total=len(train_set['projects']),
                                  desc='Project', leave=False,
                                  disable=disable_progress):
            project = train_set['projects'][idx_project]
            with project_filters(
                    self.config.components.linking.filters, project,
                    extra_cui_filter, use_filters):
                self._train_supervised_for_project(
                    project, current_document, train_from_false_positives,
                    devalue_others)

        if terminate_last and not never_terminate:
            # Remove entities that were terminated,
            # but after all training is done
            # for project in train_set['projects']:
            #     for doc in project['documents']:
            #         for ann in doc_annotations:
            for ann in (ann for project in train_set['projects']
                        for doc in project['documents']
                        for ann in doc['annotations']):
                if ann.get('killed', False):
                    self.unlink_concept_name(ann['cui'], ann['value'], False)

    def _train_supervised_for_project(self,
                                      project: MedCATTrainerExportProject,
                                      current_document: int,
                                      train_from_false_positives: bool,
                                      devalue_others: bool):
        with self.config.meta.prepare_and_report_training(
                project['documents'], 1, True, project_name=project['name']
                ) as docs:
            with temp_changed_config(self.config.components.linking,
                                     'train', True):
                self._train_supervised_for_project2(
                    docs, current_document, train_from_false_positives,
                    devalue_others)

    def _train_supervised_for_project2(self,
                                       docs: list[MedCATTrainerExportDocument],
                                       current_document: int,
                                       train_from_false_positives: bool,
                                       devalue_others: bool):
        cnf_linking = self.config.components.linking
        for idx_doc in trange(current_document,
                              len(docs),
                              initial=current_document,
                              total=len(docs),
                              desc='Document', leave=False):
            doc = docs[idx_doc]
            with temp_changed_config(self.config.components.linking,
                                     'train', False):
                mut_doc = self.caller(doc['text'])

            # Compatibility with old output where annotations are a list
            for ann in doc['annotations']:
                if ann.get('killed', False):
                    continue
                logger.info("    Annotation %s (%s) [%d:%d]",
                            ann['value'], ann['cui'], ann['start'], ann['end'])
                cui = ann['cui']
                start = ann['start']
                end = ann['end']
                mut_entity = mut_doc.get_tokens(start, end)
                if not mut_entity:
                    logger.warning(
                        "When looking for CUI '%s' (value '%s') [%d...%d] "
                        "within the document '%s' (ID %s) was unable "
                        "to get any tokens that match the start and end. ",
                        cui, ann['value'], start, end,
                        doc['name'], doc['id'])
                    continue
                deleted = bool(ann.get('deleted', False))
                if not cnf_linking.filters.check_filters(cui):
                    continue
                try:
                    self.add_and_train_concept(
                        cui=cui, name=ann['value'], mut_doc=mut_doc,
                        mut_entity=mut_entity, negative=deleted,
                        devalue_others=devalue_others)
                except (ValueError, KeyError) as ve:
                    context_window = 20  # characters
                    splitter_left, splitter_right = "<", ">"
                    cur_text = doc['text']
                    context_start = max(start - context_window, 0)
                    context_end = min(end + context_window, len(cur_text) - 1)
                    context = (cur_text[context_start: start] +
                               splitter_left +
                               cur_text[start: end] +
                               splitter_right +
                               cur_text[end: context_end])
                    if context_start > 0:
                        context = "[...]" + context
                    if context_end < len(cur_text) - 1:
                        context += "[...]"
                    msg_template = (
                        "Failed to identify '%s' (%s) ([%d:%d]) "
                        "in '%s' %s within document %s | %s, "
                        "skipping training for this example")
                    msg_context = (
                        cui, ann['value'], ann['start'], ann['end'],
                        context, mut_entity, doc['id'], doc['name'])
                    if self.strict_train:
                        raise ValueError(msg_template % msg_context) from ve
                    else:
                        logger.warning(msg_template, *msg_context, exc_info=ve)
            if train_from_false_positives:
                fps: list[MutableEntity] = get_false_positives(doc, mut_doc)

                for fp in fps:  # type: ignore
                    fp_: MutableEntity = fp  # type: ignore
                    # TODO: allow adding/training
                    self.add_and_train_concept(
                        cui=fp_.cui, name=fp_.base.text,
                        mut_doc=mut_doc, mut_entity=fp_,
                        negative=True, do_add_concept=False)

            # latest_trained_step += 1
            # if (checkpoint is not None and checkpoint.steps is not None
            #         and latest_trained_step % checkpoint.steps == 0):
            #     checkpoint.save(self.cdb, latest_trained_step)

    def unlink_concept_name(self, cui: str, name: str,
                            preprocessed_name: bool = False) -> None:
        """Unlink a concept name from the CUI (or all CUIs if full_unlink),
        removes the link from the Concept Database (CDB). As a consequence
        medcat will never again link the `name` to this CUI - meaning the
        name will not be detected as a concept in the future.

        Args:
            cui (str):
                The CUI from which the `name` will be removed.
            name (str):
                The span of text to be removed from the linking dictionary.
            preprocessed_name (bool):
                Whether the name being used is preprocessed.

        Examples:

            >>> # To never again link C0020538 to HTN
            >>> cat.unlink_concept_name('C0020538', 'htn', False)
        """

        cuis = [cui]
        if preprocessed_name:
            names: dict[str, NameDescriptor] = {
                name: NameDescriptor([], set(), name, name.isupper())}
        else:
            names = prepare_name(name, self._pipeline.tokenizer, {},
                                 self._pn_configs)

        # If full unlink find all CUIs
        if self.config.general.full_unlink:
            logger.warning("In the config `full_unlink` is set to `True`. "
                           "Thus removing all CUIs linked to the specified "
                           "name (%s)", name)
            for n in names:
                if n not in self.cdb.name2info:
                    continue
                cuis.extend(self.cdb.name2info[n]['per_cui_status'].keys())

        # Remove name from all CUIs
        for c in cuis:
            self.cdb._remove_names(cui=c, names=names.keys())

    def add_and_train_concept(self,
                              cui: str,
                              name: str,
                              mut_doc: Optional[MutableDocument] = None,
                              mut_entity: Optional[
                                  Union[list[MutableToken],
                                        MutableEntity]] = None,
                              ontologies: set[str] = set(),
                              name_status: str = 'A',
                              type_ids: set[str] = set(),
                              description: str = '',
                              full_build: bool = True,
                              negative: bool = False,
                              devalue_others: bool = False,
                              do_add_concept: bool = True) -> None:
        r"""Add a name to an existing concept, or add a new concept, or do not
        do anything if the name or concept already exists. Perform training if
        spacy_entity and spacy_doc are set.

        Args:
            cui (str):
                CUI of the concept.
            name (str):
                Name to be linked to the concept (in the case of MedCATtrainer
                this is simply the selected value in text, no preprocessing or
                anything needed).
            mut_doc (Optional[MutableDocument]):
                Spacy representation of the document that was manually
                annotated.
            mut_entity (mut_entity: Optional[Union[list[MutableToken],
                                                   MutableEntity]]):
                Given the spacy document, this is the annotated span of text -
                list of annotated tokens that are marked with this CUI.
            ontologies (set[str]):
                ontologies in which the concept exists (e.g. SNOMEDCT, HPO)
            name_status (str):
                One of `P`, `N`, `A`
            type_ids (set[str]):
                Semantic type identifier (have a look at TUIs in UMLS or
                SNOMED-CT)
            description (str):
                Description of this concept.
            full_build (bool):
                If True the dictionary self.addl_info will also be populated,
                contains a lot of extra information about concepts, but can be
                very memory consuming. This is not necessary for normal
                functioning of MedCAT (Default Value `False`).
            negative (bool):
                Is this a negative or positive example.
            devalue_others (bool):
                If set, cuis to which this name is assigned and are not `cui`
                will receive negative training given that negative=False.
            do_add_concept (bool):
                Whether to add concept to CDB.
        """
        names = prepare_name(name, self._pipeline.tokenizer_with_tag, {},
                             self._pn_configs)
        if (not names and cui not in self.cdb.cui2info and
                name_status == 'P'):
            logger.warning(
                "No names were able to be prepared in "
                "CAT.add_and_train_concept method. As such no preferred name "
                "will be able to be specifeid. The CUI: '%s' and raw name: "
                "'%s'", cui, name)
        # Only if not negative, otherwise do not add the new name if in fact
        # it should not be detected
        if do_add_concept and not negative:
            self.cdb._add_concept(cui=cui, names=names, ontologies=ontologies,
                                  name_status=name_status, type_ids=type_ids,
                                  description=description,
                                  full_build=full_build)

        if mut_entity is None or mut_doc is None:
            return
        linker = self._pipeline.get_component(
            CoreComponentType.linking)
        if not isinstance(linker, TrainableComponent):
            logger.warning(
                "Linker cannot be trained during add_and_train_concept"
                "because it has no train method: %s", linker)
        else:
            # Train Linking
            if isinstance(mut_entity, list):
                mut_entity = self._pipeline.entity_from_tokens(mut_entity)
            linker.train(cui=cui, entity=mut_entity, doc=mut_doc,
                         negative=negative, names=names)

            if not negative and devalue_others:
                # Find all cuis
                cuis: set[str] = set()
                for n in names:
                    if n in self.cdb.name2info:
                        info = self.cdb.name2info[n]
                        cuis.update(info['per_cui_status'].keys())
                # Remove the cui for which we just added positive training
                if cui in cuis:
                    cuis.remove(cui)
                # Add negative training for all other CUIs that link to
                # these names
                for _cui in cuis:
                    linker.train(cui=_cui, entity=mut_entity, doc=mut_doc,
                                 negative=True)

    @property
    def _pn_configs(self) -> tuple[General, Preprocessing, CDBMaker]:
        return (self.config.general, self.config.preprocessing,
                self.config.cdb_maker)
