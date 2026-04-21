import unittest
import unittest.mock

from medcat.config import Config
from medcat.components.types import CoreComponentType, AbstractEntityProvidingComponent
from medcat.stats.stats import get_stats
from medcat.trainer import Trainer
from medcat.utils.training_utils import dataset_aware_component


class _FakeEntityBase:

    def __init__(self, start: int, end: int, text: str):
        self.start_char_index = start
        self.end_char_index = end
        self.text = text


class _FakeEntity:

    def __init__(self, start: int, end: int, text: str, cui: str):
        self.base = _FakeEntityBase(start, end, text)
        self.cui = cui
        self.context_similarity = 1.0


class _FakeToken:

    def __init__(self, start: int, end: int):
        self.start_char_index = start
        self.end_char_index = end


class _FakeDocBase:

    def __init__(self, text: str):
        self.text = text


class _FakeDoc:

    def __init__(self, text: str, cui_by_start: dict[int, str]):
        self.text = text
        self.base = _FakeDocBase(text)
        self.cui_by_start = cui_by_start
        self.ner_ents = []
        self.linked_ents = []

    def get_tokens(self, start: int, end: int):
        return [_FakeToken(start, end)]


class _FakeTokenizer:

    def entity_from_tokens_in_doc(self, tkns, doc: _FakeDoc):
        start = tkns[0].start_char_index
        end = tkns[-1].end_char_index
        text = doc.text[start:end]
        cui = doc.cui_by_start.get(start, "C_WRONG")
        return _FakeEntity(start, end, text, cui)


class _EmptyNER(AbstractEntityProvidingComponent):
    name = "empty_ner"

    def __init__(self):
        super().__init__(False, False)

    def get_type(self) -> CoreComponentType:
        return CoreComponentType.ner

    def predict_entities(self, doc, ents=None):
        return []


class _PassThroughLinker(AbstractEntityProvidingComponent):
    name = "pass_linker"

    def __init__(self):
        super().__init__(True, True)

    def get_type(self) -> CoreComponentType:
        return CoreComponentType.linking

    def predict_entities(self, doc, ents=None):
        return list(doc.ner_ents)


class _TrainablePassThroughLinker(_PassThroughLinker):

    full_name = "linking:pass_linker"

    def __init__(self):
        super().__init__()
        self.unsup_train_calls = 0
        self.sup_train_calls = 0

    def train_unsupervised(self, doc):
        self.unsup_train_calls += 1

    def train(self, *args, **kwargs):
        self.sup_train_calls += 1


class _TrainableNER(_EmptyNER):

    full_name = "ner:trainable_ner"

    def __init__(self):
        super().__init__()
        self.unsup_train_calls = 0
        self.sup_train_calls = 0

    def train_unsupervised(self, doc):
        self.unsup_train_calls += 1

    def train(self, *args, **kwargs):
        self.sup_train_calls += 1


class _FakeFilters:

    def __init__(self) -> None:
        self.cuis = []
        self.exclude_cuis = []

    def check_filters(self, cui: str) -> bool:
        return True


class _FakePipeline:

    def __init__(self, components):
        self._components = components
        self.tokenizer = _FakeTokenizer()

    def get_component(self, comp_type):
        for comp in self._components:
            if comp.get_type() == comp_type:
                return comp
        raise KeyError(comp_type)

    def iter_all_components(self):
        return self._components

    def entity_from_tokens_in_doc(self, tkns, doc):
        return self.tokenizer.entity_from_tokens_in_doc(tkns, doc)

    def tokenizer_with_tag(self, text):
        return _FakeDoc(text, {})

    def __call__(self, doc):
        for comp in self._components:
            doc = comp(doc)
        return doc


class _FakeCDB:

    def __init__(self, config):
        self.config = config
        self.addl_info = {}
        self.cui2info = {}

    def reset_training(self):
        return

    def _add_concept(self, *args, **kwargs):
        return


class _FakeCat:

    def __init__(self, dataset, components):
        self.config = Config()
        self.config.components.linking.filters = _FakeFilters()
        self.cdb = _FakeCDB(self.config)
        self.pipe = _FakePipeline(components)
        self._dataset = dataset

    def __call__(self, text):
        by_text = {doc["text"]: doc for project in self._dataset["projects"]
                   for doc in project["documents"]}
        ann_doc = by_text[text]
        cui_by_start = {ann["start"]: ann["cui"] for ann in ann_doc["annotations"]}
        doc = _FakeDoc(text, cui_by_start)
        return self.pipe(doc)


