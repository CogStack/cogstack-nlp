"""Tests for registering model packs that include RelCAT addons.

The Trainer's responsibility when registering a model pack is to load its
addons and register only the MetaCAT ones (as ``MetaCATModel`` rows). RelCAT
addons must be tolerated (loaded by ``CAT.load_addons``) but skipped during
registration. These tests mock ``CAT.load_addons`` so they exercise that
filtering logic without downloading or loading real models.
"""

import os
import tempfile
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
class ModelPackRelCATRegistrationTests(TestCase):
    def _prepare_model_pack(self, name="relcat-pack-test"):
        """Create a ModelPack with a fake unpacked dir (cdb dir + vocab file)."""
        model_pack = ModelPack(name=name)
        model_pack.model_pack.save(f"{name}.zip", ContentFile(b"fake"), save=False)
        unpacked = model_pack.model_pack.path[: -len(".zip")]
        os.makedirs(os.path.join(unpacked, "cdb"), exist_ok=True)
        with open(os.path.join(unpacked, "vocab"), "w", encoding="utf-8") as fh:
            fh.write("")
        return model_pack, unpacked

    def test_register_model_pack_with_relcat_addon_skips_relcat(self):
        model_pack, unpacked = self._prepare_model_pack()
        comps = os.path.join(unpacked, "saved_components")

        addons = [
            (os.path.join(comps, "addon_meta_cat.Status"), _make_meta_cat_addon()),
            (os.path.join(comps, "addon_rel_cat.rel_cat"), _make_rel_cat_addon()),
        ]

        with patch("api.models.CAT.attempt_unpack"), \
                patch("api.models.CDB.load"), \
                patch("api.models.Vocab.load"), \
                patch("api.models.CAT.load_addons", return_value=addons):
            model_pack.save()

        self.assertIsNotNone(model_pack.concept_db)
        self.assertIsNotNone(model_pack.vocab)
        # RelCAT addon must be filtered out; only the MetaCAT is registered.
        self.assertEqual(model_pack.meta_cats.count(), 1)
        self.assertEqual(model_pack.meta_cats.first().name, "Status - bert")

    def test_register_model_pack_without_addons(self):
        model_pack, unpacked = self._prepare_model_pack(name="no-addon-pack")

        with patch("api.models.CAT.attempt_unpack"), \
                patch("api.models.CDB.load"), \
                patch("api.models.Vocab.load"), \
                patch("api.models.CAT.load_addons", return_value=[]):
            model_pack.save()

        self.assertIsNotNone(model_pack.concept_db)
        self.assertEqual(model_pack.meta_cats.count(), 0)
