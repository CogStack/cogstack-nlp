import warnings
import logging
from .types import (
    TrainableComponent, TrainingExample, BatchTrainableComponent,
    BaseComponent)
from medcat.tokenizing.tokens import MutableEntity


logger = logging.getLogger(__name__)


class _LegacyBatchAdapter:
    """Wraps an old-style TrainableComponent so it looks like a
    BatchTrainableComponent to the rest of the codebase."""

    def __init__(self, component: TrainableComponent):
        self._component = component
        # NOTE: cannot know for certain, really
        self.strict_train = False

    def train_supervised_batch(self, examples: list[TrainingExample]) -> None:
        for ex in examples:
            for _ in range(ex.epochs):
                try:
                    self._component.train(
                        ex.cui, ex.entity, ex.doc, ex.negative)
                except (ValueError, KeyError) as ve:
                    doc_text = ex.doc.base.text
                    value = ex.entity.base.text.lower().replace(" ", "~")
                    warn_on_error(
                        ve, doc_text,
                        (ex.cui, value, ex.entity.base.start_char_index,
                         ex.entity.base.end_char_index),
                        (ex.entity, "Unknown", "Unknown"), self.strict_train)


def warn_on_error(
    ve: BaseException,
    cur_text: str,
    mut_context_start: tuple[str, str, int, int],
    mut_context_end: tuple[MutableEntity | None, str, str],
    strict_train: bool,
):
    msg_template, msg_context = get_warn_context(
        cur_text, mut_context_start, mut_context_end)
    if strict_train:
        raise ValueError(msg_template % msg_context) from ve
    else:
        logger.warning(msg_template, *msg_context, exc_info=ve)


def get_warn_context(
    cur_text: str,
    mut_context_start: tuple[str, str, int, int],
    mut_context_end: tuple[MutableEntity | None, str, str]
) -> tuple[str, tuple[str, str, int, int, str, MutableEntity | None, str, str]]:
    start, end = mut_context_start[2:]
    context_window = 20  # characters
    splitter_left, splitter_right = "<", ">"
    context_start = max(start - context_window, 0)
    context_end = min(end + context_window, len(cur_text) - 1)
    context = (
        cur_text[context_start: start] +
        splitter_left +
        cur_text[start: end] +
        splitter_right +
        cur_text[end: context_end]
    )
    if context_start > 0:
        context = "[...]" + context
    if context_end < len(cur_text) - 1:
        context += "[...]"
    msg_template = (
        "Failed to identify '%s' (%s) ([%d:%d]) "
        "in '%s' %s within document %s | %s, "
        "skipping training for this example")
    msg_context = (
        *mut_context_start, context, *mut_context_end)
    return msg_template, msg_context


def as_batch_trainable(component: BaseComponent) -> BatchTrainableComponent:
    if isinstance(component, BatchTrainableComponent):
        return component
    if isinstance(component, TrainableComponent):
        # NOTE: this is where we can (in the future) raise instead
        #       if/when we decide to not support the old protocol
        _warn_legacy_once(type(component))
        return _LegacyBatchAdapter(component)
    raise TypeError(f"{component!r} does not support training")


def is_supervised_trainable(component: BaseComponent) -> bool:
    try:
        as_batch_trainable(component)
        return True
    except TypeError:
        return False


_warned_classes: set[type] = set()


def _warn_legacy_once(cls: type) -> None:
    if cls not in _warned_classes:
        _warned_classes.add(cls)
        warnings.warn(
            f"{cls.__name__} implements the legacy TrainableComponent.train() "
            "interface. This will be removed in a future release; implement "
            "BatchTrainableComponent.train_supervised_batch() instead.",
            DeprecationWarning,
            stacklevel=2,
        )
