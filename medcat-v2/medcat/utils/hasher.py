from typing import Any, Callable

import xxhash
import dill
from io import BytesIO as StringIO


def dumps(obj: Any, length: bool = False) -> bytes:
    """Dump the content of an object to bytes.

    This method uses dill to dump the contents of an
    object into a BytesIO object and then either
    reads its bytes or (or length == True) simply
    reruns the process on the length of the byte array.

    Args:
        obj (Any): The object to dump.
        length (bool, optional):
            Whether to only dump the length of the file array.
            Defaults to False.

    Returns:
        bytes: The resulting byte array.
    """
    with StringIO() as file:
        dill.dump(obj, file, recurse=True)
        if length:
            return dumps(len(file.getvalue()), length=False)
        else:
            return file.getvalue()


class Hasher:
    """A consistent hasher.

    This class is able to hash the same object(s) to the
    same value every time.
    This is in contrast to the normal hashing in python
    that does not guarantee identical results over multiple
    runs.

    Args:
        dumper (Callable[[Any, bool], bytes], optional):
            The dumper to be used. Defaults to the `dumps` method.
    """

    def __init__(self, dumper: Callable[[Any, bool], bytes] = dumps):
        self.m = xxhash.xxh64()
        self._dumper = dumper

    def update(self, obj: Any, length: bool = False) -> None:
        """Update the hasher with the object in question.

        If `length = True` is passed, only the length of
        the byte array corresponding to the data is considered
        Otherwise the entire byte array is used.

        Args:
            obj (Any): The object to be added / hashed.
            length (bool, optional):
                Whether to only dump the length of the file array.
                Defaults to False.
        """
        self.m.update(self._dumper(obj, length))

    def update_bytes(self, b: bytes) -> None:
        """Update the hasher with a byte array.

        Args:
            b (bytes): The byte array to update with.
        """
        self.m.update(b)

    def hexdigest(self) -> str:
        """Get the hex for the current hash state.

        Returns:
            str: The hex representation of the hashed objects.
        """
        return self.m.hexdigest()
