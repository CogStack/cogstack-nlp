"""Unit tests for api.model_cache.

We avoid loading actual MedCAT artifacts by mocking CDB.load / Vocab.load /
CAT.load_model_pack. Cache state is reset in setUp and tearDown.
"""

from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from .. import model_cache
from ..models import ConceptDB, ModelPack, Vocabulary
from ._helpers import create_basic_project


@override_settings(MEDIA_ROOT='/tmp/mct-tests-model-cache')
class ModelCacheTests(TestCase):
    def setUp(self):
        self.cdb_map = {}
        self.vocab_map = {}
        self.cat_map = {}
        self.project = create_basic_project(name='mc-proj')

    def test_is_model_loaded_returns_false_when_cache_empty(self):
        self.assertFalse(
            model_cache.is_model_loaded(self.project, cdb_map=self.cdb_map, cat_map=self.cat_map)
        )

    def test_is_model_loaded_returns_true_when_cdb_cached(self):
        self.cdb_map[self.project.concept_db.id] = MagicMock()
        self.assertTrue(
            model_cache.is_model_loaded(self.project, cdb_map=self.cdb_map, cat_map=self.cat_map)
        )

    def test_get_cached_medcat_returns_none_when_missing(self):
        self.assertIsNone(
            model_cache.get_cached_medcat(self.project, cat_map=self.cat_map)
        )

    def test_get_cached_medcat_returns_value_when_present(self):
        cat_id = f'{self.project.concept_db.id}-{self.project.vocab.id}'
        sentinel = MagicMock()
        self.cat_map[cat_id] = sentinel
        self.assertIs(
            model_cache.get_cached_medcat(self.project, cat_map=self.cat_map),
            sentinel,
        )

    def test_get_cached_medcat_raises_when_no_cdb_and_not_remote(self):
        # Project without CDB but not using a remote service - should raise
        self.project.concept_db = None
        self.project.use_model_service = False
        with self.assertRaises(Exception) as ctx:
            model_cache.get_cached_medcat(self.project, cat_map=self.cat_map)
        self.assertIn('misconfigured', str(ctx.exception))

    def test_get_cached_medcat_raises_for_remote_service_project(self):
        self.project.use_model_service = True
        self.project.model_service_url = 'http://x'
        self.project.concept_db = None
        self.project.vocab = None
        self.project.save()
        with self.assertRaises(ValueError):
            model_cache.get_cached_medcat(self.project, cat_map=self.cat_map)

    def test_clear_cached_medcat_removes_cat_from_cat_map(self):
        cdb_id = self.project.concept_db.id
        vocab_id = self.project.vocab.id
        cat_id = f'{cdb_id}-{vocab_id}'
        self.cat_map[cat_id] = MagicMock()

        model_cache.clear_cached_medcat(self.project, cat_map=self.cat_map)

        self.assertNotIn(cat_id, self.cat_map)

    def test_clear_cached_cdb_no_op_when_missing(self):
        # Should not raise even if cdb not in map
        model_cache.clear_cached_cdb(99999, cdb_map=self.cdb_map)

    def test_clear_cached_vocab_no_op_when_missing(self):
        model_cache.clear_cached_vocab(99999, vocab_map=self.vocab_map)


@override_settings(MEDIA_ROOT='/tmp/mct-tests-model-cache')
class GetCachedCdbTests(TestCase):
    def setUp(self):
        self.cdb = ConceptDB(name='cached-cdb', cdb_file='cached-cdb.dat')
        self.cdb.save(skip_load=True)
        self.cdb_map = {}

    @patch('api.utils.clear_cdb_cnf_addons')
    @patch('api.model_cache.CDB.load')
    def test_loads_when_not_cached(self, mock_load, mock_clear):
        loaded = MagicMock()
        mock_load.return_value = loaded

        cached = model_cache.get_cached_cdb(self.cdb.id, cdb_map=self.cdb_map)
        self.assertIs(cached, loaded)
        self.assertIn(self.cdb.id, self.cdb_map)
        mock_clear.assert_called_once()

    @patch('api.model_cache.CDB.load')
    def test_returns_existing_when_cached(self, mock_load):
        sentinel = MagicMock()
        self.cdb_map[self.cdb.id] = sentinel
        result = model_cache.get_cached_cdb(self.cdb.id, cdb_map=self.cdb_map)
        self.assertIs(result, sentinel)
        mock_load.assert_not_called()


