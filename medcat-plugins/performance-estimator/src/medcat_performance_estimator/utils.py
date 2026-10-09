import math
from collections.abc import Callable
from functools import lru_cache
from typing import Any

import numpy as np


class method_lru_cache:
    """This class acts a replacement for the regular lru_cache.

    The idea is taht we have a separate cache for each instance.
    That way, we can have the instance(s) be garbage collected
    since otherwise the global cache would keep the instances
    referenced until it's explicitly cleared.
    """

    def __init__(self, maxsize=128, typed=False):
        self.maxsize = maxsize
        self.typed = typed
        self.func: Callable[[...], Any]

    def __call__(self, func):
        self.func = func
        return self

    def __get__(self, instance, owner=None):
        if instance is None:
            return self

        # Wrap the function as an lru_cache bound to this instance
        bound_func = lru_cache(maxsize=self.maxsize, typed=self.typed)(
            self.func.__get__(instance, owner)
        )

        # Store on the instance so descriptor lookup is skipped on future calls
        setattr(instance, self.func.__name__, bound_func)
        return bound_func



def damped_count(count: int, use_log_damping: bool) -> float:
    """Compress large counts so no single concept's exposure dominates.

    Mirrors the log-damping used for entity-linking mention-entity priors:
    without this, a concept trained 50,000 times vs. one trained 500 times
    would swing `relative_mass` by 100x for what's often a much smaller
    real difference in how "available" each concept is to the model.
    """
    if use_log_damping:
        return math.log1p(count)
    return float(count)


def count_confidence(count: int, k: float) -> float:
    """Saturating confidence weight in [0, 1) from a raw training count.

    `k` is the count at which confidence reaches exactly 0.5 -- e.g. with
    k=20, a concept trained 20 times gets confidence 0.5, trained 200 times
    gets confidence ~0.91. count=0 always gives exactly 0.0, which is the
    property that makes the untrained-model case reduce exactly to the
    ontology-only estimate.
    """
    if count <= 0:
        return 0.0
    return count / (count + k)


def relative_mass(
    target_count: int,
    other_count: int,
    use_log_damping: bool,
    max_relative_mass: float,
) -> float:
    """How much more "available" a competitor is than the target concept,
    based on relative training exposure alone (no ontology, no vectors).

    Returns 1.0 when both counts are equal (including both zero, which is
    exactly the untrained-model case -- this leaves stage-1 confusability
    weights completely unchanged). Clipped to avoid one wildly overrepresented
    competitor dominating the whole estimate.
    """
    target_mass = damped_count(target_count, use_log_damping) + 1.0
    other_mass = damped_count(other_count, use_log_damping) + 1.0
    ratio = other_mass / target_mass
    return min(ratio, max_relative_mass)


def combine_context_vector(
    vectors: dict[str, np.ndarray],
    weights: dict[str, float],
    default_size: int = 300,
) -> np.ndarray:
    """Combine the small/medium/large/xlarge context vectors into one,
    using `config.components.linking.context_vector_weights`.

    Only combines over window sizes actually present for this concept
    (a low-count concept may be missing some window sizes entirely) and
    renormalises over whichever weights were actually used, rather than
    assuming all four are always present.
    """
    used_weight = 0.0
    combined: np.ndarray | None = None
    for window, vec in vectors.items():
        w = weights.get(window)
        if w is None or w <= 0:
            continue
        combined = vec * w if combined is None else combined + vec * w
        used_weight += w

    if combined is None or used_weight <= 0:
        return np.zeros(default_size)
    return combined / used_weight
