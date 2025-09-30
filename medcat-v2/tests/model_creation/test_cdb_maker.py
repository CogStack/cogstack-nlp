import unittest
import logging
import os
import numpy as np
import pandas as pd
from medcat.model_creation.cdb_maker import CDBMaker
from medcat.cdb import CDB
from medcat.config import Config
from medcat.preprocessors.cleaners import prepare_name


RESOURCES_PATH = os.path.join(
     os.path.dirname(__file__), "..", "resources"
)
MODEL_CREATION_RES_PATH = os.path.join(RESOURCES_PATH, "model_creation")


class CDBMakerBaseTests(unittest.TestCase):
    use_spacy = False

    @classmethod
    def setUpClass(cls):
        cls.config = Config()
        cls.config.general.log_level = logging.DEBUG
        if cls.use_spacy:
            cls.config.general.nlp.provider = 'spacy'
            cls.config.general.nlp.modelname = "en_core_web_md"
        cls.maker = CDBMaker(cls.config)
        csvs = [
            os.path.join(MODEL_CREATION_RES_PATH, 'cdb.csv'),
            os.path.join(MODEL_CREATION_RES_PATH, 'cdb_2.csv'),
        ]
        cls.cdb = cls.maker.prepare_csvs(csvs, full_build=True)


class MakeWithDashes(CDBMakerBaseTests):
    cui = '69482004'
    namelist = ["Korsakoff's psychosis",
                'Wernicke-Korsakoff syndrome',
                'Korsakov syndrome - alcoholic']
    expected_names = [
        # NOTE: whitespace and punctuation (e.g spaces, dashes)
        #       are replaced with separator (~) here
        #       and names are lower case
        #       notably, only 1 separator at a time is shown
        "korsakoff~s~psychosis",
        "wernicke~korsakoff~syndrome",
        "korsakov~syndrome~alcoholic",
    ]
    cui_df = pd.DataFrame({'cui': cui, 'name': namelist})

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.maker.prepare_csvs([cls.cui_df, ], full_build=True)

    def test_has_cui(self):
        self.assertIn(self.cui, self.cdb.cui2info)

    def test_has_full_names(self):
        for name in self.expected_names:
            with self.subTest(f"Name: {name}"):
                self.assertIn(name, self.cdb.name2info.keys())


class MakeWithDashesSpacy(MakeWithDashes):
    use_spacy = True


