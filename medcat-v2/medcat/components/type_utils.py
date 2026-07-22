import warnings
from .types import TrainableComponent, TrainingExample, BatchTrainableComponent


class _LegacyBatchAdapter:
    """Wraps an old-style TrainableComponent so it looks like a
    BatchTrainableComponent to the rest of the codebase."""
    def __init__(self, component: TrainableComponent):
        self._component = component

    def train_supervised_batch(self, examples: list[TrainingExample]) -> None:
        for ex in examples:
            for _ in range(ex.epochs):
                self._component.train(ex.cui, ex.entity, ex.doc, ex.negative)


def as_batch_trainable(component) -> BatchTrainableComponent:
    if isinstance(component, BatchTrainableComponent):
        return component
    if isinstance(component, TrainableComponent):
        _warn_legacy_once(type(component))
        return _LegacyBatchAdapter(component)
    raise TypeError(f"{component!r} does not support training")


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
