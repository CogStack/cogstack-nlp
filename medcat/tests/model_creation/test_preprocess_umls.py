import os
import tempfile
import unittest

from medcat.config import Config
from medcat.model_creation.cdb_maker import CDBMaker
from medcat.model_creation.preprocess_umls import UMLS


# Synthetic MRCONSO rows for one concept:
# CUI|LAT|TS|LUI|STT|SUI|ISPREF|AUI|SAUI|SCUI|SDUI|SAB|TTY|CODE|STR|SRL|SUPPRESS|CVF|
MRCONSO_ROWS = [
    # the preferred name (TS=P, STT=PF, ISPREF=Y)
    "C9000001|ENG|P|L9000001|PF|S9000001|Y|A9000001||||SRC_A|PT|X1|"
    "Example disease|0|N||",
    # the same string from a second source (ISPREF=N)
    "C9000001|ENG|P|L9000001|PF|S9000001|N|A9000002||||SRC_B|PT|Y1|"
    "Example disease|0|N||",
    # synonyms, one with ISPREF=N
    "C9000001|ENG|S|L9000002|PF|S9000002|N|A9000003||||SRC_B|SY|Y1|"
    "Example illness|0|N||",
    "C9000001|ENG|S|L9000003|PF|S9000003|Y|A9000004||||SRC_A|SY|X1|"
    "Disease of example|0|N||",
]
MRSTY_ROWS = [
    "C9000001|T047|B2.2.1.2.1|Disease or Syndrome|AT0000001||",
]


class UMLSConceptDfNameStatusTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        conso_file = os.path.join(cls.temp_dir.name, "MRCONSO.RRF")
        sty_file = os.path.join(cls.temp_dir.name, "MRSTY.RRF")
        with open(conso_file, "w", encoding="utf-8") as f:
            f.write("\n".join(MRCONSO_ROWS) + "\n")
        with open(sty_file, "w", encoding="utf-8") as f:
            f.write("\n".join(MRSTY_ROWS) + "\n")
        cls.df = UMLS(conso_file, sty_file).to_concept_df()

    @classmethod
    def tearDownClass(cls):
        cls.temp_dir.cleanup()

    def test_only_preferred_name_has_status_p(self):
        self.assertEqual(list(self.df["name_status"]), ["P", "A", "A", "A"])

    def test_cdb_has_preferred_name_and_no_must_disambiguate_names(self):
        cdb = CDBMaker(Config()).prepare_csvs([self.df])
        statuses = {
            name: cdb.name2info[name]["per_cui_status"]["C9000001"]
            for name in cdb.cui2info["C9000001"]["names"]
        }
        self.assertEqual(statuses, {
            "example~disease": "P",
            "example~illness": "A",
            "disease~of~example": "A",
        })
        self.assertEqual(
            cdb.cui2info["C9000001"]["preferred_name"], "Example disease")
