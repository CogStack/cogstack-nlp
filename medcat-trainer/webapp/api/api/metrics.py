import json
import logging
import math
import os
import warnings
from collections import Counter
from typing import List, Dict
from background_task import background

import numpy as np
import pandas as pd
import torch
from background_task.models import Task
from django.contrib.auth.models import User
from django.db.models import QuerySet
from medcat.stats.stats import get_stats
from medcat.cat import CAT
from medcat.cdb import CDB
from medcat.config.config_meta_cat import ConfigMetaCAT
from medcat.components.addons.meta_cat.meta_cat import MetaCATAddon
from medcat.components.addons.meta_cat.mctokenizers.tokenizers import TokenizerWrapperBase
from medcat.components.addons.meta_cat.data_utils import prepare_from_json, encode_category_values
from medcat.components.addons.meta_cat.ml_utils import create_batch_piped_data
from medcat.vocab import Vocab
from torch import nn

from api.admin import retrieve_project_data
from api.models import AnnotatedEntity, ProjectAnnotateEntities, ProjectMetrics as AppProjectMetrics
from api.utils import clear_cdb_cnf_addons
from core.settings import MEDIA_ROOT

_dt_fmt = '%Y-%m-%d %H:%M:%S.%f'

logger = logging.getLogger(__name__)


@background(schedule=1, queue='metrics')
def calculate_metrics(project_ids: List[int], report_name: str):
    """
    Computes metrics in a background task
    :param projects: list of projects to compute metrics for.
        Uses the 'first' for the CDB / vocab or ModelPack,
        but should be the same CDB, but will still try and compute metrics regardless.
    :return: computed metrics results
    """
    logger.info('Calculating metrics for report: %s', report_name)
    projects = [ProjectAnnotateEntities.objects.filter(id=p_id).first() for p_id in project_ids]
    loaded_model_pack = False
    if projects[0].model_pack:
        # assume the model pack is set.
        cat = CAT.load_model_pack(projects[0].model_pack.model_pack.path)
        loaded_model_pack = True
    else:
        # assume the cdb / vocab is set in these projects
        cdb = CDB.load(projects[0].concept_db.cdb_file.path)
        clear_cdb_cnf_addons(cdb, projects[0].concept_db.name)
        vocab = Vocab.load(projects[0].vocab.vocab_file.path)
        cat = CAT(cdb, vocab, config=cdb.config)
    project_data = retrieve_project_data(projects)
    metrics = ProjectMetrics(project_data, cat)
    report = metrics.generate_report(meta_ann=loaded_model_pack)
    report_file_path = f'{MEDIA_ROOT}/{report_name}.json'
    json.dump(report, open(report_file_path, 'w'))
    apm = AppProjectMetrics()
    apm.report_name_generated = report_name
    apm.report.name = report_file_path
    apm.save()
    apm.projects.set(projects)
    logger.info('Finished calculating metrics for report: %s, saved results in ProjectMetrics(id=%s)',
                report_name, apm.id)