class TrainingUtilsTests(unittest.TestCase):

    DATASET = {
        "projects": [{
            "id": "P1",
            "name": "P1",
            "cuis": "",
            "tuis": "",
            "documents": [{
                "id": "D1",
                "name": "D1",
                "text": "abc def",
                "annotations": [{"start": 0, "end": 3, "cui": "C1", "value": "abc"}],
            }]
        }]
    }

    def test_get_stats_can_be_perfect_when_ner_and_linker_are_dataset_aware(self):
        cat = _FakeCat(self.DATASET, [_EmptyNER(), _PassThroughLinker()])

        with dataset_aware_component(cat, CoreComponentType.ner, self.DATASET):
            with dataset_aware_component(cat, CoreComponentType.linking, self.DATASET):
                _, fns, tps, _, _, cui_f1, _, _ = get_stats(
                    cat, self.DATASET, do_print=False)

        self.assertEqual(fns, {})
        self.assertEqual(tps.get("C1"), 1)
        self.assertEqual(cui_f1.get("C1"), 1.0)

    def test_get_stats_can_isolate_ner_quality_by_cheating_ner_only(self):
        cat = _FakeCat(self.DATASET, [_EmptyNER(), _PassThroughLinker()])

        with dataset_aware_component(cat, CoreComponentType.ner, self.DATASET):
            _, fns, tps, _, _, cui_f1, _, _ = get_stats(
                cat, self.DATASET, do_print=False)

        self.assertEqual(fns, {})
        self.assertEqual(tps.get("C1"), 1)
        self.assertEqual(cui_f1.get("C1"), 1.0)

    def test_train_unsupervised_can_train_only_linker_when_ner_is_cheating(self):
        ner = _TrainableNER()
        linker = _TrainablePassThroughLinker()
        cat = _FakeCat(self.DATASET, [ner, linker])
        trainer = Trainer(cat.cdb, cat.__call__, cat.pipe)

        with dataset_aware_component(cat, CoreComponentType.ner, self.DATASET):
            trainer.train_unsupervised(["abc def"], nepochs=1)

        self.assertEqual(ner.unsup_train_calls, 0)
        self.assertEqual(linker.unsup_train_calls, 1)

    def test_train_unsupervised_can_train_only_ner_when_linker_is_cheating(self):
        ner = _TrainableNER()
        linker = _TrainablePassThroughLinker()
        cat = _FakeCat(self.DATASET, [ner, linker])
        trainer = Trainer(cat.cdb, cat.__call__, cat.pipe)

        with dataset_aware_component(cat, CoreComponentType.linking, self.DATASET):
            trainer.train_unsupervised(["abc def"], nepochs=1)

        self.assertEqual(ner.unsup_train_calls, 1)
        self.assertEqual(linker.unsup_train_calls, 0)

    def test_train_supervised_can_train_only_linker_when_ner_is_cheating(self):
        ner = _TrainableNER()
        linker = _TrainablePassThroughLinker()
        cat = _FakeCat(self.DATASET, [ner, linker])
        trainer = Trainer(cat.cdb, cat.__call__, cat.pipe)

        with unittest.mock.patch("medcat.trainer.prepare_name", return_value={"abc": {}}):
            with dataset_aware_component(cat, CoreComponentType.ner, self.DATASET):
                trainer.train_supervised_raw(self.DATASET, disable_progress=True)

        self.assertEqual(ner.sup_train_calls, 0)
        self.assertEqual(linker.sup_train_calls, 1)

    def test_train_supervised_can_train_only_ner_when_linker_is_cheating(self):
        ner = _TrainableNER()
        linker = _TrainablePassThroughLinker()
        cat = _FakeCat(self.DATASET, [ner, linker])
        trainer = Trainer(cat.cdb, cat.__call__, cat.pipe)

        with unittest.mock.patch("medcat.trainer.prepare_name", return_value={"abc": {}}):
            with dataset_aware_component(cat, CoreComponentType.linking, self.DATASET):
                trainer.train_supervised_raw(self.DATASET, disable_progress=True)

        self.assertEqual(ner.sup_train_calls, 1)
        self.assertEqual(linker.sup_train_calls, 0)
