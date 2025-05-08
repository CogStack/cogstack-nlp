from typing import Optional
import os
from datetime import datetime

from medcat2.storage.serialisables import (
    Serialisable, AbstractSerialisable, ManualSerialisable,
    AbstractManualSerialisable)
from medcat2.storage import serialisers
from medcat2.cat import CAT
from medcat2.cdb import CDB
from medcat2.vocab import Vocab
from medcat2.config import Config
from medcat2.preprocessors.cleaners import NameDescriptor

import numpy as np
import unittest
import tempfile


class DummyClassWithDefValues(AbstractSerialisable):

    def __init__(self,
                 attr1: Optional[Serialisable] = None,
                 attr2: Optional[int] = None,
                 attr3: Optional[datetime] = None,
                 attr4: Optional[Serialisable] = None,
                 ):
        super().__init__()
        self.attr1 = attr1
        self.attr2 = attr2
        self.attr3 = attr3
        self.attr4 = attr4

    @classmethod
    def get_default(cls) -> 'DummyClassWithDefValues':
        return cls(
            attr1=AbstractSerialisable(),
            attr2=-1,
            attr3=datetime.now(),
            attr4=AbstractSerialisable(),
        )

    def __str__(self):
        return (f"<attr1: {self.attr1}, attr2: {self.attr2}"
                f"attr3: {self.attr3}, attr4: {self.attr4}>")

    def __repr__(self):
        return f"{{{self}}}"

    def __eq__(self, other) -> bool:
        if not isinstance(other, DummyClassWithDefValues):
            return False
        # NOTE: only the serialisable bits can eb checked since
        #       the rest of it doesn't get loaded
        return (self.attr1 == other.attr1 and self.attr4 == other.attr4)


class DummyClassWithMissingDefValues(DummyClassWithDefValues):

    def __init__(self, attr5: bool,
                 attr1: Optional[Serialisable] = None,
                 attr2: Optional[int] = None,
                 attr3: Optional[str] = None,
                 attr4: Optional[Serialisable] = None):
        super().__init__(attr1, attr2, attr3, attr4)
        self.attr5 = attr5

    @classmethod
    def get_init_attrs(cls):
        return ['attr5']

    @classmethod
    def get_default(cls, extra: bool = True
                    ) -> 'DummyClassWithMissingDefValues':
        return cls(
            attr5=extra,
            attr1=AbstractSerialisable(),
            attr2=-1,
            attr3='some string',
            attr4=AbstractSerialisable(),
        )


class SerialiserWorksTests(unittest.TestCase):
    SERIALISER_TYPE = serialisers.AvailableSerialisers.dill
    SERIALISABLE_INSTANCE = DummyClassWithDefValues.get_default()
    TARGET_CLASS = DummyClassWithDefValues

    def setUp(self):
        self._temp_folder = tempfile.TemporaryDirectory()
        self.temp_folder = self._temp_folder.name
        serialisers.serialise(self.SERIALISER_TYPE,
                              self.SERIALISABLE_INSTANCE,
                              self.temp_folder)

    def deserialise(self):
        return serialisers.deserialise(self.temp_folder)

    def tearDown(self):
        self._temp_folder.cleanup()

    def assert_has_files_in_folder(self):
        self.assertTrue(os.listdir(self.temp_folder))

    def test_can_serialise_to_file(self):
        self.assert_has_files_in_folder()

    def test_can_deserialise_from_file(self):
        got = self.deserialise()
        self.assertIsInstance(got, self.TARGET_CLASS)

    def test_deserialised_instance_same(self):
        got = self.deserialise()
        self.assertEqual(got, self.SERIALISABLE_INSTANCE)

    def test_used_correct_ser(self):
        ser_file = os.path.join(self.temp_folder, serialisers.SER_TYPE_FILE)
        got = serialisers.AvailableSerialisers.from_file(ser_file)
        self.assertIs(got, self.SERIALISER_TYPE)


class SerialiserFailsTests(SerialiserWorksTests):
    SERIALISABLE_INSTANCE = DummyClassWithMissingDefValues.get_default()
    TARGET_CLASS = DummyClassWithMissingDefValues


class MyDummyConfig(AbstractSerialisable):

    def __init__(self, arg1: str = 'DEF ARG', arg2: int = -1):
        self.arg1 = arg1
        self.arg2 = arg2


class MyDummyParentSerialisableWithConfig(AbstractSerialisable):

    def __init__(self, config: MyDummyConfig,
                 smth_else: int = 10):
        self.config = config
        self.smth_else = smth_else

    @classmethod
    def get_init_attrs(cls):
        return ['config']

    @classmethod
    def get_default(cls) -> 'MyDummyParentSerialisableWithConfig':
        return cls(
            config=MyDummyConfig()
        )


