from typing import Optional, Callable, cast

from tqdm import tqdm
import traceback

from medcat.cat import CAT
from medcat.utils.filters import project_filters
from medcat.data.mctexport import (
    MedCATTrainerExport, MedCATTrainerExportProject,
    MedCATTrainerExportDocument, MedCATTrainerExportAnnotation)
from medcat.config.config import LinkingFilters
from medcat.cdb.concepts import CUIInfo, get_new_cui_info
from medcat.tokenizing.tokens import MutableEntity, MutableDocument


class StatsBuilder:

    def __init__(self,
                 filters: LinkingFilters,
                 addl_info: dict,
                 doc_getter: Callable[[str], Optional[MutableDocument]],
                 cui2info: dict[str, CUIInfo],
                 use_project_filters: bool = False,
                 use_overlaps: bool = False,
                 #  use_cui_doc_limit: bool = False,
                 #  use_groups: bool = False,
                 extra_cui_filter: Optional[set[str]] = None) -> None:
        self.filters = filters
        self.addl_info = addl_info
        self.doc_getter = doc_getter
        self.cui2info = cui2info
        self.use_project_filters = use_project_filters
        self.use_overlaps = use_overlaps
        # self.use_cui_doc_limit = use_cui_doc_limit
        # self.use_groups = use_groups
        self.extra_cui_filter = extra_cui_filter
        self._reset_stats()

    def _reset_stats(self):
        self.tp = 0
        self.fp = 0
        self.fn = 0
        self.fps: dict[str, int] = {}
        self.fns: dict[str, int] = {}
        self.tps: dict[str, int] = {}
        self.cui_prec: dict[str, float] = {}
        self.cui_rec: dict[str, float] = {}
        self.cui_f1: dict[str, float] = {}
        self.cui_counts: dict[str, int] = {}
        self.examples: dict = {'fp': {}, 'fn': {}, 'tp': {}}
        self.fp_docs: set = set()
        self.fn_docs: set = set()

    def process_project(self, project: MedCATTrainerExportProject) -> None:
        """Process the project.

        This processes each document in the project.

        Args:
            project (MedCATTrainerExportProject): The trainer export project.
        """
        project_name = cast(str, project.get('name'))
        project_id = cast(str, project.get('id'))

        documents = project["documents"]
        for dind, doc in tqdm(
            enumerate(documents),
            desc="Stats document",
            total=len(documents),
            leave=False,
        ):
            self.process_document(project_name, project_id, doc)

    def process_document(self, project_name: str, project_id: str,
                         doc: MedCATTrainerExportDocument
                         ) -> None:
        """Process the trainer export document.

        Args:
            project_name (str): The project within which this document lies.
            project_id (str): The project ID for the project.
            doc (MedCATTrainerExportDocument): The trainer export document.
        """
        anns = doc['annotations']

        # Apply document level filtering, in this case project_filter is
        # ignored while the extra_cui_filter is respected still
        # if self.use_cui_doc_limit:
        #     _cuis = set([ann['cui'] for ann in anns])
        #     if _cuis:
        #         self.filters.cuis = intersect_nonempty_set(_cuis,
        #             self.extra_cui_filter)
        #     else:
        #         self.filters.cuis = {'empty'}

        mut_doc: MutableDocument = self.doc_getter(
            doc['text'])  # type: ignore

        p_anns = mut_doc.linked_ents  # or all ents?

        (anns_norm, anns_norm_neg,
         anns_examples, _) = self._preprocess_annotations(
             project_name, project_id, doc, anns)

        p_anns_norm, p_anns_examples = self._process_p_anns(
            project_name, project_id, doc, p_anns)
        self._count_p_anns_norm(doc, anns_norm, anns_norm_neg,
                                p_anns_norm, p_anns_examples)
        self._process_anns_norm(doc, anns_norm, p_anns_norm, anns_examples)

    def _process_anns_norm(self, doc: MedCATTrainerExportDocument,
                           anns_norm: list[tuple[int, str]],
                           p_anns_norm: list[tuple[int, str]],
                           anns_examples: list[dict]) -> None:
        for iann, ann in enumerate(anns_norm):
            if ann not in p_anns_norm:
                cui = ann[1]
                self.fn += 1
                self.fn_docs.add(doc.get('name', 'unk'))

                self.fns[cui] = self.fns.get(cui, 0) + 1
                examples = self.examples['fn'].get(cui, [])
                self.examples['fn'][cui] = examples + [anns_examples[iann]]

    def _process_p_anns(self, project_name: str, project_id: str,
                        doc: MedCATTrainerExportDocument,
                        p_anns: list[MutableEntity]
                        ) -> tuple[list[tuple[int, str]], list[dict]]:
        p_anns_norm: list[tuple[int, str]] = []
        p_anns_examples: list[dict] = []
        for ann in p_anns:
            cui = ann.cui

            p_anns_norm.append((ann.base.start_char_index, cui))
            p_anns_examples.append(self._create_annotation_2(
                project_name, project_id, cui, doc, ann))
        return p_anns_norm, p_anns_examples

    def _count_p_anns_norm(self, doc: MedCATTrainerExportDocument,
                           anns_norm: list[tuple[int, str]],
                           anns_norm_neg: list[tuple[int, str]],
                           p_anns_norm: list[tuple[int, str]],
                           p_anns_examples: list[dict]) -> None:
        for iann, ann in enumerate(p_anns_norm):
            cui = ann[1]
            if ann in anns_norm:
                self.tp += 1
                self.tps[cui] = self.tps.get(cui, 0) + 1

                example = p_anns_examples[iann]

                examples = self.examples['tp'].get(cui, [])
                self.examples['tp'][cui] = examples + [example]
            else:
                self.fp += 1
                self.fps[cui] = self.fps.get(cui, 0) + 1
                self.fp_docs.add(doc.get('name', 'unk'))

                # Add example for this FP prediction
                example = p_anns_examples[iann]
                if ann in anns_norm_neg:
                    # Means that it really was annotated as negative
                    example['real_fp'] = True

                examples = self.examples['fp'].get(cui, [])
                self.examples['fp'][cui] = examples + [example]

    def _create_annotation(self, project_name: str, project_id: str, cui: str,
                           doc: MedCATTrainerExportDocument,
                           ann: MedCATTrainerExportAnnotation) -> dict:
        return {"text": doc['text'][max(0, ann['start'] - 60):ann['end'] + 60],
                "cui": cui,
                "start": ann['start'],
                "end": ann['end'],
                "source value": ann['value'],
                "acc": 1,
                "project name": project_name,
                "document name": doc.get('name'),
                "project id": project_id,
                "document id": doc.get('id')}

    def _create_annotation_2(self, project_name: str, project_id: str,
                             cui: str, doc: MedCATTrainerExportDocument,
                             ann: MutableEntity) -> dict:
        start = max(0, ann.base.start_char_index - 60)
        end = ann.base.end_char_index + 60
        return {"text": doc['text'][start:end],
                "cui": cui,
                "start": ann.base.start_char_index,
                "end": ann.base.start_char_index,
                "source value": ann.base.text,
                "acc": float(ann.context_similarity),
                "project name": project_name,
                "document name": doc.get('name'),
                "project id": project_id,
                "document id": doc.get('id')}

    def _preprocess_annotations(self, project_name: str, project_id: str,
                                doc: MedCATTrainerExportDocument,
                                anns: list[MedCATTrainerExportAnnotation]
                                ) -> tuple[list[tuple[int, str]],
                                           list[tuple[int, str]],
                                           list[dict],
                                           list[str]]:
        anns_norm: list[tuple[int, str]] = []
        anns_norm_neg: list[tuple[int, str]] = []
        anns_examples: list[dict] = []
        anns_norm_cui: list[str] = []
        for ann in anns:
            cui = ann['cui']
            if self.filters.check_filters(cui):

                if (ann.get('validated', True) and
                    (not ann.get('killed', False) and not ann.get('deleted',
                                                                  False))):
                    anns_norm.append((ann['start'], cui))
                    anns_examples.append(self._create_annotation(
                        project_name, project_id, cui, doc, ann))
                elif (ann.get('validated', True) and
                      (ann.get('killed', False) or ann.get('deleted', False))):
                    anns_norm_neg.append((ann['start'], cui))

                if ann.get("validated", True):
                    # This is used to test was someone annotating for this
                    # CUI in this document
                    anns_norm_cui.append(cui)
                    self.cui_counts[cui] = self.cui_counts.get(cui, 0) + 1
        return anns_norm, anns_norm_neg, anns_examples, anns_norm_cui

    def finalise_report(self, epoch: int, do_print: bool = True):
        """Finalise the report / metrics.

        This prints out the overall metrics and calculates per CUI metrics.

        Args:
            epoch (int): The number of the current epoch.
            do_print (bool, optional): Whether to print the output.
                Defaults to True.
        """
        try:
            if self.tp + self.fp == 0:
                prec = 0.0
            else:
                prec = self.tp / (self.tp + self.fp)
            if self.tp + self.fp == 0:
                rec = 0.0
            else:
                rec = self.tp / (self.tp + self.fn)
            if prec == 0 and rec == 0:
                f1 = 0.0
            else:
                f1 = 2 * (prec * rec) / (prec + rec)
            if do_print:
                print("Epoch: {}, Prec: {}, Rec: {}, F1: {}\n".format(
                    epoch, prec, rec, f1))
                print("Docs with false positives: {}\n".format("; ".join(
                    [str(x) for x in list(self.fp_docs)[0:10]])))
                print("Docs with false negatives: {}\n".format("; ".join(
                    [str(x) for x in list(self.fn_docs)[0:10]])))

            # Sort fns & prec
            fps = {k: v for k, v in sorted(self.fps.items(),
                   key=lambda item: item[1], reverse=True)}
            fns = {k: v for k, v in sorted(self.fns.items(),
                   key=lambda item: item[1], reverse=True)}
            tps = {k: v for k, v in sorted(self.tps.items(),
                   key=lambda item: item[1], reverse=True)}

            # F1 per concept
            for cui in tps.keys():
                prec = tps[cui] / (tps.get(cui, 0) + fps.get(cui, 0))
                rec = tps[cui] / (tps.get(cui, 0) + fns.get(cui, 0))
                f1 = 2 * (prec * rec) / (prec + rec)
                self.cui_prec[cui] = prec
                self.cui_rec[cui] = rec
                self.cui_f1[cui] = f1

            # Get top 10
            pr_fps = [(self._get_pref_name(cui),
                      cui, fps[cui]) for cui in list(fps.keys())[0:10]]
            pr_fns = [(self._get_pref_name(cui),
                       cui, fns[cui]) for cui in list(fns.keys())[0:10]]
            pr_tps = [(self._get_pref_name(cui),
                       cui, tps[cui]) for cui in list(tps.keys())[0:10]]

            if do_print:
                print("\n\nFalse Positives\n")
                for one in pr_fps:
                    print("{:70} - {:20} - {:10}".format(str(one[0])[0:69],
                                                         str(one[1])[0:19],
                                                         one[2]))
                print("\n\nFalse Negatives\n")
                for one in pr_fns:
                    print("{:70} - {:20} - {:10}".format(str(one[0])[0:69],
                                                         str(one[1])[0:19],
                                                         one[2]))
                print("\n\nTrue Positives\n")
                for one in pr_tps:
                    print("{:70} - {:20} - {:10}".format(str(one[0])[0:69],
                                                         str(one[1])[0:19],
                                                         one[2]))
                print("*" * 110 + "\n")

        except Exception:
            traceback.print_exc()

    def _empty(self, cui: str) -> CUIInfo:
        return get_new_cui_info(
            cui=cui, preferred_name=cui, names=set((cui, )))

    def _get_or_empty(self, cui: str) -> CUIInfo:
        return self.cui2info.get(cui, self._empty(cui))

    def _get_pref_name(self, cui: str) -> str:
        info = self._get_or_empty(cui)
        return info['preferred_name'] or list(info['names'])[0]

    def unwrap(self) -> tuple[
        dict[str, int], dict[str, int], dict[str, int],
        dict[str, float], dict[str, float], dict[str, float],
        dict[str, int], dict
    ]:
        return (self.fps, self.fns, self.tps,
                self.cui_prec, self.cui_rec, self.cui_f1,
                self.cui_counts, self.examples)

    @classmethod
    def from_cat(cls, cat: CAT,
                 use_project_filters: bool = False,
                 use_overlaps: bool = False,
                 #  use_cui_doc_limit: bool = False,
                 #  use_groups: bool = False,
                 extra_cui_filter: Optional[set[str]] = None
                 ) -> 'StatsBuilder':
        """Get the stats builder from a model pack and some extra information.

        Args:
            cat (CAT):
                The model pack.
            use_project_filters (bool, optional):
                Whether to use per project filters. Defaults to False.
            use_overlaps (bool, optional):
                Whether to allow overlaps. Defaults to False.
            extra_cui_filter (Optional[set[str]], optional):
                Extra CUI filter. Defaults to None.

        Returns:
            StatsBuilder: The stats builder.
        """
        return StatsBuilder(addl_info=cat.cdb.addl_info,
                            filters=cat.config.components.linking.filters,
                            doc_getter=cat.__call__,
                            # cui2group=cat.cdb.addl_info['cui2group'],
                            # cui2preferred_name=cat.cdb.cui2preferred_name,
                            cui2info=cat.cdb.cui2info,
                            use_project_filters=use_project_filters,
                            use_overlaps=use_overlaps,
                            # use_cui_doc_limit=use_cui_doc_limit,
                            # use_groups=use_groups,
                            extra_cui_filter=extra_cui_filter)


