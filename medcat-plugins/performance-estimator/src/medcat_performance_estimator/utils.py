from collections.abc import Callable
from functools import lru_cache
from typing import Any


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
