from typing import Callable, Union, Optional
import logging
from functools import partial
from contextlib import contextmanager
import inspect

from medcat.cat import CAT
from medcat.utils.defaults import DEFAULT_PACK_NAME

from medcat_den.den import get_default_den, Den
from medcat_den.base import ModelInfo


_ORIG_CAT_LOAD_MODEL_PACK = CAT.load_model_pack
_ORIG_CAT_SAVE_MODEL_PACK = CAT.save_model_pack


logger = logging.getLogger(__name__)


def _is_already_in_stack(module_name: Optional[str] = None):
    # Start from 2nd alement. The first 2 are this method and the calling
    # method. Because otherwise the calling method is always in scope
    stack = inspect.stack()
    # get calling method name from stack
    target_func_name: str = stack[1].function
    for frame in stack[2:]:
        if frame.function == target_func_name:
            if (module_name is None or
                    frame.frame.f_globals.get("__name__") == module_name):
                return True
    return False


def injected_load_model_pack(model_pack_name: str,
                             *args,
                             prefix: str,
                             den: Den,
                             model_name_mapper: Optional[Union[
                                 Callable[[str], str], dict[str, str]]] = None,
                             **kwargs,
                             ) -> CAT:
    # check stack - to avoid infinite recursion
    if _is_already_in_stack(__name__):
        return _ORIG_CAT_LOAD_MODEL_PACK(model_pack_name, *args, **kwargs)
    if prefix and not model_pack_name.startswith(prefix):
        # pass back to original method
        logger.info("Loading model directoy off of disk: %s", model_pack_name)
        return _ORIG_CAT_LOAD_MODEL_PACK(model_pack_name, *args, **kwargs)
    if prefix:
        model_pack_name = model_pack_name.removeprefix(prefix)
    if model_name_mapper:
        if isinstance(model_name_mapper, dict):
            model_id = model_name_mapper.get(model_pack_name, model_pack_name)
        else:
            model_id = model_name_mapper(model_pack_name)
    else:
        model_id = model_pack_name
    logger.info("Loading model by ID '%s' (named '%s')",
                model_id, model_pack_name)
    return den.fetch_model(ModelInfo(
        model_id=model_id, model_card=None, base_model=None))


def is_injected_for_save() -> bool:
    """Checks whether medcat.cat.CAT has been injected for saving.

    I.e if the injection is in place, allow saving through the
    `CAT.save_model_pack` method since that'll just save to den anyway.

    Returns:
        bool: Whether save-based injection is in play.
    """
    return CAT.save_model_pack is not _ORIG_CAT_SAVE_MODEL_PACK


def injected_save_model_pack(
                             prefix: str,
                             den: Den,
                             ):
    def _wrapper_method(cat: CAT,
                        target_folder: str,
                        pack_name: str = DEFAULT_PACK_NAME,
                        *args, **kwargs):
        if _is_already_in_stack(__name__):
            return _ORIG_CAT_SAVE_MODEL_PACK(cat, target_folder, pack_name,
                                             *args, **kwargs)
        if pack_name is DEFAULT_PACK_NAME:
            # use folder if no pack name passed (generally normal)
            pack_name = target_folder
        if prefix and not pack_name.startswith(prefix):
            # pass back to original method
            logger.info("Saving model directly to disk: %s/%s",
                        target_folder, pack_name)
            return _ORIG_CAT_SAVE_MODEL_PACK(cat, target_folder, pack_name,
                                             *args, **kwargs)
        description: str
        if "change_description" in kwargs:
            description = kwargs["change_description"]
        elif args and isinstance(args[-1], str):
            # use last positional argument
            description = args[-1]
        elif pack_name and pack_name is not DEFAULT_PACK_NAME:
            # use pack name (2nc argument) as description
            description = pack_name
        else:
            # use target folder (first argument) as description
            description = target_folder
        logger.info("Pushing model %s: %s", type(cat), cat)
        logger.info(" - with description: %s", repr(description))
        den.push_model(cat, description=description)
    return _wrapper_method


def inject_into_medcat(
        den_getter: Callable[[], Den] = get_default_den,
        model_name_mapper: Optional[Union[
            Callable[[str], str], dict[str, str]]] = None,
        prefix: str = '',
        inject_save: bool = False,
        ):
    """Inject MedCAT-Den into core library.

    This method injects the MedCAT-den functionatlity into the core library.
    That is, it allows the CAT.load_model_pack method to be used directly
    in order to load a model pack from a centralised (potentially remote)
    location.

    While the default behaviour is to expect a model ID (the hash) when loading
    a model pack, there is built in functionality for translating a model name
    to a hash.

    The default behaviour doesn't allow for any model pack loads off of disk.
    However, if a non-empty `prefix` is passed, names without the prefix will
    be loaded off of disk.

    Args:
        den_getter (Callable[[], Den]): The method to get the relevant den.
            Defaults to `get_default_den`.
        model_name_mapper (Optional[Union[Callable[[str], str],
            dict[str, str]]): The model name mapper (if specified). Can either
                be a dict based mapping or a function based one.
                Defaults to None.
        prefix (str): The prefix for the den-based models. If sepcified, names
            without a prefix will be loaded off disk locally, otherwise no
            local model loads will be allowed. Defaults to ''.
        inject_save (bool): Whether to also inject saving of models. If
            specified, models will also be pushed back to the den at save time
            (i.e when calling CAT.save_model_pack). Defaults to False.
    """
    den = den_getter()
    CAT.load_model_pack = partial(  # type: ignore
        injected_load_model_pack, den=den,
        model_name_mapper=model_name_mapper,
        prefix=prefix)
    if inject_save:
        CAT.save_model_pack = (  # type: ignore
            injected_save_model_pack(
                den=den,
                prefix=prefix))


def uninject_into_medcat():
    """Undo the injection into MedCAT."""
    logger.info("Undoing injection")
    CAT.load_model_pack = _ORIG_CAT_LOAD_MODEL_PACK
    CAT.save_model_pack = _ORIG_CAT_SAVE_MODEL_PACK


@contextmanager
def injected_den(
        den_getter: Callable[[], Den] = get_default_den,
        model_name_mapper: Optional[Union[
            Callable[[str], str], dict[str, str]]] = None,
        prefix: str = '',
        inject_save: bool = False,
        ):
    """A context manager for injecting into MedCAT.

    This allows the injection to be active temporarily.
    See `inject_int_medcat` for all the details.

    Args:
        den_getter (Callable[[], Den]): The method to get the relevant den.
            Defaults to `get_default_den`.
        model_name_mapper (Optional[Union[Callable[[str], str],
            dict[str, str]]): The model name mapper (if specified). Can either
                be a dict based mapping or a function based one.
                Defaults to None.
        prefix (str): The prefix for the den-based models. If sepcified, names
            without a prefix will be loaded off disk locally, otherwise no
            local model loads will be allowed. Defaults to ''.
        inject_save (bool): Whether to also inject saving of models. If
            specified, models will also be pushed back to the den at save time
            (i.e when calling CAT.save_model_pack). Defaults to False.
    """
    inject_into_medcat(den_getter=den_getter,
                       model_name_mapper=model_name_mapper,
                       prefix=prefix, inject_save=inject_save)
    try:
        yield
    finally:
        uninject_into_medcat()
