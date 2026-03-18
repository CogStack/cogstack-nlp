from typing import Callable, Literal, Protocol, Union, Type, cast
import time
import contextlib
import logging
from io import StringIO
import cProfile
from pstats import Stats
import statistics

from medcat.components.addons.addons import AddonComponent
from medcat.components.types import BaseComponent, CoreComponent, CoreComponentType
from medcat.pipeline import Pipeline
from medcat.tokenizing.tokenizers import BaseTokenizer
from medcat.tokenizing.tokens import MutableDocument
from medcat.cat import AddonType

logger = logging.getLogger(__name__)


@contextlib.contextmanager
def _with_logging():
    has_stream_handler = any(
        type(h) is logging.StreamHandler
        for h in logger.handlers
    )
    handler = None
    original_level = logger.level
    if not has_stream_handler:
        handler = logging.StreamHandler()
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    try:
        yield
    finally:
        if handler is not None:
            logger.removeHandler(handler)
            logger.setLevel(original_level)


def context_manager_with_logging(func):
    @contextlib.wraps(func)
    @contextlib.contextmanager
    def wrapper(*args, **kwargs):
        with _with_logging():
            yield from func(*args, **kwargs)
    return wrapper


class BaseTimedObjectProtocol(Protocol):
    @property
    def full_name(self) -> str:
        pass

    def __getattr__(self, name: str):
        pass

    def __repr__(self) -> str:
        pass


class BaseTimedObject:

    def __init__(self, component: Union[BaseComponent, BaseTokenizer]):
        self._component = component

    def __getattr__(self, name: str):
        if name == '_component':
            raise AttributeError('_component not set')
        return getattr(self._component, name)

    @property
    def full_name(self):
        if isinstance(self._component, BaseComponent):
            return self._component.full_name
        else:
            return f"Tokenizer:{self._component.__class__.__name__}"

    def __repr__(self):
        return f"{self.__class__.__name__}({self._component!r})"


class BaseTimedComponent(Protocol):

    def __call__(self, doc: MutableDocument) -> MutableDocument:
        pass


class BaseTimedTokenizer(Protocol):

    def __call__(self, text: str) -> MutableDocument:
        pass

class TimedComponentProtocol(BaseTimedObjectProtocol, BaseTimedComponent, Protocol):
    pass

class TimedTokenizerProtocol(BaseTimedObjectProtocol, BaseTimedTokenizer, Protocol):
    pass


class PerDocTimedObject(BaseTimedObject):

    def time_it(self, to_run: Callable[[], MutableDocument]) -> MutableDocument:
        start = time.perf_counter()
        result = to_run()
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info("Component %s took %.3fms", self.full_name, elapsed_ms)
        return result


class TimedComponent(PerDocTimedObject):
    """Wraps a component and logs the time spent in it."""

    def __init__(self, component: BaseComponent,
                 ) -> None:
        super().__init__(component)
        self._component: BaseComponent

    def __call__(self, doc: MutableDocument) -> MutableDocument:
        return self.time_it(lambda: self._component(doc))


class TimedTokenizer(PerDocTimedObject):

    def __init__(self, component: BaseTokenizer,
                 ) -> None:
        super().__init__(component)
        self._component: BaseTokenizer

    def __call__(self, text: str) -> MutableDocument:
        return self.time_it(lambda: self._component(text))


