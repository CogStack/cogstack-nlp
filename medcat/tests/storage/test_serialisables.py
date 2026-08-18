from dataclasses import dataclass

from medcat.storage import serialisables

import unittest


@dataclass
class MyDummyTestClass1:
    attr1: serialisables.Serialisable
    attr2: serialisables.Serialisable
    attr3: int
    attr4: str

    def get_strategy(self) -> serialisables.SerialisingStrategy:
        return serialisables.SerialisingStrategy.SERIALISABLES_AND_DICT

    @classmethod
    def get_init_attrs(self) -> list[str]:
        return ['']

    @classmethod
    def ignore_attrs(self) -> list[str]:
        return ['']

    @classmethod
    def include_properties(cls) -> list[str]:
        return []

    @classmethod
    def get_def_correct_inst(cls) -> tuple['MyDummyTestClass1', set[str]]:
        return cls(
            attr1=serialisables.AbstractSerialisable(),
            attr2=serialisables.AbstractSerialisable(),
            attr3=-1, attr4='string',
        ), {'attr1', 'attr2'}

    @classmethod
    def get_def_incorrect_inst(cls) -> tuple['MyDummyTestClass1', set[str]]:
        return cls(
            attr1=serialisables.AbstractSerialisable(),
            attr2=10,
            attr3=serialisables.AbstractSerialisable(),
            attr4='string',
        ), {"attr1", 'attr3'}


class SerialisableTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        (cls.correct_inst,
         cls.names4correct) = MyDummyTestClass1.get_def_correct_inst()
        (cls.incorrect_inst,
         cls.names4incorrect) = MyDummyTestClass1.get_def_incorrect_inst()

    def assert_correct_number_of_members(
            self,
            members: list[tuple[serialisables.Serialisable, str]],
            exp_names: set[str]):
        if len(members) != len(exp_names):
            raise AssertionError(
                "Found and unexpected number of members. "
                f"Expected {len(exp_names)}, got {len(members)}")

    def assert_captured_correct_members(
            self,
            members: list[tuple[serialisables.Serialisable, str]],
            exp_names: set[str]):
        all_found_names = set(found_name for _, found_name in members)
        for name in exp_names:
            if name not in all_found_names:
                raise AssertionError(f"{name} was found (but not expected)")

    def assert_did_not_capture_incorrect_members(
            self,
            members: list[tuple[serialisables.Serialisable, str]],
            exp_names: set[str]):
        for _, name in members:
            if name not in exp_names:
                raise AssertionError(f"{name} not found (but expected)")

    def assert_correctly_captured(
            self,
            members: list[tuple[serialisables.Serialisable, str]],
            exp_names: set[str]):
        self.assert_correct_number_of_members(members, exp_names)
        self.assert_captured_correct_members(members, exp_names)
        self.assert_did_not_capture_incorrect_members(members, exp_names)

    def test_finds_all_serialisable_members_correct(self):
        members, _ = serialisables.get_all_serialisable_members(
            self.correct_inst)
        self.assert_correctly_captured(members, self.names4correct)

    def test_finds_all_serialisable_members_incorrect(self):
        members, _ = serialisables.get_all_serialisable_members(
            self.incorrect_inst)
        self.assert_correctly_captured(members, self.names4incorrect)
