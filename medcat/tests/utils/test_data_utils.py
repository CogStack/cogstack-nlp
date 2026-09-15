import unittest
import numpy as np

from medcat.utils.data_utils import TestTrainSplitter, make_mc_train_test
from medcat.data.mctexport import MedCATTrainerExport


class _FakeCDB:
    """Minimal CDB stub - TestTrainSplitter does not access CDB directly."""
    pass


def _make_synthetic_export(n_docs: int,
                           n_projects: int = 1,
                           cui: str = "428763004",
                           anns_per_doc: int = 1) -> MedCATTrainerExport:
    """Create a synthetic MedCATTrainerExport with a single common CUI.

    Using a single CUI appearing in all documents replicates the real-world
    condition that triggers the bug: the test quota fills quickly because
    MAX_TEST_FRACTION (0.3) is reached after only a small number of documents,
    causing all remaining documents to be processed by the if-branch in split().
    """
    docs_per_project = n_docs // n_projects
    projects = []
    doc_id = 0

    for p_idx in range(n_projects):
        documents = []
        for d_idx in range(docs_per_project):
            documents.append({
                "id": doc_id,
                "name": f"note_{doc_id}",
                "last_modified": "N/A",
                "text": f"Patient has Staphylococcus aureus bacteraemia. Document {doc_id}.",
                "annotations": [
                    {
                        "cui": cui,
                        "value": "Staphylococcus aureus bacteraemia",
                        "start": 11,
                        "end": 44,
                    }
                    for _ in range(anns_per_doc)
                ]
            })
            doc_id += 1

        projects.append({
            "id": p_idx,
            "name": f"project_{p_idx}",
            "cuis": "",
            "documents": documents,
        })

    return {"projects": projects}


class TestTrainSplitterNoDocumentLossTests(unittest.TestCase):
    """Tests that TestTrainSplitter assigns all documents to train or test.

    Previously, when the test annotation quota was reached, documents were
    silently dropped via `continue` rather than being routed to the train set.
    This caused the majority of documents to be discarded from both sets.

    See: https://discourse.cogstack.org/t/testtrainsplitter-silently-drops-documents
    """

    N_DOCS = 50
    TEST_SIZE = 0.2
    RNG_SEED = 42

    @classmethod
    def setUpClass(cls):
        cls.cdb = _FakeCDB()
        cls.export = _make_synthetic_export(cls.N_DOCS)

    def setUp(self):
        np.random.seed(self.RNG_SEED)

    def _count_docs(self, dataset: MedCATTrainerExport) -> int:
        return sum(len(p['documents']) for p in dataset['projects'])

    def test_no_documents_lost_single_project(self):
        """All documents should be assigned to train or test — none dropped."""
        splitter = TestTrainSplitter(self.export, self.cdb,
                                     test_size=self.TEST_SIZE)
        train_set, test_set, _, _ = splitter.split()

        total = self._count_docs(self.export)
        train = self._count_docs(train_set)
        test  = self._count_docs(test_set)

        self.assertEqual(
            train + test, total,
            f"Documents lost: {total - train - test} "
            f"(train={train}, test={test}, total={total})"
        )

    def test_train_set_is_larger_than_test_set(self):
        """Train set should contain the majority of documents."""
        splitter = TestTrainSplitter(self.export, self.cdb,
                                     test_size=self.TEST_SIZE)
        train_set, test_set, _, _ = splitter.split()

        train = self._count_docs(train_set)
        test  = self._count_docs(test_set)

        self.assertGreater(train, test,
                           f"Expected train ({train}) > test ({test})")

    def test_test_set_is_not_empty(self):
        """Test set should contain at least one document."""
        splitter = TestTrainSplitter(self.export, self.cdb,
                                     test_size=self.TEST_SIZE)
        train_set, test_set, _, _ = splitter.split()

        test = self._count_docs(test_set)
        self.assertGreater(test, 0, "Test set should not be empty")

    def test_no_documents_lost_multi_project(self):
        """No documents lost when data spans multiple projects."""
        export = _make_synthetic_export(self.N_DOCS, n_projects=2)
        splitter = TestTrainSplitter(export, self.cdb,
                                     test_size=self.TEST_SIZE)
        train_set, test_set, _, _ = splitter.split()

        total = self._count_docs(export)
        train = self._count_docs(train_set)
        test  = self._count_docs(test_set)

        self.assertEqual(
            train + test, total,
            f"Documents lost across projects: {total - train - test} "
            f"(train={train}, test={test}, total={total})"
        )

    def test_make_mc_train_test_no_documents_lost(self):
        """make_mc_train_test wrapper should also lose no documents."""
        np.random.seed(self.RNG_SEED)
        train_set, test_set, _, _ = make_mc_train_test(
            self.export, self.cdb, test_size=self.TEST_SIZE
        )

        total = self._count_docs(self.export)
        train = self._count_docs(train_set)
        test  = self._count_docs(test_set)

        self.assertEqual(
            train + test, total,
            f"make_mc_train_test lost {total - train - test} documents"
        )


if __name__ == "__main__":
    unittest.main()