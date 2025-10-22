from typing import Union, Optional, cast

from medcat.cat import CAT
from medcat.utils.defaults import DEFAULT_PACK_NAME
from medcat.storage.serialisers import AvailableSerialisers
from medcat.trainer import Trainer
from medcat.data.mctexport import MedCATTrainerExport

from medcat_den.base import ModelInfo
from medcat_den.config import DenConfig, RemoteDenConfig


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
    _den_cnf: DenConfig

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
        if (is_injected_for_save() and isinstance(
                self._den_cnf, RemoteDenConfig) and
                not self._den_cnf.allow_push_fine_tuned):
            # NOTE: should there be a check whether this is a base model?
            raise CannotSendToRemoteException(
                "Cannot save fine-tuned model onto a remote den."
                "In order to make full use of the remote den capabilities, "
                "use the den API to fine tune a model directly on the den. "
                "See `Den.finetune_model` for details or set the config "
                "option of `allow_push_fine_tuned` to True"
            )
        return super().save_model_pack(
            target_folder, pack_name, serialiser_type, make_archive,
            only_archive, add_hash_to_pack_name, change_description)

    @property
    def trainer(self) -> Trainer:
        tr = super().trainer
        return WrappedTrainer(self._den_cnf, tr)

    @classmethod
    def load_model_pack(cls, model_pack_path: str,
                        config_dict: Optional[dict] = None,
                        addon_config_dict: Optional[dict[str, dict]] = None,
                        model_info: Optional[ModelInfo] = None,
                        den_cnf: Optional[DenConfig] = None,
                        ) -> 'CAT':
        """Load the model pack from file.

        This may also disallow model load from disk in certain secnarios.

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
            den_cnf: (Optional[DenConfig]): The config for the den being
                used. Should not be left None.


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
        if den_cnf is None:
            raise CannotWrapModel("den_cnf must be provided")
        cat._model_info = model_info
        cat._den_cnf = den_cnf
        return cat


class WrappedTrainer(Trainer):

    def __init__(self, den_cnf: DenConfig, delegate: Trainer):
        super().__init__(delegate.cdb, delegate.caller, delegate._pipeline)
        self._den_cnf = den_cnf

    def train_supervised_raw(
            self, data: MedCATTrainerExport, reset_cui_count: bool = False,
            nepochs: int = 1, print_stats: int = 0, use_filters: bool = False,
            terminate_last: bool = False, use_overlaps: bool = False,
            use_cui_doc_limit: bool = False, test_size: float = 0,
            devalue_others: bool = False, use_groups: bool = False,
            never_terminate: bool = False,
            train_from_false_positives: bool = False,
            extra_cui_filter: Optional[set[str]] = None,
            disable_progress: bool = False, train_addons: bool = False):
        if (isinstance(self._den_cnf, RemoteDenConfig) and
                not self._den_cnf.allow_local_fine_tune):
            raise NotAllowedToFineTuneLocallyException(
                "You are not allowed to fine-tune remote models locally. "
                "Please use the `Den.finetune_model` method directly to "
                "fine tune on the remote den, or if required, set the "
                "`allow_local_fine_tune` config value to `True`."
            )
        return super().train_supervised_raw(
            data, reset_cui_count, nepochs, print_stats, use_filters,
            terminate_last, use_overlaps, use_cui_doc_limit, test_size,
            devalue_others, use_groups, never_terminate,
            train_from_false_positives, extra_cui_filter, disable_progress,
            train_addons)


class CannotWrapModel(ValueError):

    def __init__(self, *args):
        super().__init__(*args)


class CannotSaveOnDiskException(ValueError):

    def __init__(self, *args):
        super().__init__(*args)


class CannotSendToRemoteException(ValueError):

    def __call__(self, *args):
        return super().__call__(*args)


class NotAllowedToFineTuneLocallyException(ValueError):

    def __call__(self, *args):
        return super().__call__(*args)
