from typing import Any, Union, Protocol, runtime_checkable, Iterable
from enum import Enum, auto


class SerialisingStrategy(Enum):
    """Describes the strategy for serialising."""
    SERIALISABLE_ONLY = auto()
    """Only serialise attributes that are of Serialisable type"""
    SERIALISABLES_AND_DICT = auto()
    """Serialise attributes that are Serialisable as well as
    the rest of .__dict__"""
    DICT_ONLY = auto()
    """Only include the object's .__dict__"""
    MANUAL = auto()
    """Use manual serialisation defined by the object itself.

    NOTE: In this case, most of the logic defined within here will
          likely be ignored.
    """

    def _is_suitable_in_dict(self, attr_name: str,
                             attr: Any, obj: 'Serialisable') -> bool:
        if attr_name in obj.ignore_attrs():
            return False
        if self == SerialisingStrategy.SERIALISABLE_ONLY:
            return False
        elif self == SerialisingStrategy.DICT_ONLY:
            return True
        elif self == SerialisingStrategy.SERIALISABLES_AND_DICT:
            return not isinstance(attr, Serialisable)
        else:
            raise ValueError(f"Unknown instance: {self}")

    def _is_suitable_part(self, attr_name: str, part: Any, obj: 'Serialisable'
                          ) -> bool:
        if attr_name in obj.ignore_attrs():
            return False
        if not isinstance(part, Serialisable):
            return False
        if self == SerialisingStrategy.SERIALISABLE_ONLY:
            return True
        elif self == SerialisingStrategy.DICT_ONLY:
            return False
        return True

    def _iter_obj_items(self, obj: 'Serialisable'
                        ) -> Iterable[tuple[str, Any]]:
        for attr_name, attr in obj.__dict__.items():
            if attr_name.startswith("__"):
                # ignore privates
                continue
            yield attr_name, attr

    def _iter_obj_values(self, obj: 'Serialisable') -> Iterable[Any]:
        for _, val in self._iter_obj_items(obj):
            yield val

    def get_dict(self, obj: 'Serialisable') -> dict[str, Any]:
        """Gets the appropriate parts of the __dict__ of the object.

        I.e this filters out parts that shouldn't be included.

        Args:
            obj (Serialisable): The serialisable object.

        Returns:
            dict[str, Any]: The filtered attributes map.
        """
        out_dict = {
            attr_name: attr for attr_name, attr in self._iter_obj_items(obj)
            if self._is_suitable_in_dict(attr_name, attr, obj)
        }
        # do properties
        # NOTE: these are explicitly declared, so suitability is not checked
        out_dict.update({
            property_name: getattr(obj, property_name)
            for property_name in obj.include_properties()
        })
        return out_dict

    def get_parts(self, obj: 'Serialisable'
                  ) -> list[tuple['Serialisable', str]]:
        """Gets the matching serialisable parts of the object.

        This includes only serialisable parts, and only if specified
        by the strategy.

        Returns:
            list[tuple[Serialisable, str]]: The serialisable parts with names.
        """
        out_list: list[tuple[Serialisable, str]] = [
            (attr, attr_name) for attr_name, attr in self._iter_obj_items(obj)
            if self._is_suitable_part(attr_name, attr, obj)
        ]
        return out_list


@runtime_checkable
class Serialisable(Protocol):
    """The base serialisable protocol."""

    def get_strategy(self) -> SerialisingStrategy:
        """Get the serialisation strategy.

        Returns:
            SerialisingStrategy: The strategy.
        """
        pass

    @classmethod
    def get_init_attrs(cls) -> list[str]:
        """Get the names of the arguments needed for init upon deserialisation.

        Returns:
            list[str]: The list of init arguments' names.
        """
        pass

    @classmethod
    def ignore_attrs(cls) -> list[str]:
        """Get the names of attributes not to serialise.

        Returns:
            list[str]: The attribute names that should not be serialised.
        """
        pass

    @classmethod
    def include_properties(cls) -> list[str]:
        pass