@override_settings(MEDIA_ROOT='/tmp/mct-tests-model-cache')
class IsModelPackLoadedTests(TestCase):
    def test_returns_true_when_present(self):
        cat_map = {'mp42': MagicMock()}
        self.assertTrue(model_cache.is_model_pack_loaded(42, cat_map=cat_map))

    def test_returns_false_when_absent(self):
        self.assertFalse(model_cache.is_model_pack_loaded(42, cat_map={}))

    def test_clear_by_modelpack_id_removes_entry(self):
        cat_map = {'mp42': MagicMock(), 'mp7': MagicMock()}
        model_cache.clear_cached_medcat_by_model_pack_id(42, cat_map=cat_map)
        self.assertNotIn('mp42', cat_map)
        self.assertIn('mp7', cat_map)

    def test_clear_by_modelpack_id_no_op_when_missing(self):
        cat_map = {}
        # Should not raise
        model_cache.clear_cached_medcat_by_model_pack_id(42, cat_map=cat_map)


@override_settings(MEDIA_ROOT='/tmp/mct-tests-model-cache')
class GetMedcatFromModelPackIdTests(TestCase):
    def setUp(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        self.modelpack = ModelPack(
            name='mp-cached',
            model_pack=SimpleUploadedFile('mp.zip', b'fake'),
        )
        self.modelpack.save(skip_load=True)

    @patch('api.model_cache.CAT.load_model_pack')
    def test_loads_when_not_cached(self, mock_load):
        cat_map = {}
        loaded = MagicMock()
        mock_load.return_value = loaded
        result = model_cache.get_medcat_from_model_pack_id(self.modelpack.id, cat_map=cat_map)
        self.assertIs(result, loaded)
        self.assertIn(f'mp{self.modelpack.id}', cat_map)

    @patch('api.model_cache.CAT.load_model_pack')
    def test_returns_cached_when_present(self, mock_load):
        sentinel = MagicMock()
        cat_map = {f'mp{self.modelpack.id}': sentinel}
        result = model_cache.get_medcat_from_model_pack_id(self.modelpack.id, cat_map=cat_map)
        self.assertIs(result, sentinel)
        mock_load.assert_not_called()


@override_settings(MEDIA_ROOT='/tmp/mct-tests-model-cache')
class GetMedcatFromCdbVocabTests(TestCase):
    def setUp(self):
        self.project = create_basic_project(name='cv-proj')

    @patch('api.model_cache.CAT')
    @patch('api.model_cache.Vocab.load')
    @patch('api.model_cache.CDB.load')
    @patch('api.utils.clear_cdb_cnf_addons')
    def test_loads_and_caches(self, mock_clear, mock_cdb_load, mock_vocab_load, mock_cat_cls):
        mock_cdb = MagicMock()
        mock_vocab = MagicMock()
        mock_cdb_load.return_value = mock_cdb
        mock_vocab_load.return_value = mock_vocab
        mock_cat_instance = MagicMock()
        mock_cat_cls.return_value = mock_cat_instance

        cdb_map = {}
        vocab_map = {}
        cat_map = {}

        result = model_cache.get_medcat_from_cdb_vocab(
            self.project, cdb_map=cdb_map, vocab_map=vocab_map, cat_map=cat_map
        )

        cat_id = f'{self.project.concept_db.id}-{self.project.vocab.id}'
        self.assertIn(cat_id, cat_map)
        self.assertIn(self.project.concept_db.id, cdb_map)
        self.assertIn(self.project.vocab.id, vocab_map)
        self.assertIs(result, mock_cat_instance)

    @patch('api.model_cache.CAT')
    @patch('api.model_cache.Vocab.load')
    @patch('api.model_cache.CDB.load')
    def test_returns_cached_cat_when_present(self, mock_cdb_load, mock_vocab_load, mock_cat_cls):
        cat_id = f'{self.project.concept_db.id}-{self.project.vocab.id}'
        sentinel = MagicMock()
        cat_map = {cat_id: sentinel}

        result = model_cache.get_medcat_from_cdb_vocab(
            self.project, cdb_map={}, vocab_map={}, cat_map=cat_map
        )
        self.assertIs(result, sentinel)
        mock_cdb_load.assert_not_called()
        mock_vocab_load.assert_not_called()
        mock_cat_cls.assert_not_called()
