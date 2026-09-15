from typing import Callable, Iterable, TypeVar, Sized

T = TypeVar("T")


def _callback_iterator_iterable(identifier: str, data_iterator: Iterable[T],
                                callback: Callable[[str, int], None]
                                ) -> Iterable[T]:
    count = 0
    try:
        for item in data_iterator:
            count += 1
            yield item
    finally:
        callback(identifier, count)


def callback_iterator(identifier: str, data_iterator: Iterable[T],
                      callback: Callable[[str, int], None]) -> Iterable[T]:
    """Get an iterable with callback function to identify number of items.

    If the data has a size (i.e list or dict), the length of the data will
    be reported before iteration.

    If the data doesn't have a size (i.e a generator), the number of items
    iterated will be reported after the iteration is done.

    Args:
        identifier (str): The identifier / name for the iterator.
        data_iterator (Iterable[T]): The iterator.
        callback (Callable[[str, int], None]): The callback method.

    Returns:
        Iterable[T]: The wrapped iterator.
    """
    if isinstance(data_iterator, Sized):
        callback(identifier, len(data_iterator))
        return data_iterator
    return _callback_iterator_iterable(identifier, data_iterator, callback)
