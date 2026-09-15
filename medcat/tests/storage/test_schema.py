import os

from medcat.storage import schema as mct_schema

import unittest
import tempfile


class MyDummyTestClass:
    pass


class SchemaTests(unittest.TestCase):
    SCHEMA_FILE_BASENAME = ".schema.json"
    SAMPLE_SCHEMA = {
        "attr1": "file1.dat",
        "attr2": "file2.dat",
        "attr3": "file2.dat",
    }

    def setUp(self):
        self._temp_folder = tempfile.TemporaryDirectory()
        self.schema_save_file = os.path.join(self._temp_folder.name,
                                             self.SCHEMA_FILE_BASENAME)

    def tearDown(self):
        self._temp_folder.cleanup()

    def _save_default_schema(self):
        mct_schema.save_schema(self.schema_save_file, MyDummyTestClass,
                               self.SAMPLE_SCHEMA)

    def _load_default_schema(self):
        return mct_schema.load_schema(self.schema_save_file)

    def test_can_save(self):
        self._save_default_schema()
        self.assertTrue(os.path.exists(self.schema_save_file))

    def test_loads_correct_cls(self):
        self._save_default_schema()
        cls_path, _ = self._load_default_schema()
        self.assertEqual(cls_path, mct_schema._cls2path(MyDummyTestClass))

    def test_loads_correct_schema(self):
        self._save_default_schema()
        _, schema = self._load_default_schema()
        self.assertEqual(schema, self.SAMPLE_SCHEMA)