class AbstractSerialisable:
    """The abstract serialisable base class.

    This defines some common defaults.
    """

    def get_strategy(self) -> SerialisingStrategy:
        return SerialisingStrategy.SERIALISABLES_AND_DICT

    @classmethod
    def get_init_attrs(cls) -> list[str]:
        return []

    @classmethod
    def ignore_attrs(cls) -> list[str]:
        return []

    @classmethod
    def include_properties(cls) -> list[str]:
        return []

    def __eq__(self, other: Any) -> bool:
        if type(self) is not type(other):
            return False
        if set(self.__dict__) != set(other.__dict__):
            return False
        for attr_name, attr_value in self.__dict__.items():
            if not hasattr(other, attr_name):
                return False
            other_value = getattr(other, attr_name)
            if attr_value != other_value:
                return False
        return True


@runtime_checkable
class ManualSerialisable(Serialisable, Protocol):

    def serialise_to(self, folder_path: str) -> None:
        """Serialise to a folder.

        Args:
            folder_path (str): The folder to serialise to.
        """
        pass

    @classmethod
    def deserialise_from(cls, folder_path: str, **init_kwargs
                         ) -> 'ManualSerialisable':
        """Deserialise from a specifc path.

        The init keyword arguments are generally:
        - cnf: The config relevant to the components
        - tokenizer (BaseTokenizer): The base tokenizer for the model
        - cdb (CDB): The CDB for the model
        - vocab (Vocab): The Vocab for the model
        - model_load_path (Optional[str]): The model load path,
            but not the component load path

        Args:
            folder_path (str): The path to deserialsie form.

        Returns:
            ManualSerialisable: The deserialised object.
        """
        pass


class AbstractManualSerialisable:

    def get_strategy(self) -> SerialisingStrategy:
        return SerialisingStrategy.MANUAL

    @classmethod
    def get_init_attrs(cls) -> list[str]:
        return []

    @classmethod
    def ignore_attrs(cls) -> list[str]:
        return []

    @classmethod
    def include_properties(cls) -> list[str]:
        return []


def name_all_serialisable_elements(target_list: Union[list, tuple],
                                   name_start: str = '',
                                   all_or_nothing: bool = True
                                   ) -> list[tuple[Serialisable, str]]:
    """Gets all serialisable elements from a list or tuple.

    There's two strategies for finding the parts:
    1) If `all_or_nothing == True` either all the elements
        in the list must be Serialisable or None of them.
    2) If `all_or_nothing == False` some elements may be
        serialisable while others may not be.

    Args:
        target_list (Union[list, tuple]): The list/tuple of objects to look in.
        name_start (str, optional): The start of the name. Defaults to ''.
        all_or_nothing (bool, optional):
            Whether to disallow lists/tuple where only some elements are
            serialisable. Defaults to True.

    Raises:
        ValueError: If `all_or_nothing` is specified and not all elements
            are serialisable.

    Returns:
        list[tuple[Serialisable, str]]: The serialisable parts along with name.
    """
    out_parts: list[tuple[Serialisable, str]] = []
    if not target_list:
        return out_parts
    for el_nr, el in enumerate(target_list):
        if isinstance(el, Serialisable):
            out_parts.append((el, name_start + f"_el_{el_nr}"))
        elif all_or_nothing and out_parts:
            raise ValueError(f"The first {len(out_parts)} were serialisable "
                             "whereas the next one was not. Specify "
                             "`all_or_nothing=False` to allow for only "
                             "some of the list elements to be serialisable.")
    return out_parts


def get_all_serialisable_members(object: Serialisable
                                 ) -> tuple[list[tuple[Serialisable, str]],
                                            dict[str, Any]]:
    """Gets all serialisable members of an object.

    This looks for public and protected members, but not private ones.
    It should also be able to return parts of lists and tuples.
    It also provides the name of each serialisable object.

    Args:
        object (Any): The target object.

    Returns:
        tuple[list[tuple[Serialisable, str]], dict[str, Any]]:
            list of serialisable objects along with their names
    """
    strat = object.get_strategy()
    return strat.get_parts(object), strat.get_dict(object)
