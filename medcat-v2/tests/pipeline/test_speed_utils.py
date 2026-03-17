import time
import unittest
from unittest.mock import MagicMock, patch
from medcat.tokenizing.tokens import MutableDocument
from medcat.pipeline import Pipeline
from medcat.components.types import BaseComponent

from medcat.pipeline.speed_utils import (
    TimedComponent,
    AveragingTimedComponent,
    pipeline_per_doc_timer,
    pipeline_timer_averaging_docs,
)


def make_mock_component(name: str = "test_component") -> MagicMock:
    """Create a mock BaseComponent with a full_name and callable behaviour."""
    comp = MagicMock(spec=BaseComponent)
    comp.full_name = name
    comp.side_effect = lambda doc: doc  # passthrough
    return comp


def make_mock_pipeline(*component_names: str) -> MagicMock:
    """Create a mock Pipeline with named components and no addons."""
    pipeline = MagicMock(spec=Pipeline)
    pipeline._components = [make_mock_component(n) for n in component_names]
    pipeline._addons = []
    return pipeline


def make_mock_doc() -> MagicMock:
    return MagicMock(spec=MutableDocument)


class TestBaseTimedComponentDelegation(unittest.TestCase):

    def test_call_delegates_to_underlying_component(self):
        comp = make_mock_component()
        doc = make_mock_doc()
        timed = TimedComponent(comp)
        timed(doc)
        comp.assert_called_once_with(doc)

    def test_call_returns_result_of_underlying_component(self):
        comp = make_mock_component()
        doc = make_mock_doc()
        expected = make_mock_doc()
        comp.side_effect = lambda d: expected
        timed = TimedComponent(comp)
        result = timed(doc)
        self.assertIs(result, expected)

    def test_full_name_delegates(self):
        comp = make_mock_component("my_component")
        timed = TimedComponent(comp)
        self.assertEqual(timed.full_name, "my_component")

    def test_getattr_delegates_unknown_attribute(self):
        comp = make_mock_component()
        comp.some_custom_attr = 42
        timed = TimedComponent(comp)
        self.assertEqual(timed.some_custom_attr, 42)

    def test_getattr_raises_on_missing_component(self):
        timed = TimedComponent.__new__(TimedComponent)
        with self.assertRaises(AttributeError):
            _ = timed._component

    def test_repr_includes_class_and_component(self):
        comp = make_mock_component()
        timed = TimedComponent(comp)
        r = repr(timed)
        self.assertIn("TimedComponent", r)
        self.assertIn(repr(comp), r)


class TestPerDocTimed(unittest.TestCase):

    def test_components_replaced_inside_context(self):
        pipeline = make_mock_pipeline("comp_a", "comp_b")
        original = list(pipeline._components)
        with pipeline_per_doc_timer(pipeline):
            for comp in pipeline._components:
                self.assertIsInstance(comp, TimedComponent)
            self.assertNotEqual(pipeline._components, original)

    def test_components_restored_after_context(self):
        pipeline = make_mock_pipeline("comp_a")
        original = list(pipeline._components)
        with pipeline_per_doc_timer(pipeline):
            pass
        self.assertEqual(pipeline._components, original)

    def test_components_restored_after_exception(self):
        pipeline = make_mock_pipeline("comp_a")
        original = list(pipeline._components)
        with self.assertRaises(RuntimeError):
            with pipeline_per_doc_timer(pipeline):
                raise RuntimeError("boom")
        self.assertEqual(pipeline._components, original)

    def test_addons_replaced_and_restored(self):
        pipeline = make_mock_pipeline()
        pipeline._addons = [make_mock_component("addon_a")]
        original_addons = list(pipeline._addons)
        with pipeline_per_doc_timer(pipeline):
            for addon in pipeline._addons:
                self.assertIsInstance(addon, TimedComponent)
        self.assertEqual(pipeline._addons, original_addons)

    def test_underlying_component_called_per_doc(self):
        pipeline = make_mock_pipeline("comp_a")
        original_comp = pipeline._components[0]
        doc = make_mock_doc()
        with pipeline_per_doc_timer(pipeline):
            for _ in range(3):
                pipeline._components[0](doc)
        self.assertEqual(original_comp.call_count, 3)

    @patch("medcat.pipeline.speed_utils.logger")
    def test_logs_once_per_doc_per_component(self, mock_logger):
        pipeline = make_mock_pipeline("comp_a", "comp_b")
        doc = make_mock_doc()
        with pipeline_per_doc_timer(pipeline):
            for comp in pipeline._components:
                comp(doc)
                comp(doc)
        # 2 components * 2 calls each = 4 log lines
        self.assertEqual(mock_logger.info.call_count, 4)