class MyDummyParentSerialisableWithNestedSameInstance(AbstractSerialisable):

    def __init__(self, obj_w_config: MyDummyParentSerialisableWithConfig):
        self.obj_w_config = obj_w_config
        self.config = obj_w_config.config

    @classmethod
    def get_init_attrs(cls):
        return ['obj_w_config']

    @classmethod
    def ignore_attrs(cls):
        return ['config']

    @classmethod
    def get_default(cls) -> 'MyDummyParentSerialisableWithNestedSameInstance':
        return cls(
            obj_w_config=MyDummyParentSerialisableWithConfig.get_default()
        )


class NestedSameInstanceSerialisableTests(SerialiserWorksTests):
    SERIALISABLE_INSTANCE = (
        MyDummyParentSerialisableWithNestedSameInstance.get_default())
    TARGET_CLASS = MyDummyParentSerialisableWithNestedSameInstance

    def deserialise(self) -> MyDummyParentSerialisableWithNestedSameInstance:
        return super().deserialise()

    def test_has_same_config(self):
        got = self.deserialise()
        self.assertIs(got.config, got.obj_w_config.config)


class CanSerialiseCATSimple(SerialiserWorksTests):
    CONFIG = Config()
    CDB = CDB(CONFIG)
    VOCAB = Vocab()
    SERIALISABLE_INSTANCE = CAT(CDB, VOCAB, CONFIG)
    TARGET_CLASS = CAT


def get_slightly_complex_cat() -> CAT:
    cnf = Config()
    cdb = CDB(cnf)
    vocab = Vocab()
    # aff a few words to vocab
    vocab.add_word("Word#1", -1)
    vocab.add_word("Word#2", 10, np.arange(4))
    # add a concept to CDB
    cdb.add_names("CUI#1", {"CUI#1NAME": NameDescriptor(
        tokens=["CUI#1", "NAME"], snames=["CUI#1", "NAME"],
        raw_name="CUI#1NAME", is_upper=True)})
    cnf.meta.mark_saved_now()
    return CAT(cdb, vocab, cnf)


class CanSerialiseCATSlightlyComplex(SerialiserWorksTests):
    SERIALISABLE_INSTANCE = get_slightly_complex_cat()
    TARGET_CLASS = CAT


class DummyManualSerialisable(AbstractManualSerialisable):
    FN = "DUMMY_FILY"

    def __init__(self, payload: str):
        self.payload = payload

    @classmethod
    def fp(cls, folder_path: str) -> str:
        return os.path.join(folder_path, cls.FN)

    def serialise_to(self, folder_path: str) -> None:
        with open(self.fp(folder_path), 'w') as f:
            f.write(self.payload)

    @classmethod
    def deserialise_from(cls, folder_path: str) -> 'ManualSerialisable':
        with open(cls.fp(folder_path)) as f:
            payload = f.read()
        return cls(payload=payload)

    def __eq__(self, other):
        if not isinstance(other, DummyManualSerialisable):
            return False
        return self.payload == other.payload


class ManualSerialisableTests(unittest.TestCase):
    ser_type = serialisers.AvailableSerialisers.dill
    payload = "Some text..."

    def setUp(self):
        self.dummy = DummyManualSerialisable(payload=self.payload)

    def test_dummy_class_appropriate(self):
        self.assertIsInstance(self.dummy, ManualSerialisable)

    def test_dummy_file_can_save(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            serialisers.serialise(self.ser_type, self.dummy, temp_dir)

    def test_dummy_file_can_save_and_load(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            serialisers.serialise(self.ser_type, self.dummy, temp_dir)
            loaded = serialisers.deserialise(temp_dir)
        self.assertEqual(self.dummy, loaded)


class PartlyManuallySerialisableTests(unittest.TestCase):
    SER_TYPE = serialisers.AvailableSerialisers.dill
    PAYLOAD = "Some payload"
    OBJ = DummyClassWithDefValues(attr1=DummyManualSerialisable(PAYLOAD))

    def test_dummy_file_can_save(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            serialisers.serialise(self.SER_TYPE, self.OBJ, temp_dir)

    def test_dummy_file_can_save_and_load(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            serialisers.serialise(self.SER_TYPE, self.OBJ, temp_dir)
            loaded = serialisers.deserialise(temp_dir)
        self.assertEqual(self.OBJ, loaded)
        self.assertEqual(self.OBJ.attr1, loaded.attr1)
