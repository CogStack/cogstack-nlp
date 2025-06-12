from typing import Optional, cast
import numpy as np

from medcat.cdb import CDB
from medcat.data.mctexport import (MedCATTrainerExport,
                                   MedCATTrainerExportProject,
                                   MedCATTrainerExportDocument)
from medcat.tokenizing.tokens import MutableDocument, MutableEntity


class TestTrainSplitter:
    MAX_TEST_FRACTION = 0.3
    MIN_CNT_FOR_TEST = 10

    def __init__(self, data: MedCATTrainerExport, cdb: CDB,
                 test_size: float = 0.2):
        self.data = data
        self.cdb = cdb
        self.test_size = test_size
        self._reset()

    def _reset(self) -> None:
        self.cnts: dict[str, int] = {}
        self.test_cnts: dict[str, int] = {}
        self.total_anns = 0
        self.test_anns = 0
        self.test_prob = 0.90

    def _count_project(self, project: MedCATTrainerExportProject) -> None:
        cui_filter = None

        if 'cuis' in project and len(project['cuis'].strip()) > 0:
            cui_filter = [x.strip() for x in project['cuis'].split(",")]

        for ann in (ann for doc in project['documents']
                    for ann in doc['annotations']):
            if cui_filter is not None and ann['cui'] not in cui_filter:
                continue
            if ann['cui'] in self.cnts:
                self.cnts[ann['cui']] += 1
            else:
                self.cnts[ann['cui']] = 1

            self.total_anns += 1

    def split(self) -> tuple[MedCATTrainerExport, MedCATTrainerExport,
                             int, int]:
        # Count all CUIs
        for project in self.data['projects']:
            self._count_project(project)

        test_set: MedCATTrainerExport = {'projects': []}
        train_set: MedCATTrainerExport = {'projects': []}

        perm_arr: list[int] = cast(
            list[int],
            np.random.permutation(range(
                len(self.data['projects']))).tolist())

        for i_project in perm_arr:
            project = self.data['projects'][i_project]
            cui_filter = None

            # copy everything else, but reset documents list
            test_project: MedCATTrainerExportProject = project.copy()
            train_project: MedCATTrainerExportProject = project.copy()
            test_project['documents'] = []
            train_project['documents'] = []

            if 'cuis' in project and len(project['cuis'].strip()) > 0:
                cui_filter = [x.strip() for x in project['cuis'].split(",")]

            num_of_docs = len(project['documents'])
            for i_document in np.random.permutation(range(0, num_of_docs)):
                # Do we have enough documents in the test set
                if self.test_anns / self.total_anns >= self.test_size:
                    continue
                document = project['documents'][i_document]
                self._split_doc_train_test(document, cui_filter,
                                           train_project, test_project)

            test_set['projects'].append(test_project)
            train_set['projects'].append(train_project)

        return train_set, test_set, self.test_anns, self.total_anns

    def _split_doc_train_test(self, document: MedCATTrainerExportDocument,
                              cui_filter: Optional[list[str]],
                              train_project: MedCATTrainerExportProject,
                              test_project: MedCATTrainerExportProject):
        # Count CUIs for this document
        _cnts: dict[str, int] = {}
        doc_annotations = document['annotations']

        for ann in doc_annotations:
            if (cui_filter is not None and ann['cui'] not in cui_filter):
                continue
            if ann['cui'] in _cnts:
                _cnts[ann['cui']] += 1
            else:
                _cnts[ann['cui']] = 1

        is_test = self._should_add_to_test(_cnts)

        # Add to test set
        if is_test and np.random.rand() < self.test_prob:
            test_project['documents'].append(document)
            doc_annotations = document['annotations']

            for ann in doc_annotations:
                if cui_filter is not None and ann['cui'] not in cui_filter:
                    continue
                self.test_anns += 1
                if ann['cui'] in self.test_cnts:
                    self.test_cnts[ann['cui']] += 1
                else:
                    self.test_cnts[ann['cui']] = 1
        else:
            train_project['documents'].append(document)

    def _should_add_to_test(self, _cnts: dict[str, int]) -> bool:
        # Did we get more than 30% of concepts for any CUI with >=10 cnt
        return any(
            self.cnts[cui] >= self.MIN_CNT_FOR_TEST and
            (v + self.test_cnts.get(cui, 0)
             ) / self.cnts[cui] < self.MAX_TEST_FRACTION
            for cui, v in _cnts.items()
        )


def make_mc_train_test(data: MedCATTrainerExport,
                       cdb: CDB, test_size: float = 0.2) -> tuple:
    """Make train set.

    This is a disaster.

    Args:
        data (MedCATTrainerExport): The data.
        cdb (CDB): The concept database.
        test_size (float): The test size. Defaults to 0.2.

    Returns:
        tuple:
            The train set, the test set, the test annotations,
            and the total annotations
    """
    return TestTrainSplitter(data, cdb, test_size).split()


def get_false_positives(doc: MedCATTrainerExportDocument,
                        spacy_doc: MutableDocument
                        ) -> list[MutableEntity]:
    """Get the false positives within a trainer export.

    Args:
        doc (MedCATTrainerExportDocument): The trainer export.
        spacy_doc (MutableDocument): The annotated document.

    Returns:
        list[MutableEntity]: The list of false positive entities.
    """
    truth = set([(ent['start'], ent['cui']) for ent in doc['annotations']])

    fps = []
    for ent in spacy_doc.ner_ents:
        if (ent.base.start_index, ent.cui) not in truth:
            fps.append(ent)

    return fps
