import unittest

from medcat2.cdb import concepts
from medcat2.utils.defaults import StatusTypes


class CUIInfoTests(unittest.TestCase):
    cui = 'CUI1'
    pref_name = 'PREF NAME'
    names = {"N1", "N2"}
    subnames = {"N1a", "N2b"}
    type_ids = {"T0"}

    @classmethod
    def setUpClass(cls) -> None:
        cls.info = concepts.get_new_cui_info(
            cui=cls.cui, preferred_name=cls.pref_name,
            names=cls.names, subnames=cls.subnames,
            type_ids=cls.type_ids)

    def setUp(self) -> None:
        self.info['count_train'] = 10
        self.info['average_confidence'] = 0.6
        self.info['context_vectors'] = {"F": concepts.np.array(2)}
        return super().setUp()

    def test_training_reset_works_cnt_train(self):
        concepts.reset_cui_training(self.info)
        self.assertEqual(self.info['count_train'], 0)

    def test_training_reset_works_average_confidence(self):
        concepts.reset_cui_training(self.info)
        self.assertEqual(self.info['average_confidence'], 0.0)

    def test_training_reset_works_context_vectors(self):
        concepts.reset_cui_training(self.info)
        self.assertIs(self.info['context_vectors'], None)


class NameInfoTests(unittest.TestCase):
    name = "N1"
    cuis = {"C1", "C2"}

    @classmethod
    def setUpClass(cls) -> None:
        cls.info = concepts.get_new_name_info(name=cls.name,
                                              per_cui_status={
                                                  cui: StatusTypes.AUTOMATIC
                                                  for cui in cls.cuis})

    def test_def_cuistatus_is_automatic(self):
        for cui in self.cuis:
            with self.subTest(cui):
                status = self.info['per_cui_status'][cui]
                self.assertEqual(status, StatusTypes.AUTOMATIC)
