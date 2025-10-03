from typing import Protocol, Optional, runtime_checkable, Union

from medcat.cat import CAT
from medcat.data.mctexport import MedCATTrainerExport

from medcat_den.base import ModelInfo
from medcat_den.wrappers import CATWrapper
from medcat_den.backend import DenType


@runtime_checkable
class Den(Protocol):

    @property
    def den_type(self) -> DenType:
        """The type of the den.

        Returns:
            DenType: The den type.
        """
        pass

    def list_available_models(self) -> list[ModelInfo]:
        """List all available models.

        Returns:
            list[ModelInfo]: The list of models.
        """
        pass

    def list_available_base_models(self) -> list[ModelInfo]:
        """List all available base models.

        Returns:
            list[ModelInfo]: The available base models.
        """
        pass

    def list_available_derivative_models(self, model: ModelInfo
                                         ) -> list[ModelInfo]:
        """List the available derivative models for the given model info.

        Args:
            model (ModelInof): The base model.

        Returns:
            list[ModelInfo]: The available deriative models.
        """

    def fetch_model(self, model_info: ModelInfo) -> CATWrapper:
        """Fetch the specified model.

        Args:
            model_info (ModelInfo): The model info.

        Returns:
            CAT: The model pack.
        """
        pass

    def push_model(self, cat: CAT, description: str) -> None:
        """Push the model pack back to the remote.

        This may be able to take advantage of the initial model info
        of the model to determine some of the details.
        If that is not possible, it will be treated as a brand new base
        model.

        Args:
            cat (CAT): The model pack.
            description (str): The description of the changes.

        Raises:
            DuplicateModelException: If the model by this ID already exists.
        """
        pass

    def _push_model_from_file(self, file_path: str, description: str) -> None:
        """Internal method to push a model from a file.

        Normally, if you're pushhing to a remote den, the file needs to
        be saved to disk first (to serialise and archive it).

        So this method should be the one that is called after saving the
        model to disk and it should push the model to the remote storage.

        Args:
            file_path (str): The file path.
            description (str): The description of the changes.
        """

    def delete_model(self, model_info: ModelInfo,
                     allow_delete_base_models: bool = False) -> None:
        """Delete the specified model from the den.

        Unless `allow_delete_base_models=True` is provided,
        base models will noe be allowed to deleted.

        Args:
            model_info (ModelInfo): The model info for the model to delete.
            allow_delete_base_models (bool): Whether to allow base models to
                be deleted. Defaults to False.
        """
        pass

    def finetune_model(self, model_info: ModelInfo,
                       data: Union[list[str], MedCATTrainerExport]
                       ) -> ModelInfo:
        """Finetune the model on the remote den.

        This is an optional API that is (generally) only available
        for remote dens. The idea is that the data is sent to the remote
        den and the finetuning is done on the remote.

        If raw data is given, unless already present remotely, it will be
        uploaded to the remote den.

        Args:
            model_info (ModelInfo): The model info
            data (Union[list[str], MedCATTrainerExport]): The list of project
                ids (already on remote) or the trainer export to train on.

        Returns:
            ModelInfo: The resulting model.

        Raises:
            UnsupportedAPIException: If the den does not support this API.
        """

    def evaluate_model(self, model_info: ModelInfo,
                       data: Union[list[str], MedCATTrainerExport]) -> dict:
        """Evaluate model on remote den.

        This is an optional API that is (generally) only available
        for remote dens. The idea is that the data is sent to the remote
        den and the metrics are gathered on the remote.

        If raw data is given, unless already present remotely, it will be
        uploaded to the remote den.

        Args:
            model_info (ModelInfo): The model info.
            data (Union[list[str], MedCATTrainerExport]): The list of project
                ids (already on remote) or the trainer export to train on.

        Returns:
            dict: The resulting metrics.
        """
        pass


class UnsupportedAPIException(ValueError):
    pass


def get_default_den(
        type_: Optional[DenType] = None,
        location: Optional[str] = None,
        host: Optional[str] = None,
        credentials: Optional[dict] = None,
        local_cache_path: Optional[str] = None,
        expiration_time: Optional[int] = None,
        max_size: Optional[int] = None,
        eviction_policy: Optional[str] = None,
        remote_allow_local_fine_tune: Optional[str] = None,
        remote_allow_push_fine_tuned: Optional[str] = None,
        ) -> Den:
    """Get the default den.

    This will resolve for the default den (either local or remote)
    based on both the explicit input as well as the environmental variables.
    The explicit input will override any environmental variable values.

    Some parameters may be ignored based on the den type (e.g location is not
    used for a remote den and host / credentials are not used for a local den).

    Args:
        type_ (Optional[DenType]): The den type. Defaults to LOCAL_USER.
        location (Optional[str]): The den location (for local). Defaults to
            OS-normalised user or site-specific data dir as required.
        host (Optional[str]): The host (for remote). Defaults to None.
        credentials (Optional[dict]): The credentials (for remote).
            Defaults to None.
        local_cache_path (Optional[str]): The path to use for local caching of
            remote dens. Defaults to None.
        expiration_time (Optional[int]): The expiration time for local cache.
        max_size (Optional[int]): The max size (in bytes) for local cache.
        eviction_policy (Optional[str]): The expiration policy for local cache.
            Policies avialable: LRU (`least-recently-used`),
                LRS (`least-recently-stored`), LFU (`least-frequently-used`),
                and `none` (disables evictions).
        remote_allow_local_fine_tune (Optional[str]): Whether to allow local
            fine tuning of remote models.
        remote_allow_push_fine_tuned (Optional[str]): Whether to allow pushing
            of locally fine-tuned models to the remote

    Returns:
        Den: The resolved den.
    """
    # NOTE: doing dynamic import to avoid circular imports
    from medcat_den.resolver import resolve
    return resolve(type_, location, host, credentials, local_cache_path,
                   expiration_time, max_size, eviction_policy,
                   remote_allow_local_fine_tune, remote_allow_push_fine_tuned)


def get_default_user_local_den(
        location: Optional[str] = None) -> Den:
    return get_default_den(DenType.LOCAL_USER, location=location)


def get_default_machine_local_den(
        location: Optional[str] = None) -> Den:
    return get_default_den(DenType.LOCAL_MACHINE, location=location)


class DuplicateModelException(ValueError):

    def __init__(self, *args):
        super().__init__(*args)
