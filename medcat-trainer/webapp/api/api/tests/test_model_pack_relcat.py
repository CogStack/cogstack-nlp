"""Tests for registering model packs that include RelCAT addons."""

import os
import shutil
import tempfile
import zipfile
from urllib.request import urlretrieve

from django.core.files.base import ContentFile
from django.test import TestCase, override_settings

from medcat.storage.serialisers import MANUAL_SERIALISED_TAG, SER_TYPE_FILE

from ..models import ModelPack

MODEL_PACK_ZIP_URL = (
    "https://raw.githubusercontent.com/CogStack/cogstack-nlp/"
    "051edf6cbd94fa83436fab807aff49d78dd68e59/"
    "medcat-service/models/examples/example-medcat-v2-model-pack.zip"
)
REL_CAT_ADDON_CLS = (
    "medcat.components.addons.relation_extraction.rel_cat.RelCATAddon"
)


def _add_rel_cat_addon_stub(model_pack_dir: str, addon_name: str = "rel_cat") -> None:
    """Add a minimal RelCAT addon folder that triggers manual deserialisation."""
    components_dir = os.path.join(model_pack_dir, "saved_components")
    os.makedirs(components_dir, exist_ok=True)
    addon_dir = os.path.join(components_dir, f"addon_rel_cat.{addon_name}")
    os.makedirs(addon_dir, exist_ok=True)
    with open(os.path.join(addon_dir, SER_TYPE_FILE), "w", encoding="utf-8") as f:
        f.write(MANUAL_SERIALISED_TAG + REL_CAT_ADDON_CLS)


def _build_model_pack_zip_with_relcat(cache_dir: str) -> str:
    zip_path = os.path.join(cache_dir, "cached_model_pack.zip")
    if not os.path.exists(zip_path):
        urlretrieve(MODEL_PACK_ZIP_URL, zip_path)
    unpacked = os.path.join(cache_dir, "model_pack")
    if os.path.exists(unpacked):
        shutil.rmtree(unpacked)
    shutil.unpack_archive(zip_path, unpacked)
    _add_rel_cat_addon_stub(unpacked)
    out_zip = os.path.join(cache_dir, "model_pack_with_relcat.zip")
    if os.path.exists(out_zip):
        os.remove(out_zip)
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(unpacked):
            for file_name in files:
                file_path = os.path.join(root, file_name)
                arcname = os.path.relpath(file_path, unpacked)
                zf.write(file_path, arcname)
    return out_zip


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class ModelPackRelCATRegistrationTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._cache_dir = tempfile.mkdtemp()
        cls.model_pack_zip = _build_model_pack_zip_with_relcat(cls._cache_dir)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls._cache_dir, ignore_errors=True)
        super().tearDownClass()

    def test_register_model_pack_with_relcat_addon_succeeds(self):
        with open(self.model_pack_zip, "rb") as fh:
            pack_bytes = fh.read()
        model_pack = ModelPack(name="relcat-pack-test")
        model_pack.model_pack = ContentFile(pack_bytes, name="relcat-pack-test.zip")
        model_pack.save()

        self.assertIsNotNone(model_pack.concept_db)
        self.assertIsNotNone(model_pack.vocab)
