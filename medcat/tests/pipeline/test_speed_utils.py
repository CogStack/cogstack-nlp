import contextlib
import time
import unittest
from unittest.mock import MagicMock, patch
from medcat.tokenizing.tokenizers import BaseTokenizer
from medcat.tokenizing.tokens import MutableDocument
from medcat.pipeline import Pipeline
from medcat.components.types import BaseComponent

import logging
import cProfile
from unittest.mock import patch, MagicMock
from medcat.components.types import CoreComponentType

from medcat.pipeline.speed_utils import (
    AveragingTimedTokenizer,
    TimedComponent,
    AveragingTimedComponent,
    TimedTokenizer,
    pipeline_per_doc_timer,
    pipeline_timer_averaging_docs,
    ProfiledComponent,
    profile_pipeline_component,
    logger,
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
    pipeline._tokenizer = None
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


def make_mock_core_component(name: str = "test_component") -> MagicMock:
    comp = MagicMock(spec=BaseComponent)
    comp.full_name = name
    comp.side_effect = lambda doc: doc
    return comp


class TestProfiledComponent(unittest.TestCase):

    def test_underlying_component_called(self):
        comp = make_mock_component()
        doc = make_mock_doc()
        profiled = ProfiledComponent(comp)
        profiled(doc)
        comp.assert_called_once_with(doc)

    def test_returns_result_of_underlying_component(self):
        comp = make_mock_component()
        doc = make_mock_doc()
        expected = make_mock_doc()
        comp.side_effect = lambda d: expected
        profiled = ProfiledComponent(comp)
        result = profiled(doc)
        self.assertIs(result, expected)

    def test_profiler_is_cprofile_instance(self):
        comp = make_mock_component()
        profiled = ProfiledComponent(comp)
        self.assertIsInstance(profiled._profiler, cProfile.Profile)

    @patch("medcat.pipeline.speed_utils.logger")
    def test_show_stats_logs_tottime_and_cumtime(self, mock_logger):
        comp = make_mock_component()
        doc = make_mock_doc()
        profiled = ProfiledComponent(comp)
        profiled(doc)
        profiled.show_stats(limit=5)
        # Should log once for tottime, once for cumtime
        self.assertEqual(mock_logger.info.call_count, 2)
        logged_messages = mock_logger.info.call_args_list
        print("LOGGED:", logged_messages)
        self.assertTrue(any("tottime" in part for record in logged_messages for part in record))
        self.assertTrue(any("cumtime" in part for record in logged_messages for part in record))

    @patch("medcat.pipeline.speed_utils.logger")
    def test_show_stats_includes_component_name(self, mock_logger):
        comp = make_mock_component("my_component")
        doc = make_mock_doc()
        profiled = ProfiledComponent(comp)
        profiled(doc)
        profiled.show_stats()
        for c in mock_logger.info.call_args_list:
            self.assertIn("my_component", c.args[1])

    @patch("medcat.pipeline.speed_utils.logger")
    def test_show_stats_without_any_calls_does_not_raise(self, mock_logger):
        comp = make_mock_component()
        profiled = ProfiledComponent(comp)
        try:
            profiled.show_stats()
        except Exception as e:
            self.fail(f"show_stats raised unexpectedly: {e}")


class TestProfileComponent(unittest.TestCase):

    @contextlib.contextmanager
    def _pipe_with_data(self, pipeline, comp_type, do_call: bool = True):
        with profile_pipeline_component(pipeline, comp_type):
            if do_call:
                doc = make_mock_doc()
                for comp in pipeline._components + pipeline._addons:
                    comp(doc)
            yield


    def _make_core_pipeline(self, comp_type: CoreComponentType) -> MagicMock:
        pipeline = MagicMock(spec=Pipeline)
        comp = make_mock_component()
        pipeline._components = [comp]
        pipeline._addons = []
        pipeline._tokenizer = None
        pipeline.get_component.return_value = comp
        pipeline.iter_addons.return_value = iter([])
        return pipeline

    def _make_addon_pipeline(self, addon_type) -> tuple[MagicMock, MagicMock]:
        pipeline = MagicMock(spec=Pipeline)
        addon = MagicMock(spec=addon_type)
        addon.full_name = "test_addon"
        addon.side_effect = lambda doc: doc
        pipeline._components = []
        pipeline._addons = [addon]
        pipeline._tokenizer = None
        pipeline.get_component.side_effect = RuntimeError("not a core comp")
        pipeline.iter_addons.return_value = iter([addon])
        return pipeline, addon

    def test_core_component_wrapped_inside_context(self):
        comp_type = MagicMock(spec=CoreComponentType)
        pipeline = self._make_core_pipeline(comp_type)
        with self._pipe_with_data(pipeline, comp_type):
            self.assertTrue(
                any(isinstance(c, ProfiledComponent)
                    for c in pipeline._components))

    def test_core_component_restored_after_context(self):
        comp_type = MagicMock(spec=CoreComponentType)
        pipeline = self._make_core_pipeline(comp_type)
        original = list(pipeline._components)
        with self._pipe_with_data(pipeline, comp_type):
            pass
        self.assertEqual(pipeline._components, original)

    def test_core_component_restored_after_exception(self):
        comp_type = MagicMock(spec=CoreComponentType)
        pipeline = self._make_core_pipeline(comp_type)
        original = list(pipeline._components)
        with self.assertRaises(RuntimeError):
            with self._pipe_with_data(pipeline, comp_type):
                raise RuntimeError("boom")
        self.assertEqual(pipeline._components, original)

    def test_addon_component_wrapped_inside_context(self):
        addon_type = type(MagicMock())
        pipeline, _ = self._make_addon_pipeline(addon_type)
        with self._pipe_with_data(pipeline, addon_type):
            self.assertTrue(
                any(isinstance(a, ProfiledComponent)
                    for a in pipeline._addons))

    def test_addon_component_restored_after_context(self):
        addon_type = type(MagicMock())
        pipeline, _ = self._make_addon_pipeline(addon_type)
        original = list(pipeline._addons)
        with self._pipe_with_data(pipeline, addon_type):
            pass
        self.assertEqual(pipeline._addons, original)

    def test_underlying_component_still_called(self):
        comp_type = MagicMock(spec=CoreComponentType)
        pipeline = self._make_core_pipeline(comp_type)
        original_comp = pipeline.get_component.return_value
        doc = make_mock_doc()
        with self._pipe_with_data(pipeline, comp_type, do_call=False):
            pipeline._components[0](doc)
        original_comp.assert_called_once_with(doc)

    @patch("medcat.pipeline.speed_utils.logger")
    def test_show_stats_called_on_exit(self, mock_logger):
        comp_type = MagicMock(spec=CoreComponentType)
        pipeline = self._make_core_pipeline(comp_type)
        doc = make_mock_doc()
        with self._pipe_with_data(pipeline, comp_type):
            pipeline._components[0](doc)
        # tottime + cumtime = 2 log calls
        self.assertEqual(mock_logger.info.call_count, 2)

    @patch("medcat.pipeline.speed_utils.logger")
    def test_show_stats_called_on_exit_after_exception(self, mock_logger):
        comp_type = MagicMock(spec=CoreComponentType)
        pipeline = self._make_core_pipeline(comp_type)
        doc = make_mock_doc()
        with self.assertRaises(RuntimeError):
            with self._pipe_with_data(pipeline, comp_type):
                pipeline._components[0](doc)
                raise RuntimeError("boom")
        self.assertEqual(mock_logger.info.call_count, 2)


def make_mock_tokenizer(name: str = "test_tokenizer") -> MagicMock:
    tokenizer = MagicMock(spec=BaseTokenizer)
    tokenizer.side_effect = lambda text: make_mock_doc()
    return tokenizer


def make_mock_pipeline_with_tokenizer(*component_names: str) -> MagicMock:
    pipeline = make_mock_pipeline(*component_names)
    pipeline._tokenizer = make_mock_tokenizer()
    return pipeline


class TestTimedTokenizer(unittest.TestCase):

    def test_underlying_tokenizer_called(self):
        tokenizer = make_mock_tokenizer()
        timed = TimedTokenizer(tokenizer)
        timed("some text")
        tokenizer.assert_called_once_with("some text")

    def test_returns_result_of_underlying_tokenizer(self):
        tokenizer = make_mock_tokenizer()
        expected = make_mock_doc()
        tokenizer.side_effect = lambda text: expected
        timed = TimedTokenizer(tokenizer)
        result = timed("some text")
        self.assertIs(result, expected)

    def test_full_name_includes_class_name(self):
        tokenizer = make_mock_tokenizer()
        timed = TimedTokenizer(tokenizer)
        self.assertIn("Tokenizer", timed.full_name)

    @patch("medcat.pipeline.speed_utils.logger")
    def test_logs_once_per_call(self, mock_logger):
        tokenizer = make_mock_tokenizer()
        timed = TimedTokenizer(tokenizer)
        timed("text one")
        timed("text two")
        self.assertEqual(mock_logger.info.call_count, 2)


class TestAveragingTimedTokenizer(unittest.TestCase):

    def _every_n(self, n: int):
        return lambda num_docs, time_spent: num_docs >= n

    def test_underlying_tokenizer_called(self):
        tokenizer = make_mock_tokenizer()
        timed = AveragingTimedTokenizer(tokenizer, self._every_n(1))
        timed("some text")
        tokenizer.assert_called_once_with("some text")

    @patch("medcat.pipeline.speed_utils.logger")
    def test_logs_after_n_calls(self, mock_logger):
        tokenizer = make_mock_tokenizer()
        timed = AveragingTimedTokenizer(tokenizer, self._every_n(3))
        for _ in range(3):
            timed("text")
        mock_logger.info.assert_called_once()

    @patch("medcat.pipeline.speed_utils.logger")
    def test_does_not_log_before_n_calls(self, mock_logger):
        tokenizer = make_mock_tokenizer()
        timed = AveragingTimedTokenizer(tokenizer, self._every_n(3))
        for _ in range(2):
            timed("text")
        mock_logger.info.assert_not_called()


class TestTokenizerInPipelinePerDocTimer(unittest.TestCase):

    def test_tokenizer_replaced_inside_context(self):
        pipeline = make_mock_pipeline_with_tokenizer("comp_a")
        original = pipeline._tokenizer
        with pipeline_per_doc_timer(pipeline):
            self.assertIsInstance(pipeline._tokenizer, TimedTokenizer)
            self.assertIsNot(pipeline._tokenizer, original)

    def test_tokenizer_restored_after_context(self):
        pipeline = make_mock_pipeline_with_tokenizer("comp_a")
        original = pipeline._tokenizer
        with pipeline_per_doc_timer(pipeline):
            pass
        self.assertIs(pipeline._tokenizer, original)

    def test_tokenizer_restored_after_exception(self):
        pipeline = make_mock_pipeline_with_tokenizer("comp_a")
        original = pipeline._tokenizer
        with self.assertRaises(RuntimeError):
            with pipeline_per_doc_timer(pipeline):
                raise RuntimeError("boom")
        self.assertIs(pipeline._tokenizer, original)

    def test_underlying_tokenizer_called(self):
        pipeline = make_mock_pipeline_with_tokenizer("comp_a")
        original_tokenizer = pipeline._tokenizer
        with pipeline_per_doc_timer(pipeline):
            pipeline._tokenizer("some text")
        original_tokenizer.assert_called_once_with("some text")


class TestTokenizerInPipelineTimerAveragingDocs(unittest.TestCase):

    def test_tokenizer_replaced_inside_context(self):
        pipeline = make_mock_pipeline_with_tokenizer("comp_a")
        original = pipeline._tokenizer
        with pipeline_timer_averaging_docs(pipeline, show_frequency_docs=10):
            self.assertIsInstance(pipeline._tokenizer, AveragingTimedTokenizer)
            self.assertIsNot(pipeline._tokenizer, original)

    def test_tokenizer_restored_after_context(self):
        pipeline = make_mock_pipeline_with_tokenizer("comp_a")
        original = pipeline._tokenizer
        with pipeline_timer_averaging_docs(pipeline, show_frequency_docs=10):
            pass
        self.assertIs(pipeline._tokenizer, original)

    @patch("medcat.pipeline.speed_utils.logger")
    def test_tokenizer_flushed_on_exit(self, mock_logger):
        pipeline = make_mock_pipeline_with_tokenizer()
        with pipeline_timer_averaging_docs(pipeline, show_frequency_docs=100):
            for _ in range(5):
                pipeline._tokenizer("text")
        mock_logger.info.assert_called_once()


class TestWithLogging(unittest.TestCase):

    def test_stream_handler_added_when_none_present(self):
        logger.handlers.clear()
        with pipeline_per_doc_timer(make_mock_pipeline_with_tokenizer()):
            self.assertTrue(
                any(type(h) is logging.StreamHandler for h in logger.handlers))

    def test_stream_handler_removed_after_context(self):
        logger.handlers.clear()
        with pipeline_per_doc_timer(make_mock_pipeline_with_tokenizer()):
            pass
        self.assertFalse(
            any(type(h) is logging.StreamHandler for h in logger.handlers))

    def test_stream_handler_not_added_if_already_present(self):
        logger.handlers.clear()
        existing = logging.StreamHandler()
        logger.addHandler(existing)
        with pipeline_per_doc_timer(make_mock_pipeline_with_tokenizer()):
            stream_handlers = [
                h for h in logger.handlers
                if type(h) is logging.StreamHandler
            ]
            self.assertEqual(len(stream_handlers), 1)
        logger.removeHandler(existing)

    def test_log_level_restored_after_context(self):
        original_level = logger.level
        with pipeline_per_doc_timer(make_mock_pipeline_with_tokenizer()):
            pass
        self.assertEqual(logger.level, original_level)

    def test_log_level_restored_after_exception(self):
        original_level = logger.level
        with self.assertRaises(RuntimeError):
            with pipeline_per_doc_timer(make_mock_pipeline_with_tokenizer()):
                raise RuntimeError("boom")
        self.assertEqual(logger.level, original_level)

    def test_stream_handler_removed_after_exception(self):
        logger.handlers.clear()
        with self.assertRaises(RuntimeError):
            with pipeline_per_doc_timer(make_mock_pipeline_with_tokenizer()):
                raise RuntimeError("boom")
        self.assertFalse(
            any(type(h) is logging.StreamHandler for h in logger.handlers))

if __name__ == "__main__":
    unittest.main()
