from typing import Union, Optional, cast

from medcat.cat import CAT
from medcat.utils.defaults import DEFAULT_PACK_NAME
from medcat.storage.serialisers import AvailableSerialisers

from medcat_den.base import ModelInfo


class CATWrapper(CAT):
    """A wrapper for the medcat.cat.CAT class.

    The idea is to not allow the model to be saved on disk.
    This is because the class is supposed to used with a remote
    back end for storage. And saving files on disk would be counter-
    productive for this use case.

    In order to save the model to disk, you need to explicitly pass
    `force_save_local=True`. But that is generally not advised.
    """

    _model_info: ModelInfo

    def save_model_pack(
            self, target_folder: str, pack_name: str = DEFAULT_PACK_NAME,
            serialiser_type: Union[str, AvailableSerialisers] = 'dill',
            make_archive: bool = True,
            only_archive: bool = False,
            add_hash_to_pack_name: bool = True,
            change_description: Optional[str] = None,
            force_save_local: bool = False,
            ) -> str:
        """Attempt save model pack.

        This method will not allow you to save the model pack on disk
        unless you specify `force_save_local=True`.

        For most of the API see medcat.cat.CAT.

        Args:
            force_save_local (bool): Force saving model to disk.
                Defaults to False.

        Raises:
            CannotSaveOnDiskException: If there's an attempt to save the
                model on disk without an explicit `force_save_local=True`.

        Returns:
            str: The model pack.
        """
        # NOTE: dynamic import to avoid circular imports
        from medcat_den.injection.medcat_injector import is_injected_for_save
        # NOTE: if injected for save, allow saving on disk
        if not force_save_local and not is_injected_for_save():
            raise CannotSaveOnDiskException(
                f"Cannot save model on disk: {CATWrapper.__doc__}")
        return super().save_model_pack(
            target_folder, pack_name, serialiser_type, make_archive,
            only_archive, add_hash_to_pack_name, change_description)

    @classmethod
    def load_model_pack(cls, model_pack_path: str,
                        config_dict: Optional[dict] = None,
                        addon_config_dict: Optional[dict[str, dict]] = None,
                        model_info: Optional[ModelInfo] = None,
                        ) -> 'CAT':
        """Load the model pack from file.

        This also

        Args:
            model_pack_path (str): The model pack path.
            config_dict (Optional[dict]): The model config to
                merge in before initialising the pipe. Defaults to None.
            addon_config_dict (Optional[dict]): The Addon-specific
                config dict to merge in before pipe initialisation.
                If specified, it needs to have an addon dict per name.
                For instance, `{"meta_cat.Subject": {}}` would apply
                to the specific MetaCAT.
            model_inof (Optional[ModelInfo]): The base model info based on
                which the model was originally fetched. Should not be
                left None.

        Raises:
            ValueError: If the saved data does not represent a model pack.
            CannotWrapModel: If no model info is provided.

        Returns:
            CAT: The loaded model pack.
        """
        _cat = super().load_model_pack(
            model_pack_path, config_dict, addon_config_dict)
        cat = cast(CATWrapper, _cat)
        if not isinstance(cat, CATWrapper):
            cat.__class__ = CATWrapper
        if model_info is None:
            raise CannotWrapModel("Model info must be provided")
        cat._model_info = model_info
        return cat


class CannotWrapModel(ValueError):

    def __init__(self, *args):
        super().__init__(*args)


class CannotSaveOnDiskException(ValueError):

    def __init__(self, *args):
        super().__init__(*args)
