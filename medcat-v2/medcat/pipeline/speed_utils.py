from typing import Callable, Union, Type, cast
import time
import contextlib
import logging
from abc import ABC, abstractmethod
from io import StringIO
import cProfile
from pstats import Stats
import statistics

from medcat.components.addons.addons import AddonComponent
from medcat.components.types import BaseComponent, CoreComponent, CoreComponentType
from medcat.pipeline import Pipeline
from medcat.tokenizing.tokens import MutableDocument
from medcat.cat import AddonType

logger = logging.getLogger(__name__)

logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler())


class BaseTimedComponent(ABC):

    def __init__(self, component: BaseComponent):
        self._component = component

    @property
    def full_name(self):
        return self._component.full_name

    def __getattr__(self, name: str):
        if name == '_component':
            raise AttributeError('_component not set')
        return getattr(self._component, name)

    @abstractmethod
    def __call__(self, doc: MutableDocument) -> MutableDocument:
        pass

    def __repr__(self):
        return f"{self.__class__.__name__}({self._component!r})"


class TimedComponent(BaseTimedComponent):
    """Wraps a component and logs the time spent in it."""

    def __call__(self, doc: MutableDocument) -> MutableDocument:
        start = time.perf_counter()
        result = self._component(doc)
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info("Component %s took %.3fms", self.full_name, elapsed_ms)
        return result


class AveragingTimedComponent(BaseTimedComponent):

    def __init__(self, component: BaseComponent,
                 condition: Callable[[int, float], bool]):
        super().__init__(component)
        self._condition = condition
        self._reset()

    def _reset(self):
        self._to_average: list[float] = []
        self._last_show = time.perf_counter()

    def _show_time(self):
        total_docs = len(self._to_average)
        if total_docs == 0:
            mean_elapsed = 0
            min_elapsed = 0
            median_elapsed = 0
            max_elapsed = 0
        else:
            mean_elapsed = sum(self._to_average) / total_docs
            min_elapsed = min(self._to_average)
            median_elapsed = statistics.median(self._to_average)
            max_elapsed = max(self._to_average)
        time_elapsed = time.perf_counter() - self._last_show
        logger.info("Component %s took (min/mean/median/average): "
                    "%.3fms / %.3fms / %.3fms / %.3fms"
                    "over %d docs and a total of %.3fs",
                    self.full_name,
                    min_elapsed, mean_elapsed, median_elapsed, max_elapsed,
                    total_docs, time_elapsed)

    def _maybe_show_time(self, elapsed_ms: float):
        self._to_average.append(elapsed_ms)
        if self._condition(len(self._to_average),
                           time.perf_counter() - self._last_show):
            self._show_time()
            self._reset()

    def __call__(self, doc: MutableDocument) -> MutableDocument:
        start = time.perf_counter()
        result = self._component(doc)
        elapsed_ms = (time.perf_counter() - start) * 1000
        self._maybe_show_time(elapsed_ms)
        return result


class ProfiledComponent(BaseTimedComponent):

    def __init__(self, component: BaseComponent):
        super().__init__(component)
        self._profiler = cProfile.Profile()


    def __call__(self, doc: MutableDocument) -> MutableDocument:
        self._profiler.enable()
        result = self._component(doc)
        self._profiler.disable()
        return result

    def _show_type(self, stats_type: str, limit: int):
        if not self._profiler.getstats():
            logger.info("Component %s has no profiling data", self.full_name)
            return
        stream = StringIO()
        stats = Stats(self._profiler, stream=stream)
        stats.sort_stats(stats_type).print_stats(limit)
        logger.info("Component %s profile (by %s):\n%s",
                self.full_name, stats_type, stream.getvalue())

    def show_stats(self, limit: int = 20):
        self._show_type('tottime', limit)
        self._show_type('cumtime', limit)


@contextlib.contextmanager
def pipeline_per_doc_timer(
        pipeline: Pipeline,
        timer_init: Callable[[BaseComponent], BaseTimedComponent] = TimedComponent
    ):
    """Time the pipeline on a per document basis.

    Args:
        pipeline (Pipeline): The pipeline to time.
        timer_init (Callable[[BaseComponent], BaseTimedComponent])): The
            initialiser for the timer. Defaults to TimedComponent.

    Yields:
        Pipeline: The same pipeline.
    """
    original_components = pipeline._components
    original_addons = pipeline._addons

    updated_core_components = [
        cast(CoreComponent, timer_init(c))
        for c in original_components]
    updated_addons = [
        cast(AddonComponent, timer_init(a))
        for a in original_addons]

    pipeline._components = updated_core_components
    pipeline._addons = updated_addons

    try:
        yield pipeline
    finally:
        pipeline._components = original_components
        pipeline._addons = original_addons