class TestAveragingTimedComponent(unittest.TestCase):

    def _always_condition(self, num_docs: int, time_spent: float) -> bool:
        return True

    def _never_condition(self, num_docs: int, time_spent: float) -> bool:
        return False

    def _every_n(self, n: int):
        return lambda num_docs, time_spent: num_docs >= n

    def test_underlying_component_called(self):
        comp = make_mock_component()
        doc = make_mock_doc()
        timed = AveragingTimedComponent(comp, self._always_condition)
        timed(doc)
        comp.assert_called_once_with(doc)

    @patch("medcat.pipeline.speed_utils.logger")
    def test_logs_when_condition_met(self, mock_logger):
        comp = make_mock_component()
        doc = make_mock_doc()
        timed = AveragingTimedComponent(comp, self._every_n(3))
        for _ in range(3):
            timed(doc)
        mock_logger.info.assert_called_once()

    @patch("medcat.pipeline.speed_utils.logger")
    def test_does_not_log_before_condition_met(self, mock_logger):
        comp = make_mock_component()
        doc = make_mock_doc()
        timed = AveragingTimedComponent(comp, self._every_n(3))
        for _ in range(2):
            timed(doc)
        mock_logger.info.assert_not_called()

    @patch("medcat.pipeline.speed_utils.logger")
    def test_resets_after_condition_met(self, mock_logger):
        comp = make_mock_component()
        doc = make_mock_doc()
        timed = AveragingTimedComponent(comp, self._every_n(2))
        for _ in range(4):
            timed(doc)
        # Should have logged twice: after doc 2 and after doc 4
        self.assertEqual(mock_logger.info.call_count, 2)

    @patch("medcat.pipeline.speed_utils.logger")
    def test_time_based_condition(self, mock_logger):
        comp = make_mock_component()
        doc = make_mock_doc()
        # Trigger after 0.05s
        timed = AveragingTimedComponent(
            comp, lambda n, t: t >= 0.05)
        timed(doc)  # first call, unlikely to exceed 0.05s immediately
        mock_logger.info.assert_not_called()
        time.sleep(0.06)
        timed(doc)  # this call should trip the condition
        mock_logger.info.assert_called_once()

    @patch("medcat.pipeline.speed_utils.logger")
    def test_flush_on_exit_logs_remaining(self, mock_logger):
        pipeline = make_mock_pipeline("comp_a")
        doc = make_mock_doc()
        # Condition never fires during processing
        with pipeline_timer_averaging_docs(pipeline, show_frequency_docs=100):
            for _ in range(5):
                pipeline._components[0](doc)
        # Should have flushed the 5 accumulated docs on exit
        mock_logger.info.assert_called_once()

    @patch("medcat.pipeline.speed_utils.logger")
    def test_no_flush_on_exit_if_nothing_accumulated(self, mock_logger):
        pipeline = make_mock_pipeline("comp_a")
        with pipeline_timer_averaging_docs(pipeline, show_frequency_docs=100):
            pass  # no docs processed
        mock_logger.info.assert_not_called()


class TestDocAverageTimedValidation(unittest.TestCase):

    def test_raises_if_docs_is_zero(self):
        pipeline = make_mock_pipeline()
        with self.assertRaises(ValueError):
            with pipeline_timer_averaging_docs(pipeline, show_frequency_docs=0):
                pass

    def test_raises_if_secs_is_zero(self):
        pipeline = make_mock_pipeline()
        with self.assertRaises(ValueError):
            with pipeline_timer_averaging_docs(pipeline, show_frequency_secs=0):
                pass

    def test_raises_if_both_specified(self):
        pipeline = make_mock_pipeline()
        with self.assertRaises(ValueError):
            with pipeline_timer_averaging_docs(
                    pipeline,
                    show_frequency_docs=10,
                    show_frequency_secs=5.0):
                pass

    def test_defaults_to_100_docs_if_neither_specified(self):
        pipeline = make_mock_pipeline("comp_a")
        doc = make_mock_doc()
        with patch("medcat.pipeline.speed_utils.logger") as mock_logger:
            with pipeline_timer_averaging_docs(pipeline):
                for _ in range(100):
                    pipeline._components[0](doc)
            mock_logger.info.assert_called_once()

    def test_components_restored_after_exception(self):
        pipeline = make_mock_pipeline("comp_a")
        original = list(pipeline._components)
        with self.assertRaises(RuntimeError):
            with pipeline_timer_averaging_docs(pipeline, show_frequency_docs=10):
                raise RuntimeError("boom")
        self.assertEqual(pipeline._components, original)


if __name__ == "__main__":
    unittest.main()
