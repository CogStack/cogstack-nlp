import plotly
import plotly.graph_objects as go
from medcat.cat import CAT
from datetime import date
from typing import cast
import tempfile
from contextlib import contextmanager

import os
import json
import pandas as pd
from collections import Counter
from typing import Iterator, Optional, Union, TypedDict, Any

from medcat.components.addons.meta_cat.meta_cat import MetaCATAddon, MetaCAT
from medcat.stats.stats import get_stats
from medcat.utils.legacy.identifier import is_legacy_model_pack
from medcat.data.mctexport import (
    MedCATTrainerExport as _MedCATTrainerExport,
    MedCATTrainerExportAnnotation, iter_anns,
    MetaAnnotation)


DATETIME_FORMAT = r"%Y-%m-%d:%H:%M:%S"


class AnnotationOutput(TypedDict, total=False):
    project_name: str
    document_name: str


class MetaAnnotationPredictions(TypedDict):
    predictions: dict
    meta_values: Any


class MedcatTrainer_export(object):
    """
    Class to analyse MedCATtrainer exports
    """

    def __init__(self, mct_export_paths: list[str],
                 model_pack_path: Optional[str] = None):
        """
        :param mct_export_paths: List of paths to MedCATtrainer exports
        :param model_pack_path: Path to medcat modelpack
        """
        self.cat: Optional[CAT] = None
        self.is_legacy_model_pack = False
        if model_pack_path:
            self.cat = CAT.load_model_pack(model_pack_path)
            mpp = model_pack_path.removesuffix(".zip")
            if os.path.exists(mpp):
                self.is_legacy_model_pack = is_legacy_model_pack(mpp)
            else:
                # with medcat-den injected, can't have saved legacy model packs
                self.is_legacy_model_pack = False
        self.mct_export_paths = mct_export_paths
        self.mct_export = self._load_mct_exports(self.mct_export_paths)
        self.project_names: list[str] = []
        self.document_names: list[str] = []
        self.annotations = self._annotations()
        self.model_pack_path = model_pack_path
        if model_pack_path is not None:
            if model_pack_path[-4:] == '.zip':
                self.model_pack_path = model_pack_path[:-4]

    def _add_to_list_if_not_last(self, in_list: list[str], new_item: str):
        if not in_list:
            in_list.append(new_item)
        elif in_list[-1] != new_item:
            in_list.append(new_item)

    def _iter_anns(self, add_doc_names: bool = True,
                   add_proj_names: bool = True
                   ) -> Iterator[
                       tuple[str, str, MedCATTrainerExportAnnotation]]:
        for (proj_name, *_), doc, ann in iter_anns(self.mct_export):
            doc_name = doc['name']
            if add_proj_names:
                self._add_to_list_if_not_last(self.project_names, proj_name)
            if add_doc_names:
                self._add_to_list_if_not_last(self.document_names, doc_name)
            yield proj_name, doc_name, ann

    def _annotations(self) -> list[AnnotationOutput]:
        ann_lst = []
        # reset project and document names
        # in case of a second time calling _annotations()
        # i.e if/when renaming meta annotations
        self.project_names.clear()
        self.document_names.clear()
        for proj_name, doc_name, ann in self._iter_anns():
            meta_anns_dict = dict()
            if 'meta_anns' in ann:
                _meta_anns = ann['meta_anns']  # type: ignore
                meta_anns: list[dict]
                if isinstance(_meta_anns, dict):
                    # NOTE: mypy doesn't recognise the type for some readon
                    meta_anns = list(_meta_anns.values())  # type: ignore
                elif isinstance(_meta_anns, list):
                    # NOTE: mypy doesn't recognise the type for some readon
                    meta_anns = list(_meta_anns)  # type: ignore
                elif not meta_anns:
                    # allow empty
                    pass
                else:
                    raise ValueError(f"Unknown meta anns: {meta_anns}")
                for meta_ann in meta_anns:
                    meta_anns_dict.update(
                        {meta_ann['name']: meta_ann['value']})
                _anns = ann.copy()
                _anns.pop('meta_anns')  # type: ignore
            output: AnnotationOutput = {
                "project_name": proj_name,
                "document_name": doc_name
            }
            output.update(_anns)  # type: ignore
            output.update(meta_anns_dict)  # type: ignore
            ann_lst.append(output)
        return ann_lst

    def _load_mct_exports(self, list_of_paths_to_mct_exports: list[str]
                          ) -> _MedCATTrainerExport:
        """
        Loads a list of multiple MCT exports
        :param list_of_paths_to_mct_exports: list of mct exports
        :return: single json format object
        """
        mct_projects = []
        for mct_project in list_of_paths_to_mct_exports:
            with open(mct_project, 'r') as jsonfile:
                mct_projects.extend(json.load(jsonfile)['projects'])
        mct_proj_exports: _MedCATTrainerExport = {'projects': mct_projects}
        return mct_proj_exports

    def annotation_df(self) -> pd.DataFrame:
        """
        DataFrame of all annotations created
        :return: DataFrame
        """
        annotation_df = pd.DataFrame(self.annotations)
        if self.cat:
            annotation_df.insert(
                5, 'concept_name',
                annotation_df['cui'].map(
                    lambda cui: cast(CAT, self.cat).cdb.get_name(cui)))
        exceptions: list[ValueError] = []
        # try the default format as well as the format specified above
        for format in [None, DATETIME_FORMAT]:
            try:
                annotation_df['last_modified'] = pd.to_datetime(
                    annotation_df['last_modified'],
                    format=format).dt.tz_localize(None)
                exceptions.clear()
                break
            except ValueError as e:
                exceptions.append(e)
        if exceptions:
            # if there's issues
            raise ValueError(*exceptions)
        return annotation_df

    def concept_summary(self, extra_cui_filter: Optional[str] = None
                        ) -> pd.DataFrame:
        """
        Summary of only correctly annotated concepts from a mct export
        :return: DataFrame summary of annotations.
        """
        concept_output_raw = self.annotation_df()
        concept_output_pre = concept_output_raw[
            concept_output_raw['validated']]
        concept_output = concept_output_pre[
            (concept_output_pre['correct']) | (
                concept_output_pre['alternative'])]
        if self.cat:
            concept_count = concept_output.groupby(
                ['cui', 'concept_name']).agg({'value': set, 'id': 'count'})
        else:
            concept_count = concept_output.groupby(
                ['cui']).agg({'value': set, 'id': 'count'})
        concept_count_df = pd.DataFrame(concept_count).reset_index(drop=False)
        concept_count_df['variations'] = concept_count_df['value'].apply(
            lambda x: len(x))
        concept_count_df.rename({'id': 'concept_count'}, axis=1, inplace=True)
        concept_count_df = concept_count_df.sort_values(
            by='concept_count', ascending=False).reset_index(drop=True)
        concept_count_df['count_variations_ratio'] = round(
            concept_count_df['concept_count'] /
            concept_count_df['variations'], 3)
        if self.cat:
            fps, fns, tps, cui_prec, cui_rec, cui_f1, cui_counts, examples = (
                get_stats(self.cat, data=self.mct_export,  # type: ignore
                          use_project_filters=True,
                          # extra_cui_filter=extra_cui_filter
                          ))
            concept_count_df['fps'] = concept_count_df['cui'].map(fps)
            concept_count_df['fns'] = concept_count_df['cui'].map(fns)
            concept_count_df['tps'] = concept_count_df['cui'].map(tps)
            concept_count_df['cui_prec'] = concept_count_df[
                'cui'].map(cui_prec)
            concept_count_df['cui_rec'] = concept_count_df['cui'].map(cui_rec)
            concept_count_df['cui_f1'] = concept_count_df['cui'].map(cui_f1)
            # concept_count_df['cui_counts'] = # TODO check why cui counts is
            #                                    incorrect
            #    concept_count_df['cui'].map(cui_counts)
            examples_df = pd.DataFrame(
                examples).rename_axis('cui').reset_index(drop=False).\
                rename(columns={'fp': 'fp_examples',
                                'fn': 'fn_examples',
                                'tp': 'tp_examples'})
            concept_count_df = concept_count_df.merge(
                examples_df, how='left', on='cui')

        return concept_count_df

    def user_stats(self, by_user: bool = True) -> pd.DataFrame:
        """
        Summary of user annotation work done

        :param by_user: User Stats grouped by user rather than day
        :return: DataFrame of user annotation work done
        """
        df = self.annotation_df()[['user', 'last_modified']]
        data = df.groupby([df['last_modified'].dt.year.rename('year'),
                           df['last_modified'].dt.month.rename('month'),
                           df['last_modified'].dt.day.rename('day'),
                           df['user']]).agg({'count'})  # type: ignore
        data = pd.DataFrame(data)
        data.columns = data.columns.droplevel()
        data = data.reset_index(drop=False)
        data['date'] = pd.to_datetime(data[['year', 'month', 'day']])
        if by_user:
            data = data[['user', 'count']].groupby(by='user').agg(sum)
            data = data.reset_index(drop=False).sort_values(
                by='count', ascending=False).reset_index(drop=True)
            return data
        return data[['user', 'count', 'date']]

    def plot_user_stats(self, save_fig: bool = False,
                        save_fig_filename: str = ''):
        """
        Plot annotator user stats against time.
        An alternative method of saving the file is:
            plot_user_stats().write_image("path/filename.png")
        :param save_fig: Optional parameter to save the plot
        :param save_fig_filename: path/filename.html, default value is
            mct export projects names.
        :return: fig object
        """
        data = self.user_stats(by_user=False)
        total_annotations = data['count'].sum()
        fig = go.Figure()
        for user in data['user'].unique():
            fig.add_trace(
                go.Bar(x=data[data['user'] == user]['date'],
                       y=data[data['user'] == user]['count'], name=user),
            )
        fig.update_layout(title={'text': 'MedCATtrainer Annotator Progress - '
                                 f'Total annotations: {total_annotations}'},
                          legend_title_text='MedCAT Annotator',
                          barmode='stack')
        fig.update_xaxes(title_text='Date')
        fig.update_yaxes(title_text='Annotation Count')
        if save_fig:
            if save_fig_filename:
                filename = save_fig_filename
            else:
                filename = input("Please enter the export path/filename "
                                 "with no ext: ") + '.html'
            plotly.offline.plot(fig, filename=filename)
            print(f'The figure was saved at: {filename}')
        return fig

    def _rename_meta_ann_values(self, meta_anns: dict[str, MetaAnnotation],
                                name_replacement: str,
                                meta_ann_name: str,
                                meta_values: dict[str, str],
                                meta_ann_values2rename: dict[
                                    str, dict[str, str]]):
        if meta_anns[name_replacement]['name'] == meta_ann_name:
            for value in meta_values:
                if meta_anns[name_replacement]['value'] == value:
                    meta_anns[name_replacement]['value'] = (
                        meta_ann_values2rename[meta_ann_name][value])

    def _rename_meta_ann_for_name(
            self, meta_anns: dict[str, MetaAnnotation],
            name2replace: str,
            name_replacement: str,
            meta_ann_values2rename: dict[str, dict[str, str]]):
        meta_anns[name_replacement] = meta_anns.pop(name2replace)
        meta_anns[name_replacement]['name'] = name_replacement
        for meta_ann_name, meta_values in meta_ann_values2rename.items():
            self._rename_meta_ann_values(
                meta_anns, name_replacement, meta_ann_name, meta_values,
                meta_ann_values2rename)

    def _rename_meta_ann(
            self, meta_anns: dict[str, MetaAnnotation],
            meta_anns2rename: dict[str, str] = dict(),
            meta_ann_values2rename: dict[str, dict[str, str]] = dict()):
        for meta_name2replace in meta_anns2rename:
            try:
                self._rename_meta_ann_for_name(
                    meta_anns, meta_name2replace,
                    meta_anns2rename[meta_name2replace],
                    meta_ann_values2rename)
            except KeyError:
                pass

    def rename_meta_anns(
            self, meta_anns2rename: dict[str, str] = dict(),
            meta_ann_values2rename: dict[str, dict[str, str]] = dict()):
        """Rename the names and/or values of meta annotations.

        :param meta_anns2rename: Example input:
            `{'Subject/Experiencer': 'Subject'}`
        :param meta_ann_values2rename: Example input:
            `{'Subject':{'Relative':'Other'}}`
        :return:
        """
        # if we want to rename the values, but haven't specified any names
        # to rename we need to use a names dict to map the names to themselves
        # due to the way the current implementation works
        if meta_ann_values2rename and not meta_anns2rename:
            meta_anns2rename = dict((name, name) for name in
                                    meta_ann_values2rename)
        for _, _, ann in self._iter_anns(False, False):
            if 'meta_anns' in ann:
                _meta_anns = ann['meta_anns']  # type: ignore
                meta_anns: dict[str, MetaAnnotation]
                if isinstance(_meta_anns, list):
                    meta_anns = {ma['name']: ma
                                 for ma in _meta_anns}
                else:
                    meta_anns = _meta_anns
                if len(meta_anns) > 0:
                    self._rename_meta_ann(
                        meta_anns, meta_anns2rename, meta_ann_values2rename)
        self.annotations = self._annotations()
        return

    @contextmanager
    def _capture_intermediate_data(self):
        # NOTE: The way ml_utils.eval_model works is that
        #       it does in fact produce the exact data that
        #       we need, however it passes it to _eval_predictions
        #       and subsequently processes it into a format that
        #       is not as useful for the eval problem we're trying
        #       to solve here
        from medcat.components.addons.meta_cat import ml_utils
        captured = []
        original = ml_utils._eval_predictions

        def wrapper(*args, **kwargs):
            if len(args) >= 3:
                captured.append(args[2])
            else:
                captured.append(kwargs["predictions"])
            return original(*args, **kwargs)

        ml_utils._eval_predictions = wrapper  # type: ignore
        try:
            yield captured
        finally:
            ml_utils._eval_predictions = original  # type: ignore

    def _eval(self,
              metacat_model: MetaCAT,
              mct_export: _MedCATTrainerExport
              ) -> list[str]:
        # Run evaluation
        assert metacat_model.tokenizer is not None
        # save entire thing on disk for full path
        with tempfile.NamedTemporaryFile(suffix=".json",
                                         delete=False) as f:
            with open(f.name, "w") as fw:
                json.dump(mct_export, fw)
            f.flush()
            # NOTE: doing this to capture intermediate results being passed
            #       to the _eval_predictions method
            with self._capture_intermediate_data() as captured:
                metacat_model.eval(f.name)
        # NOTE: the return list is amended after yield
        return captured[0]

    def full_annotation_df(self) -> pd.DataFrame:
        """
        DataFrame of all annotations created including meta_annotation
            predictions.
        This function is similar to annotation_df with the addition of
            Meta_annotation predictions from the medcat model.
        prerequisite Args: MedcatTrainer_export([mct_export_paths],
            model_pack_path=<path to medcat model>)
        :return: DataFrame
        """
        # mostly for typing so mypu knows it's not None down below
        if not self.cat or not self.model_pack_path:
            raise ValueError("No model pack specified")
        anns_df = self.annotation_df()

        meta_df = anns_df

        for meta_model in self.cat.get_addons_of_type(MetaCATAddon):
            meta_cat = meta_model.mc
            meta_model_cat = meta_cat.config.general.category_name
            meta_results = self._eval(meta_cat, self.mct_export)
            pred_meta_values = meta_results

            loc = meta_df.columns.get_loc(meta_model_cat)
            if isinstance(loc, int):
                meta_df.insert(
                    loc + 1, f'predict_{meta_model_cat}', pred_meta_values)
            else:
                print(f"Warning: Unexpected column location type: {type(loc)}")
                meta_df.insert(
                    1, f'predict_{meta_model_cat}', pred_meta_values)
        meta_df = meta_df[
            (anns_df['validated']) & (~anns_df['deleted']) &
            (~anns_df['killed']) & (~anns_df['irrelevant'])]
        meta_df.reset_index(drop=True, inplace=True)

        return meta_df

    def meta_anns_concept_summary(self) -> pd.DataFrame:
        if not self.cat:
            raise ValueError("No model pack specified")
        meta_df = self.full_annotation_df()
        meta_performance = {}
        for cui in meta_df.cui.unique():
            temp_meta_df = meta_df[meta_df['cui'] == cui]
            meta_task_results = {}
            for meta_task_info in self.cat.get_model_card(
                    as_dict=True)['MetaCAT models']:
                meta_task = meta_task_info['Category Name']
                list_meta_anns = list(zip(
                    temp_meta_df[meta_task],
                    temp_meta_df['predict_' + meta_task]))
                counter_meta_anns = Counter(list_meta_anns)
                meta_value_results: dict[tuple[str, str, str],
                                         Union[int, float]] = {}
                # TODO: maybe make this easier?
                meta_cats: list[MetaCATAddon] = [
                    addon for addon in
                    self.cat._pipeline.iter_addons()
                    if (isinstance(addon, MetaCATAddon) and
                        addon.config.comp_name == meta_task)
                ]
                if len(meta_cats) != 1:
                    raise ValueError(
                        f"Unable to uniquely identify meta task {meta_task}. "
                        f"Found {len(meta_cats)} options")
                meta_cat = meta_cats[0]
                for meta_value in (
                        meta_cat.config.general.category_value2id.keys()):
                    total = 0
                    fp = 0
                    fn = 0
                    tp = 0
                    for meta_value_result, count in counter_meta_anns.items():
                        if meta_value_result[0] == meta_value:
                            if meta_value_result[1] == meta_value:
                                tp += count
                                total += count
                            else:
                                fn += count
                                total += count
                        elif meta_value_result[1] == meta_value:
                            fp += count
                        else:
                            pass  # Skips nan values
                    meta_value_results[
                        (meta_task, meta_value, 'total')] = total
                    meta_value_results[(meta_task, meta_value, 'fps')] = fp
                    meta_value_results[(meta_task, meta_value, 'fns')] = fn
                    meta_value_results[(meta_task, meta_value, 'tps')] = tp
                    try:
                        meta_value_results[(meta_task, meta_value, 'f-score')
                                           ] = tp / (tp + (1 / 2) * (fp + fn))
                    except ZeroDivisionError:
                        meta_value_results[(meta_task, meta_value, 'f-score')
                                           ] = 0
                meta_task_results.update(meta_value_results)
            meta_performance[cui] = meta_task_results

        meta_anns_df = pd.DataFrame.from_dict(meta_performance, orient='index')
        col_lst = []
        for col in meta_anns_df.columns:
            if col[2] == 'total':
                col_lst.append(col)
        meta_anns_df['total_anns'] = meta_anns_df[col_lst].sum(axis=1)
        meta_anns_df = meta_anns_df.sort_values(
            by='total_anns', ascending=False)
        meta_anns_df = meta_anns_df.rename_axis('cui').reset_index(drop=False)
        meta_anns_df.insert(1, 'concept_name', meta_anns_df['cui'].map(
            lambda cui: cast(CAT, self.cat).cdb.get_name(cui)))
        return meta_anns_df

    def generate_report(self, path: str = 'mct_report.xlsx',
                        meta_ann: bool = False,
                        concept_filter: Optional[list] = None):
        """
        :param path: Outfile path
        :param meta_ann: Include Meta_annotation evaluation in the summary
            as well
        :param concept_filter: Filter the report to only display select
            concepts of interest. List of cuis.
        :return: A full excel report for MedCATtrainer annotation work done.
        """
        if not self.cat:
            raise ValueError("No model pack specified")
        if concept_filter:
            with pd.ExcelWriter(path) as writer:
                print('Generating report...')
                # array-like is allowed by documentation but not by typing
                df = pd.DataFrame.from_dict([self.cat.get_model_card(
                    as_dict=True)]).T.reset_index(drop=False)  # type: ignore
                df.columns = [  # type: ignore
                    'MCT report',
                    f'Generated on {date.today().strftime("%Y/%m/%d")}']
                df = pd.concat(
                    [df, pd.DataFrame([['MCT Custom filter', concept_filter]],
                                      columns=df.columns)],
                    ignore_index=True)
                df.to_excel(
                    writer, index=False, sheet_name='medcat_model_card')
                self.user_stats().to_excel(
                    writer, index=False, sheet_name='user_stats')
                print('Evaluating annotations...')
                if meta_ann:
                    ann_df = self.full_annotation_df()
                    ann_df = ann_df[ann_df['cui'].isin(concept_filter)
                                    ].reset_index(drop=True)
                    # Remove timezone information
                    ann_df['timestamp'] = ann_df[
                        'timestamp'].dt.tz_localize(None)
                    ann_df.to_excel(
                        writer, index=False, sheet_name='annotations')
                else:
                    ann_df = self.annotation_df()
                    ann_df = ann_df[ann_df['cui'].isin(concept_filter)
                                    ].reset_index(drop=True)
                    # Remove timezone information
                    ann_df['timestamp'] = ann_df[
                        'timestamp'].dt.tz_localize(None)
                    ann_df.to_excel(writer, index=False,
                                    sheet_name='annotations')
                performance_summary_df = self.concept_summary()
                performance_summary_df = performance_summary_df[
                    performance_summary_df['cui'].isin(concept_filter)
                    ].reset_index(drop=True)
                performance_summary_df.to_excel(
                    writer, index=False, sheet_name='concept_summary')
                if meta_ann:
                    print('Evaluating meta_annotations...')
                    meta_anns_df = self.meta_anns_concept_summary()
                    meta_anns_df = meta_anns_df[meta_anns_df['cui'].isin(
                        concept_filter)].reset_index(drop=True)
                    meta_anns_df.to_excel(
                        writer, index=True,
                        sheet_name='meta_annotations_summary')
        else:
            with pd.ExcelWriter(path) as writer:
                print('Generating report...')
                df = pd.DataFrame.from_dict(
                    [self.cat.get_model_card(as_dict=True)]
                    ).T.reset_index(drop=False)  # type: ignore
                df.columns = [  # type: ignore
                    'MCT report',
                    f'Generated on {date.today().strftime("%Y/%m/%d")}']
                df.to_excel(
                    writer, index=False, sheet_name='medcat_model_card')
                self.user_stats().to_excel(
                    writer, index=False, sheet_name='user_stats')
                print('Evaluating annotations...')
                if meta_ann:
                    self.full_annotation_df().to_excel(
                        writer, index=False, sheet_name='annotations')
                else:
                    self.annotation_df().to_excel(
                        writer, index=False, sheet_name='annotations')
                self.concept_summary().to_excel(
                    writer, index=False, sheet_name='concept_summary')
                if meta_ann:
                    print('Evaluating meta_annotations...')
                    self.meta_anns_concept_summary().to_excel(
                        writer, index=True,
                        sheet_name='meta_annotations_summary')

        return print(f"MCT report saved to: {path}")