@contextlib.contextmanager
def pipeline_timer_averaging_docs(
        pipeline: Pipeline,
        show_frequency_docs: int = -1,
        show_frequency_secs: float = -1):
    """Time the pipeline on a multi doc basis.

    This can be set to show timings after a certain number of docs or
    after a certain time spent. The default configuration averages over 100
    documents

    Args:
        pipeline (Pipeline): The pipeline to time.
        show_frequency_docs (int): The number of documents to average
            over, or (if set to -1) use seconds instead. Defaults to -1 if
            secs frequency set and to 100 otherwise.
        show_frequency_secs (float): The frequency in seconds for showing the
            average timings for each component. Defaults to -1.

    Raises:
        ValueError: If one of the frequencies is 0.
        ValueError: If both document and time frequencies are specified.


    Yields:
        Pipeline: The same pipeline.
    """
    if show_frequency_docs == 0 or show_frequency_secs == 0:
        raise ValueError(
            "Frequency values must be greater than 0 or -1 (disabled)")
    if show_frequency_docs > 0 and show_frequency_secs > 0:
        raise ValueError("Choose either document frequency OR time frequency")
    if show_frequency_secs == -1 and show_frequency_docs == -1:
        show_frequency_docs = 100

    original_components = pipeline._components
    original_addons = pipeline._addons

    def wrapper_condition(num_docs: int, time_spent: float) -> bool:
        if show_frequency_docs >= 0:
            return num_docs >= show_frequency_docs
        return time_spent >= show_frequency_secs
    
    wrapped_core_comps = [
        AveragingTimedComponent(component, wrapper_condition)
        for component in original_components]
    wrapped_addons = [
        AveragingTimedComponent(addon, wrapper_condition)
        for addon in original_addons]

    pipeline._components = wrapped_core_comps  # type: ignore
    pipeline._addons = wrapped_addons  # type: ignore

    try:
        yield pipeline
    finally:
        pipeline._components = original_components
        pipeline._addons = original_addons
        for comp in [*wrapped_core_comps, *wrapped_addons]:
            if comp._to_average:
                comp._show_time()
                comp._reset()


@contextlib.contextmanager
def profile_pipeline_component(
        pipeline: Pipeline,
        comp_type: Union[CoreComponentType, Type[AddonType]],
        limit: int = 20,
    ):
    """Time a specific component of the pipeline.

    This can profile either a core component or an addon component.
    But notably, in case of addon components, all components of the
    same type will be profiled.

    Args:
        pipeline (Pipeline): The pipeline to time.
        comp_type (Union[CoreComponentType, Type[AddonType]]): The type of
            component to profile. This can be either a core component
            or an addon component.
        limit (int): The number of function calls to show in output.
            Defaults to 20.

    Yields:
        Pipeline: The same pipeline.
    """
    original_components = pipeline._components
    original_addons = pipeline._addons

    updated_addons: list[AddonComponent]
    updated_core_comps: list[CoreComponent]
    if isinstance(comp_type, CoreComponentType):
        changed_comp = pipeline.get_component(comp_type)
        updated_core_comps = [
            comp if comp != changed_comp else
            cast(CoreComponent, ProfiledComponent(changed_comp))
            for comp in original_components
        ]
        updated_addons = original_addons
    else:
        changed_comps = [
            addon for addon in pipeline.iter_addons()
            if isinstance(addon, comp_type)
        ]
        updated_core_comps = original_components
        updated_addons = [
            addon if addon not in changed_comps
            else cast(AddonComponent, ProfiledComponent(addon))
            for addon in original_addons
        ]
    profiled_comps = [
        comp for comp in updated_core_comps + updated_addons
        if isinstance(comp, ProfiledComponent)
    ]

    pipeline._components = updated_core_comps
    pipeline._addons = updated_addons

    try:
        yield pipeline
    finally:
        pipeline._components = original_components
        pipeline._addons = original_addons
        for comp in profiled_comps:
            comp.show_stats(limit)