class CDBMakerLoadTests(CDBMakerBaseTests):
    EXPECTED_NAMES = {
        'C0000039': {'virus~k', 'virus', 'virus~m', 'virus~z'},
        'C0000139': {'virus~k', 'virus', 'virus~m', 'virus~z'},
        'C0000239': {'second~csv'}
    }
    EXPECTED_CUIS = set(EXPECTED_NAMES.keys())
    EXPECTED_SNAMES = {
        'C0000039': {'virus~k', 'virus', 'virus~m', 'virus~z'},
        'C0000139': {'virus~k', 'virus', 'virus~m', 'virus~z'},
        'C0000239': {'second', 'second~csv'}
    }
    EXPECTED_NAME2CUIS = {
            'virus': {'C0000039', 'C0000139'},
            'virus~m': {'C0000039', 'C0000139'},
            'virus~k': {'C0000039', 'C0000139'},
            'virus~z': {'C0000039', 'C0000139'},
            'second~csv': {'C0000239'},
        }
    EXPECTED_TAGS = {}
    EXPECTED_PREFNAMES = {
        'C0000039': 'Virus', 'C0000139': 'Virus Z'}
    EXPECTED_CONTEXT_VECTORS = {}
    EXPECTED_COUNT_TRAIN = {}
    # NOTE:
    # since we now use a defaultdict, the defualt value (A)
    # is not expected
    EXP_NAME2CUIS2STATUS = {
        'virus': {
            'C0000039': 'P',
            'C0000139': 'A'
        },
        'virus~m': {
            'C0000039': 'A',
            'C0000139': 'P'
        },
        'virus~k': {
            'C0000039': 'A',
            'C0000139': 'P'
        },
        'virus~z': {
            'C0000039': 'A',
            'C0000139': 'P'
        },
        'second~csv': {
            'C0000239': 'A'
        }
    }
    EXPECTED_TYPE_IDS = {
        'C0000039': {'T234', 'T109', 'T123'},
        'C0000139': set(),
        'C0000239': set()
    }
    EXPECTED_ADDL_INFO = {
        'cui2icd10': {},
        'cui2opcs4': {},
        'cui2ontologies': {
            'C0000039': {'MSH'}
        },
        'cui2original_names': {
            'C0000039': {'Virus K', 'Virus M', 'Virus', 'Virus Z'},
            'C0000139': {'Virus K', 'Virus M', 'Virus', 'Virus Z'},
            'C0000239': {'Second csv'}
        },
        'cui2description': {
            'C0000039': 'Synthetic phospholipid used in liposomes and lipid '
            'bilayers to study biological membranes. It is also a major '
            'constituent of PULMONARY SURFACTANTS.'
        },
        'type_id2name': {},
        'type_id2cuis': {
            'T109': {'C0000039'},
            'T123': {'C0000039'},
            'T234': {'C0000039'}
        },
        'cui2group': {}
    }

    # @classmethod
    # def tearDownClass(cls) -> None:
    #     cls.maker.destroy_pipe()

    def test_has_each_cui(self):
        self.assertEqual(set(self.cdb.cui2info.keys()), self.EXPECTED_CUIS)

    def test_cdb_names_correct(self):
        cui2names = {
             cui: info['names'] for cui, info in self.cdb.cui2info.items()}
        self.assertEqual(cui2names, self.EXPECTED_NAMES)

    def test_cdb_snames_correct(self):
        cui2snames = {
             cui: info['subnames'] for cui, info in self.cdb.cui2info.items()}
        self.assertEqual(cui2snames, self.EXPECTED_SNAMES)

    def test_cdb_name_to_cuis_correct(self):
        name2cuis = {
             name: info['per_cui_status'].keys()
             for name, info in self.cdb.name2info.items()}
        self.assertEqual(name2cuis, self.EXPECTED_NAME2CUIS)

    def test_cdb_cuis_has_no_tags(self):
        cui2tags = {cui: info['tags']
                    for cui, info in self.cdb.cui2info.items()
                    if info['tags']}
        self.assertEqual(cui2tags, self.EXPECTED_TAGS)

    def test_cdb_cui_to_preferred_name_correct(self):
        cui2preferred_name = {
             cui: info['preferred_name']
             for cui, info in self.cdb.cui2info.items()
             if info['preferred_name']
        }
        self.assertEqual(cui2preferred_name, self.EXPECTED_PREFNAMES)

    def test_cdb_cui_to_context_vectors_correct(self):
        cui2context_vectors = {
             cui: info['context_vectors']
             for cui, info in self.cdb.cui2info.items()
             if info['context_vectors'] is not None
        }
        self.assertEqual(cui2context_vectors, self.EXPECTED_CONTEXT_VECTORS)

    def test_cdb_cui_to_count_train_output(self):
        cui2count_train = {
             cui: info['count_train']
             for cui, info in self.cdb.cui2info.items()
             if info['count_train'] > 0}
        self.assertEqual(cui2count_train, self.EXPECTED_COUNT_TRAIN)

    def test_cdb_name_to_cui_to_status_output(self):
        name2cuis2status = {
             name: dict(**info['per_cui_status'])
             for name, info in self.cdb.name2info.items()
             if info['per_cui_status']
        }
        self.maxDiff = None
        self.assertEqual(name2cuis2status, self.EXP_NAME2CUIS2STATUS)

    def test_cdb_cui_to_type_ids_output(self):
        cui2type_ids = {
             cui: info['type_ids'] for cui, info in self.cdb.cui2info.items()
        }
        self.assertEqual(cui2type_ids, self.EXPECTED_TYPE_IDS)

    # def test_cdb_additional_info_output(self):
    #     self.assertEqual(self.cdb.addl_info, self.EXPECTED_ADDL_INFO)


class CDBMakerEditTestsBase(CDBMakerBaseTests):

    @classmethod
    def pn_cnf_parts(cls):
        return (cls.config.general, cls.config.preprocessing,
                cls.config.cdb_maker)

    # @classmethod
    # def tearDownClass(cls) -> None:
    #     cls.maker.destroy_pipe()


class CDBMakerNameAdditionTests(CDBMakerEditTestsBase):
    CONCEPT = 'C0000239'
    NAME_STATUS = 'p'
    # EXPECTATION
    # only the added one as extra
    NUM_EXPECTED_NAMES = len(CDBMakerLoadTests.EXP_NAME2CUIS2STATUS) + 1
    NAME2PREPARE = 'MY: new,-_! Name.'
    EXP_ORIG_NAMES = {'MY: new,-_! Name.', 'Second csv'}
    EXP_NAMES = {'my~:~new~name~.'}
    EXP_SUBNAMES = {'my~:~new'}

    @classmethod
    def add_name(cls, cdb: CDB):
        cdb.add_names(cui=cls.CONCEPT, names=prepare_name(
            cls.NAME2PREPARE, cls.maker.pipeline.tokenizer_with_tag, {},
            cls.pn_cnf_parts()), name_status=cls.NAME_STATUS, full_build=True)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.add_name(cls.cdb)
        cls.cdb._reset_subnames()

    def test_has_correct_num_of_names(self):
        self.assertEqual(len(self.cdb.name2info), self.NUM_EXPECTED_NAMES)

    # def test_has_correct_orig_names(self):
    #     self.assertEqual(
    #         self.cdb.addl_info['cui2original_names'][self.CONCEPT],
    #         self.EXP_ORIG_NAMES)

    def test_has_correct_names(self):
        for name in self.EXP_NAMES:
            with self.subTest(name):
                self.assertIn(name, self.cdb.name2info)

    def test_has_correct_subnames(self):
        for sname in self.EXP_SUBNAMES:
            with self.subTest(sname):
                self.assertIn(sname, self.cdb._subnames)