class ProjectMetrics(object):
    """
    Class to analyse MedCATtrainer exports
    """

    def __init__(self, mct_export_data: dict, cat: CAT):
        """
        :param mct_export_paths: List of paths to MedCATtrainer exports
        """
        self.mct_export = mct_export_data
        self.cat = cat
        self.projects2names = {}
        self.projects2doc_ids = {}
        self.docs2names = {}
        self.docs2texts = {}
        self.meta_task_summary = {}
        self.annotations = self._annotations()

    def _annotations(self):
        ann_lst = []
        for proj in self.mct_export['projects']:
            self.projects2names[proj['id']] = proj['name']
            self.projects2doc_ids[proj['id']] = [doc['id'] for doc in proj['documents']]
            for doc in proj['documents']:
                self.docs2names[doc['id']] = doc['name']
                self.docs2texts[doc['id']] = doc['text']
                for anns in doc['annotations']:
                    meta_anns_dict = dict()
                    for meta_ann in anns['meta_anns'].items():
                        meta_anns_dict.update({meta_ann[0]: meta_ann[1]['value']})
                    _anns = anns.copy()
                    _anns.pop('meta_anns')
                    output = dict()
                    output['project'] = proj['name']
                    output['project_id'] = proj['id']
                    output['document_name'] = doc['name']
                    output['document_id'] = doc['id']
                    output.update(_anns)
                    output.update(meta_anns_dict)
                    ann_lst.append(output)
        return ann_lst

    def annotation_df(self):
        """
        DataFrame of all annotations created
        :return: DataFrame
        """
        annotation_df = pd.DataFrame(self.annotations)
        if self.cat:
            annotation_df.insert(5, 'concept_name', annotation_df['cui'].map(self.cat.cdb.get_name))
        annotation_df['last_modified'] = pd.to_datetime(annotation_df['last_modified']).dt.tz_localize(None)
        return annotation_df

    def concept_summary(self, extra_cui_filter=None):
        """
        Summary of only correctly annotated concepts from a mct export
        :return: DataFrame summary of annotations.
        """
        concept_output = self.annotation_df()
        concept_output = concept_output[concept_output['validated'] & ((concept_output['correct']) | (concept_output['alternative']))]
        if self.cat:
            concept_count = concept_output.groupby(['cui', 'concept_name']).agg({'value': set, 'id': 'count'})
        else:
            concept_count = concept_output.groupby(['cui']).agg({'value': set, 'id': 'count'})
        concept_count_df = pd.DataFrame(concept_count).reset_index(drop=False)
        concept_count_df['variations'] = concept_count_df['value'].apply(lambda x: len(x))
        concept_count_df.rename({'id': 'concept_count'}, axis=1, inplace=True)
        concept_count_df = concept_count_df.sort_values(by='concept_count', ascending=False).reset_index(drop=True)
        concept_count_df['count_variations_ratio'] = round(concept_count_df['concept_count'] /
                                                           concept_count_df['variations'], 3)
        if self.cat:
            fps, fns, tps, cui_prec, cui_rec, cui_f1, cui_counts, examples = get_stats(self.cat,
                                                                                       data=self.mct_export,
                                                                                       use_project_filters=True,
                                                                                       extra_cui_filter=extra_cui_filter)
            # remap tps, fns, fps to specific user annotations
            examples = self.enrich_medcat_metrics(examples)
            concept_count_df['fps'] = concept_count_df['cui'].map(fps)
            concept_count_df['fns'] = concept_count_df['cui'].map(fns)
            concept_count_df['tps'] = concept_count_df['cui'].map(tps)
            concept_count_df['cui_prec'] = concept_count_df['cui'].map(cui_prec)
            concept_count_df['cui_rec'] = concept_count_df['cui'].map(cui_rec)
            concept_count_df['cui_f1'] = concept_count_df['cui'].map(cui_f1)
            #concept_count_df['cui_counts'] = concept_count_df['cui'].map(cui_counts) # TODO check why cui counts is incorrect
            examples_df = pd.DataFrame(examples).rename_axis('cui').reset_index(drop=False). \
                rename(columns={'fp': 'fp_examples',
                                'fn': 'fn_examples',
                                'tp': 'tp_examples'})
            concept_count_df = concept_count_df.merge(examples_df, how='left', on='cui').fillna(0)

            # Process examples to ensure underscores are preserved
            for col in ['fp_examples', 'fn_examples', 'tp_examples']:
                if col in concept_count_df.columns:
                    concept_count_df[col] = concept_count_df[col].apply(lambda x: x if isinstance(x, list) else [])

        # brittle - probably shouldn't rely on cat._print_stats ...
        concept_summary = concept_count_df.to_dict('records')
        # convert sets to lists and ensure examples are properly formatted
        concept_summary = [{k: list(v) if isinstance(v, set) else v for k, v in row.items()} for row in concept_summary]
        return concept_summary

    def enrich_medcat_metrics(self, examples):
        """
        Add the user prop to the medcat output metrics. Can potentially add more later for each of the categories
        """
        for tp in [i for e_i in examples['tp'].values() for i in e_i]:
            try:
                ann = AnnotatedEntity.objects.get(project_id=tp['project id'], document_id=tp['document id'],
                                                  start_ind=tp['start'], end_ind=tp['end'])
                tp['user'] = ann.user.username
            except:
                tp['user'] = None
        for fp in (i for e_i in examples['fp'].values() for i in e_i):
            try:
                ann = AnnotatedEntity.objects.get(project_id=fp['project id'], document_id=fp['document id'],
                                                  start_ind=fp['start'], end_ind=fp['end'])
                fp['user'] = ann.user.username
            except:
                fp['user'] = None
        for fn in (i for e_i in examples['fn'].values() for i in e_i):
            try:
                ann = AnnotatedEntity.objects.get(project_id=fn['project id'], document_id=fn['document id'],
                                                  start_ind=fn['start'], end_ind=fn['end'])
                fn['user'] = ann.user.username
            except:
                fn['user'] = None
        return examples

    def user_stats(self, by_user: bool = True):
        """
        Summary of user annotation work done

        :param by_user: User Stats grouped by user rather than day
        :return: DataFrame of user annotation work done
        """
        df = self.annotation_df()[['user', 'last_modified']]
        data = df.groupby([df['last_modified'].dt.year.rename('year'),
                           df['last_modified'].dt.month.rename('month'),
                           df['last_modified'].dt.day.rename('day'),
                           df['user']]).agg({'count'})
        data = pd.DataFrame(data)
        data.columns = data.columns.droplevel()
        data = data.reset_index(drop=False)
        data['date'] = pd.to_datetime(data[['year', 'month', 'day']])
        if by_user:
            data = data[['user', 'count']].groupby(by='user').agg(sum)
            data = data.reset_index(drop=False).sort_values(by='count', ascending=False).reset_index(drop=True)
            return data
        return data[['user', 'count', 'date']]

    def rename_meta_anns(self, meta_anns2rename=dict(), meta_ann_values2rename=dict()):
        """
        TODO: the meta_ann_values2rename has issues
        :param meta_anns2rename: Example input: `{'Subject/Experiencer': 'Subject'}`
        :param meta_ann_values2rename: Example input: `{'Subject':{'Relative':'Other'}}`
        :return:
        """
        for proj in self.mct_export['projects']:
            for doc in proj['documents']:
                for anns in doc['annotations']:
                    if len(anns['meta_anns']) > 0:
                        for meta_name2replace in meta_anns2rename:
                            try:
                                anns['meta_anns'][meta_anns2rename[meta_name2replace]] = anns['meta_anns'].pop(meta_name2replace)
                                anns['meta_anns'][meta_anns2rename[meta_name2replace]]['name'] = meta_anns2rename[meta_name2replace]
                                for meta_ann_name, meta_values in meta_ann_values2rename.items():
                                    if anns['meta_anns'][meta_anns2rename[meta_name2replace]]['name'] == meta_ann_name:
                                        for value in meta_values:
                                            if anns['meta_anns'][meta_anns2rename[meta_name2replace]]['value'] == value:
                                                anns['meta_anns'][meta_anns2rename[meta_name2replace]]['value'] = meta_ann_values2rename[meta_ann_name][value]
                            except KeyError:
                                pass
        self.annotations = self._annotations()
        return

    def _eval_model(self, model: nn.Module, data: List, config: ConfigMetaCAT, tokenizer: TokenizerWrapperBase) -> Dict:
        device = torch.device(config.general.device)  # Create a torch device
        batch_size_eval = config.general.batch_size_eval
        pad_id = config.model.padding_idx
        ignore_cpos = config.model.ignore_cpos
        class_weights = config.train.class_weights

        if class_weights is not None:
            class_weights = torch.FloatTensor(class_weights).to(device)
            criterion = nn.CrossEntropyLoss(weight=class_weights)  # Set the criterion to Cross Entropy Loss
        else:
            criterion = nn.CrossEntropyLoss()  # Set the criterion to Cross Entropy Loss

        y_eval = [x[2] for x in data]
        num_batches = math.ceil(len(data) / batch_size_eval)
        running_loss = []
        all_logits = []
        model.to(device)
        model.eval()

        with torch.no_grad():
            for i in range(num_batches):
                x, cpos, attention_mask, y = create_batch_piped_data(data,
                                                     i*batch_size_eval,
                                                     (i+1)*batch_size_eval,
                                                     device=device,
                                                     pad_id=pad_id)
                logits = model(x, cpos, ignore_cpos=ignore_cpos)
                loss = criterion(logits, y)

                # Track loss and logits
                running_loss.append(loss.item())
                all_logits.append(logits.detach().cpu().numpy())

        predictions = np.argmax(np.concatenate(all_logits, axis=0), axis=1)
        return predictions

    def _eval(self, metacat_model, mct_export):
        # TODO: Should be moved into
        g_config = metacat_model.config.general
        t_config = metacat_model.config.train
        t_config['test_size'] = 0
        t_config['shuffle_data'] = False
        t_config['prerequisites'] = {}
        t_config['cui_filter'] = {}

        # Prepare the data
        assert metacat_model.tokenizer is not None
        data = prepare_from_json(mct_export, g_config['cntx_left'], g_config['cntx_right'], metacat_model.tokenizer,
                                 cui_filter=t_config['cui_filter'],
                                 replace_center=g_config['replace_center'], prerequisites=t_config['prerequisites'],
                                 lowercase=g_config['lowercase'])

        # Check is the name there
        category_name = g_config['category_name']
        if category_name not in data:
            warnings.warn(f"The meta_model {category_name} does not exist in this MedCATtrainer export.", UserWarning)
            return {category_name: f"{category_name} does not exist"}

        data = data[category_name]

        # We already have everything, just get the data
        category_value2id = g_config['category_value2id']
        data, _, _ = encode_category_values(data, existing_category_value2id=category_value2id)
        logger.info(_)
        # Run evaluation
        assert metacat_model.tokenizer is not None
        result = self._eval_model(metacat_model.model, data, config=metacat_model.config, tokenizer=metacat_model.tokenizer)

        return {'predictions': result, 'meta_values': _}

    def full_annotation_df(self) -> pd.DataFrame:
        """
        DataFrame of all annotations created including meta_annotation predictions.
        This function is similar to annotation_df with the addition of Meta_annotation predictions from the medcat model.
        prerequisite Args: MedcatTrainer_export([mct_export_paths], model_pack_path=<path to medcat model>)
        """
        anns_df = self.annotation_df()
        meta_df = anns_df[anns_df['validated'] & ~anns_df['deleted'] &
                          ~anns_df['killed'] & ~anns_df['irrelevant']]
        meta_df = meta_df.reset_index(drop=True)

        all_meta_cats = self.cat.get_addons_of_type(MetaCATAddon)

        for meta_model_card in self.cat.get_model_card(as_dict=True)['MetaCAT models']:
            meta_model_task = meta_model_card['Category Name']
            logger.info(f'Checking metacat model: {meta_model_task}')
            _meta_models = [mc for mc in all_meta_cats
                           if mc.config.general.category_name == meta_model_task]
            if not _meta_models:
                logger.warning(f'MetaCAT model {meta_model_task} not found in the CAT instance.')
                continue
            meta_model = _meta_models[0]
            meta_results = self._eval(meta_model, self.mct_export)
            meta_values = {v: k for k, v in meta_results['meta_values'].items()}
            pred_meta_values = []
            counter = 0
            for meta_value in meta_df[meta_model_task]:
                if pd.isnull(meta_value):
                    pred_meta_values.append(np.nan)
                else:
                    pred_meta_values.append(meta_values.get(meta_results['predictions'][counter], np.nan))
                    counter += 1
            meta_df.insert(meta_df.columns.get_loc(meta_model_task) + 1, 'predict_' + meta_model_task, pred_meta_values)

        return meta_df

    def meta_anns_concept_summary(self) -> List[Dict]:
        """Calculate performance metrics for meta annotations per concept.

        Returns:
            List[Dict]: List of dictionaries containing concept-level meta annotation metrics
        """
        meta_df = self.full_annotation_df()
        meta_performance = {}

        for cui in meta_df.cui.unique():
            concept_df = meta_df[meta_df['cui'] == cui]
            meta_task_results = {}

            for meta_model_card in self.cat.get_model_card(as_dict=True)['MetaCAT models']:
                meta_task = meta_model_card['Category Name']
                meta_classes = meta_model_card['Classes'].keys()

                # Calculate per-class metrics
                class_metrics = {}
                total_instances = 0

                for meta_value in meta_classes:
                    # Get predictions and ground truth for this class
                    preds = concept_df['predict_' + meta_task] == meta_value
                    truths = concept_df[meta_task] == meta_value

                    # Calculate metrics
                    tp = int((preds & truths).sum())
                    fp = int((preds & ~truths).sum())
                    fn = int((~preds & truths).sum())
                    total = int(truths.sum())
                    total_instances += total

                    # Store metrics
                    class_metrics[meta_value] = {
                        'total': total,
                        'f1': float(tp / (tp + 0.5 * (fp + fn)) if (tp + fp + fn) > 0 else 0),
                        'prec': float(tp / (tp + fp) if (tp + fp) > 0 else 0),
                        'rec': float(tp / (tp + fn) if (tp + fn) > 0 else 0)
                    }

                # Calculate macro averages (unweighted)
                macro_metrics = {
                    'f1': float(sum(m['f1'] for m in class_metrics.values()) / len(meta_classes)),
                    'prec': float(sum(m['prec'] for m in class_metrics.values()) / len(meta_classes)),
                    'rec': float(sum(m['rec'] for m in class_metrics.values()) / len(meta_classes))
                }

                # Calculate micro averages (weighted by class size)
                if total_instances > 0:
                    micro_metrics = {
                        'f1': float(sum(m['f1'] * m['total'] for m in class_metrics.values()) / total_instances),
                        'prec': float(sum(m['prec'] * m['total'] for m in class_metrics.values()) / total_instances),
                        'rec': float(sum(m['rec'] * m['total'] for m in class_metrics.values()) / total_instances)
                    }
                else:
                    micro_metrics = {'f1': 0.0, 'prec': 0.0, 'rec': 0.0}

                # Store results for this meta task
                meta_task_results[meta_task] = {
                    'classes': class_metrics,
                    'macro': macro_metrics,
                    'micro': micro_metrics
                }

            # Store results for this concept
            meta_performance[cui] = {
                'cui': cui,
                'concept_name': self.cat.cdb.cui2info[cui]['preferred_name'],
                'meta_tasks': meta_task_results
            }

        return list(meta_performance.values())

    def generate_report(self, meta_ann=False):
        if meta_ann:
            anno_df = self.full_annotation_df()
        else:
            anno_df = self.annotation_df()

        anno_df['last_modified'] = anno_df['last_modified'].dt.strftime(_dt_fmt)
        anno_df.fillna('-', inplace=True)

        meta_anns_summary = None
        if meta_ann:
            meta_anns_summary = self.meta_anns_concept_summary()

        # assumes all projects have the same meta_anno_defs - this would break further up if not the case.
        meta_anno_task_summary = self.mct_export['projects'][0]['meta_anno_defs']

        return {'user_stats': self.user_stats().to_dict('records'),
                'concept_summary': self.concept_summary(),
                'annotation_summary': anno_df.to_dict('records'),
                'meta_anno_summary': meta_anns_summary,
                'projects2doc_ids': self.projects2doc_ids,
                'docs2text': self.docs2texts,
                'projects2name': self.projects2names,
                'docs2name': self.docs2names,
                'meta_anns_task_summary': meta_anno_task_summary}