def get_stats(cat: CAT,
              data: MedCATTrainerExport,
              epoch: int = 0,
              use_project_filters: bool = False,
              use_overlaps: bool = False,
              #   use_cui_doc_limit: bool = False,
              #   use_groups: bool = False,
              extra_cui_filter: Optional[set[str]] = None,
              do_print: bool = True) -> tuple[
        dict[str, int], dict[str, int], dict[str, int],
        dict[str, float], dict[str, float], dict[str, float],
        dict[str, int], dict
]:
    """TODO: Refactor and make nice
    Print metrics on a dataset (F1, P, R), it will also print the concepts
    that have the most FP,FN,TP.

    Args:
        cat: (CAT):
            The model pack.
        data (dict):
            The json object that we get from MedCATtrainer on export.
        epoch (int):
            Used during training, so we know what epoch is it.
        use_project_filters (bool):
            Each project in MedCATtrainer can have filters, do we want to
            respect those filters when calculating metrics.
        use_overlaps (bool):
            Allow overlapping entities, nearly always False as it is very
            difficult to annotate overlapping entities.
        use_cui_doc_limit (bool):
            If True the metrics for a CUI will be only calculated if that CUI
            appears in a document, in other words if the document was
            annotated for that CUI. Useful in very specific situations when
            during the annotation process the set of CUIs changed.
        use_groups (bool):
            If True concepts that have groups will be combined and stats will
            be reported on groups.
        extra_cui_filter(Optional[set]):
            This filter will be intersected with all other filters, or if all
            others are not set then only this one will be used.
        do_print (bool):
            Whether to print stats out. Defaults to True.

    Returns:
        fps (dict):
            False positives for each CUI.
        fns (dict):
            False negatives for each CUI.
        tps (dict):
            True positives for each CUI.
        cui_prec (dict):
            Precision for each CUI.
        cui_rec (dict):
            Recall for each CUI.
        cui_f1 (dict):
            F1 for each CUI.
        cui_counts (dict):
            Number of occurrence for each CUI.
        examples (dict):
            Examples for each of the fp, fn, tp.
            Format will be examples['fp']['cui'][<list_of_examples>].
    """
    builder = StatsBuilder.from_cat(cat,
                                    use_project_filters=use_project_filters,
                                    use_overlaps=use_overlaps,
                                    # use_cui_doc_limit=use_cui_doc_limit,
                                    # use_groups=use_groups,
                                    extra_cui_filter=extra_cui_filter)
    for pind, project in tqdm(enumerate(data['projects']),
                              desc="Stats project",
                              total=len(data['projects']),
                              leave=False):
        with project_filters(cat.config.components.linking.filters,
                             project,
                             builder.extra_cui_filter,
                             builder.use_project_filters):
            builder.process_project(project)
    # this is the part that prints out the stats
    builder.finalise_report(epoch, do_print=do_print)
    return builder.unwrap()