class CDBMakerNameRemovalTests(CDBMakerEditTestsBase):
    # NOTE: the number remains the same since it's first added, then removed
    EXP_NUM_NAME2CUIS2STATUS = len(CDBMakerLoadTests.EXP_NAME2CUIS2STATUS)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        CDBMakerNameAdditionTests.add_name(cls.cdb)
        cls.cdb._remove_names(cui=CDBMakerNameAdditionTests.CONCEPT,
                              names=prepare_name(
                                   CDBMakerNameAdditionTests.NAME2PREPARE,
                                   cls.maker.pipeline.tokenizer_with_tag,
                                   {}, cls.pn_cnf_parts()))
        cls.cdb._reset_subnames()

    def test_has_correct_number_of_names(self):
        self.assertEqual(len(self.cdb.name2info),
                         self.EXP_NUM_NAME2CUIS2STATUS)

    def test_does_not_have_new_name(self):
        for name in CDBMakerNameAdditionTests.EXP_NAMES:
            with self.subTest(name):
                self.assertNotIn(name, self.cdb.name2info)

    # def test_filter_by_cui(self):
    #     cuis_to_keep = {'C0000039'}
    #     self.cdb.filter_by_cui(cuis_to_keep=cuis_to_keep)
    #     self.assertEqual(len(self.cdb.cui2names), 2, "Should equal 2")
    #     self.assertEqual(len(self.cdb.name2cuis), 4, "Should equal 4")
    #     self.assertEqual(len(self.cdb.snames), 4, "Should equal 4")


from medcat.components.linking.vector_context_model import ( # noqa
    update_context_vectors, get_lr_linking)


class CDBMakerContextVectorsAdditionTests(CDBMakerEditTestsBase):
    CONCEPT = 'C0000139'
    EXP_CNT_TRAIN = 2
    VEC_DIM = 300
    SEED = 11

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        np.random.seed(cls.SEED)
        cuis = list(cls.cdb.cui2info.keys())
        cvs = cls.config.components.linking.context_vector_sizes
        for i in range(2):
            for cui in cuis:
                vectors = {}
                for cntx_type in cvs:
                    vectors[cntx_type] = np.random.rand(cls.VEC_DIM)
                cinfo = cls.cdb.cui2info[cui]
                to_update = cinfo['context_vectors']
                lr = get_lr_linking(cls.config.components.linking,
                                    cinfo['count_train'])
                if to_update:
                    update_context_vectors(
                        to_update, cui, vectors, lr, negative=False)
                else:
                    cinfo['context_vectors'] = vectors
        cls.cinfo = cls.cdb.cui2info[cls.CONCEPT]
        cls.cdb._reset_subnames()

    # def test_addition_gets_correct_count_train(self):
    #     self.assertEqual(self.cinfo.count_train, self.EXP_CNT_TRAIN)

    def test_has_correct_shape(self):
        self.assertEqual(self.cinfo['context_vectors']['long'].shape[0],
                         self.VEC_DIM)


class CDBMakerContextVectorsAdditionNegTests(CDBMakerEditTestsBase):
    CONCEPT = 'C0000139'
    EXP_CNT_TRAIN = 2
    VEC_DIM = 300
    SEED = 11

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        np.random.seed(11)
        cuis = list(cls.cdb.cui2info.keys())
        cvs = cls.config.components.linking.context_vector_sizes
        for i in range(2):
            for cui in cuis:
                vectors = {}
                for cntx_type in cvs:
                    vectors[cntx_type] = np.random.rand(cls.VEC_DIM)
                cinfo = cls.cdb.cui2info[cui]
                to_update = cinfo['context_vectors']
                lr = get_lr_linking(cls.config.components.linking,
                                    cinfo['count_train'])
                if to_update:
                    update_context_vectors(to_update, cui, vectors, lr,
                                           negative=True)
                else:
                    cinfo['context_vectors'] = vectors
        cls.cinfo = cls.cdb.cui2info[cls.CONCEPT]
        cls.cdb._reset_subnames()

    # def test_epected_count_train(self):
    #     self.assertEqual(self.cinfo.count_train, self.EXP_CNT_TRAIN)

    def test_expected_vec_dim(self):
        vec = self.cinfo['context_vectors']['long']
        self.assertEqual(vec.shape[0], self.VEC_DIM)


# # TODO CDB import training?
