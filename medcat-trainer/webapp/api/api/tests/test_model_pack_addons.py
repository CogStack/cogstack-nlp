"""Tests for registering model packs that include addons.

The Trainer loads all addons via ``CAT.load_addons`` and registers only
MetaCAT ones (as ``MetaCATModel`` rows). Other addon types (e.g. RelCAT)
must load without error but are skipped during registration. These tests
mock ``CAT.load_addons`` so they exercise that behaviour without
downloading or loading real models.

Scenarios covered:

- MetaCAT only — one ``MetaCATModel`` row is created.
- RelCAT only — registration succeeds; no ``MetaCATModel`` rows.
- MetaCAT and RelCAT — both addons load; only MetaCAT is registered.
- No addons — CDB and vocab load; no ``MetaCATModel`` rows.
- Multiple MetaCAT addons — each MetaCAT is registered separately.
"""

import os
import tempfile
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from django.core.files.base import ContentFile
from django.test import TestCase, override_settings

from medcat.components.addons.meta_cat.meta_cat import MetaCATAddon
from medcat.components.addons.relation_extraction.rel_cat import RelCATAddon

from ..models import ModelPack


def _make_meta_cat_addon(category_name="Status", model_name="bert"):
    addon = MagicMock(spec=MetaCATAddon)
    meta_cat = MagicMock()
    meta_cat.config.general.category_name = category_name
    meta_cat.config.model.model_name = model_name
    meta_cat.config.general.category_value2id = {"True": 0, "False": 1}
    addon.mc = meta_cat
    return addon


def _make_rel_cat_addon():
    return MagicMock(spec=RelCATAddon)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class ModelPackAddonRegistrationTests(TestCase):
    def _prepare_model_pack(self, name="addon-pack-test"):
        """Create a ModelPack with a fake unpacked dir (cdb dir + vocab file)."""
        model_pack = ModelPack(name=name)
        model_pack.model_pack.save(f"{name}.zip", ContentFile(b"fake"), save=False)
        unpacked = model_pack.model_pack.path[: -len(".zip")]
        os.makedirs(os.path.join(unpacked, "cdb"), exist_ok=True)
        with open(os.path.join(unpacked, "vocab"), "w", encoding="utf-8") as fh:
            fh.write("")
        return model_pack, unpacked

    @contextmanager
    def _register_model_pack(self, model_pack, addons):
        with patch("api.models.CAT.attempt_unpack"), \
                patch("api.models.CDB.load"), \
                patch("api.models.Vocab.load"), \
                patch("api.models.CAT.load_addons", return_value=addons) as load_addons:
            model_pack.save()
            yield load_addons

    def test_register_model_pack_with_meta_cat_only(self):
        model_pack, unpacked = self._prepare_model_pack(name="meta-cat-pack")
        comps = os.path.join(unpacked, "saved_components")
        meta_cat_path = os.path.join(comps, "addon_meta_cat.Status")
        addons = [(meta_cat_path, _make_meta_cat_addon())]

        with self._register_model_pack(model_pack, addons) as load_addons:
            load_addons.assert_called_once_with(unpacked)

        self.assertIsNotNone(model_pack.concept_db)
        self.assertIsNotNone(model_pack.vocab)
        self.assertEqual(model_pack.meta_cats.count(), 1)
        meta_cat_model = model_pack.meta_cats.get()
        self.assertEqual(meta_cat_model.name, "Status - bert")
        self.assertTrue(meta_cat_model.meta_cat_dir.endswith("addon_meta_cat.Status"))

    def test_register_model_pack_with_rel_cat_only(self):
        model_pack, unpacked = self._prepare_model_pack(name="rel-cat-pack")
        comps = os.path.join(unpacked, "saved_components")
        rel_cat_path = os.path.join(comps, "addon_rel_cat.rel_cat")
        addons = [(rel_cat_path, _make_rel_cat_addon())]

        with self._register_model_pack(model_pack, addons) as load_addons:
            load_addons.assert_called_once_with(unpacked)

        self.assertIsNotNone(model_pack.concept_db)
        self.assertIsNotNone(model_pack.vocab)
        self.assertEqual(model_pack.meta_cats.count(), 0)

    def test_register_model_pack_registers_multiple_meta_cats(self):
        model_pack, unpacked = self._prepare_model_pack(name="multi-meta-cat-pack")
        comps = os.path.join(unpacked, "saved_components")
        addons = [
            (os.path.join(comps, "addon_meta_cat.Status"),
             _make_meta_cat_addon(category_name="Status", model_name="bert")),
            (os.path.join(comps, "addon_meta_cat.Experiencer"),
             _make_meta_cat_addon(category_name="Experiencer", model_name="roberta")),
        ]

        with self._register_model_pack(model_pack, addons):
            pass

        self.assertEqual(model_pack.meta_cats.count(), 2)
        self.assertEqual(
            set(model_pack.meta_cats.values_list("name", flat=True)),
            {"Status - bert", "Experiencer - roberta"},
        )

    def test_register_model_pack_with_meta_cat_and_rel_cat(self):
        model_pack, unpacked = self._prepare_model_pack(name="mixed-addon-pack")
        comps = os.path.join(unpacked, "saved_components")
        meta_cat_path = os.path.join(comps, "addon_meta_cat.Status")
        rel_cat_path = os.path.join(comps, "addon_rel_cat.rel_cat")
        addons = [
            (meta_cat_path, _make_meta_cat_addon()),
            (rel_cat_path, _make_rel_cat_addon()),
        ]

        with self._register_model_pack(model_pack, addons) as load_addons:
            load_addons.assert_called_once_with(unpacked)

        self.assertIsNotNone(model_pack.concept_db)
        self.assertIsNotNone(model_pack.vocab)
        # All addons load; only MetaCAT rows are registered.
        self.assertEqual(model_pack.meta_cats.count(), 1)
        meta_cat_model = model_pack.meta_cats.get()
        self.assertEqual(meta_cat_model.name, "Status - bert")
        self.assertTrue(meta_cat_model.meta_cat_dir.endswith("addon_meta_cat.Status"))

    def test_register_model_pack_without_addons(self):
        model_pack, unpacked = self._prepare_model_pack(name="no-addon-pack")

        with self._register_model_pack(model_pack, []) as load_addons:
            load_addons.assert_called_once_with(unpacked)

        self.assertIsNotNone(model_pack.concept_db)
        self.assertIsNotNone(model_pack.vocab)
        self.assertEqual(model_pack.meta_cats.count(), 0)