class AveragingTimedObject(BaseTimedObject):

    def __init__(self, component: Union[BaseComponent, BaseTokenizer],
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
        logger.info("Component %s took (min/mean/median/max): "
                    "%.3fms / %.3fms / %.3fms / %.3fms "
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


class AveragingTimedComponent(AveragingTimedObject):

    def __init__(self, component: BaseComponent,
                 condition: Callable[[int, float], bool]
                 ) -> None:
        super().__init__(component, condition)
        self._component: BaseComponent

    def __call__(self, doc: MutableDocument) -> MutableDocument:
        start = time.perf_counter()
        result = self._component(doc)
        elapsed_ms = (time.perf_counter() - start) * 1000
        self._maybe_show_time(elapsed_ms)
        return result


class AveragingTimedTokenizer(AveragingTimedObject):

    def __init__(self, component: BaseTokenizer,
                 condition: Callable[[int, float], bool]
                 ) -> None:
        super().__init__(component, condition)
        self._component: BaseTokenizer

    def __call__(self, text: str) -> MutableDocument:
        start = time.perf_counter()
        result = self._component(text)
        elapsed_ms = (time.perf_counter() - start) * 1000
        self._maybe_show_time(elapsed_ms)
        return result


class ProfiledObject(BaseTimedObject):

    def __init__(self, component: Union[BaseComponent, BaseTokenizer]):
        super().__init__(component)
        self._profiler = cProfile.Profile()

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


class ProfiledComponent(ProfiledObject):

    def __init__(self, component: BaseComponent,
                 ) -> None:
        super().__init__(component)
        self._component: BaseComponent

    def __call__(self, doc: MutableDocument) -> MutableDocument:
        self._profiler.enable()
        result = self._component(doc)
        self._profiler.disable()
        return result


class ProfiledTokenizer(ProfiledObject):

    def __init__(self, component: BaseTokenizer,
                 ) -> None:
        super().__init__(component)
        self._component: BaseTokenizer

    def __call__(self, text: str) -> MutableDocument:
        self._profiler.enable()
        result = self._component(text)
        self._profiler.disable()
        return result


@context_manager_with_logging
def pipeline_per_doc_timer(
        pipeline: Pipeline,
        timer_init: Callable[[BaseComponent],
                             TimedComponentProtocol] = TimedComponent,
        tknzer_timer_init: Callable[[BaseTokenizer],
                                    TimedTokenizerProtocol] = TimedTokenizer,
    ):
    """Time the pipeline on a per document basis.

    Args:
        pipeline (Pipeline): The pipeline to time.
        timer_init (Callable[[BaseComponent], TimedComponentProtocol])): The
            initialiser for the timer. Defaults to TimedComponent.
        tknzer_timer_init (Callable[[BaseTokenizer], TimedTokenizerProtocol): The
            initialiser for the timer for the tokenizer. Defaults to TimedTokenizer.

    Yields:
        Pipeline: The same pipeline.
    """
    original_tokenizer = pipeline._tokenizer
    original_components = pipeline._components
    original_addons = pipeline._addons

    updated_core_components = [
        cast(CoreComponent, timer_init(c))
        for c in original_components]
    updated_addons = [
        cast(AddonComponent, timer_init(a))
        for a in original_addons]

    pipeline._tokenizer = cast(
        BaseTokenizer, tknzer_timer_init(original_tokenizer))
    pipeline._components = updated_core_components
    pipeline._addons = updated_addons

    try:
        yield pipeline
    finally:
        pipeline._tokenizer = original_tokenizer
        pipeline._components = original_components
        pipeline._addons = original_addons


@context_manager_with_logging
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

    original_tokenizer = pipeline._tokenizer
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
    wrapped_tokenizer = AveragingTimedTokenizer(
            original_tokenizer, wrapper_condition)

    pipeline._tokenizer = wrapped_tokenizer  # type: ignore
    pipeline._components = wrapped_core_comps  # type: ignore
    pipeline._addons = wrapped_addons  # type: ignore

    try:
        yield pipeline
    finally:
        pipeline._tokenizer = original_tokenizer
        pipeline._components = original_components
        pipeline._addons = original_addons
        timed_objects: list[AveragingTimedObject] = [
            wrapped_tokenizer, *wrapped_core_comps, *wrapped_addons
        ]

        for comp in timed_objects:
            if comp._to_average:
                comp._show_time()
                comp._reset()


@context_manager_with_logging
def profile_pipeline_component(
        pipeline: Pipeline,
        comp_type: Union[CoreComponentType, Type[AddonType], Literal['tokenizer']],
        limit: int = 20,
    ):
    """Time a specific component of the pipeline.

    This can profile either a core component or an addon component.
    But notably, in case of addon components, all components of the
    same type will be profiled.

    Args:
        pipeline (Pipeline): The pipeline to time.
        comp_type (Union[CoreComponentType, Type[AddonType], Literal['tokenizer']]):
            The type of component to profile. This can be either a core component
            or an addon component, ot the tokenizer.
        limit (int): The number of function calls to show in output.
            Defaults to 20.

    Yields:
        Pipeline: The same pipeline.
    """
    original_tokenizer = pipeline._tokenizer
    original_components = pipeline._components
    original_addons = pipeline._addons

    updated_addons: list[AddonComponent]
    updated_core_comps: list[CoreComponent]
    if isinstance(comp_type, CoreComponentType):
        updated_tokenizer = original_tokenizer
        changed_comp = pipeline.get_component(comp_type)
        updated_core_comps = [
            comp if comp != changed_comp else
            cast(CoreComponent, ProfiledComponent(changed_comp))
            for comp in original_components
        ]
        updated_addons = original_addons
    elif comp_type == 'tokenizer':
        updated_tokenizer = cast(BaseTokenizer, ProfiledTokenizer(original_tokenizer))
        updated_core_comps = original_components
        updated_addons = original_addons
    else:
        updated_tokenizer = original_tokenizer
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
        comp for comp in updated_core_comps + updated_addons + [updated_tokenizer,]
        if isinstance(comp, ProfiledObject)
    ]

    pipeline._tokenizer = updated_tokenizer
    pipeline._components = updated_core_comps
    pipeline._addons = updated_addons

    try:
        yield pipeline
    finally:
        pipeline._tokenizer = original_tokenizer
        pipeline._components = original_components
        pipeline._addons = original_addons
        for comp in profiled_comps:
            comp.show_stats(limit)
