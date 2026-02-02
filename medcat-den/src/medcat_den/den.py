from typing import Protocol, Optional, runtime_checkable, Union
import logging

from medcat.cat import CAT
from medcat.data.mctexport import MedCATTrainerExport

from medcat_den.base import ModelInfo
from medcat_den.wrappers import CATWrapper
from medcat_den.backend import DenType


logger = logging.getLogger(__name__)

@runtime_checkable
class DenBackend(Protocol):

    @property
    def den_type(self) -> DenType:
        """The type of the den.

        Returns:
            DenType: The den type.
        """
        pass

    def list_available_models(
            self, backend_name: Optional[str] = None) -> list[ModelInfo]:
        """List all available models.

        Args:
            backend_name (Optional[str]): The backend name for multi-back end dens.
                Defaults to None.

        Returns:
            list[ModelInfo]: The list of models.
        """
        pass

    def list_available_base_models(
            self, backend_name: Optional[str] = None) -> list[ModelInfo]:
        """List all available base models.

        Args:
            backend_name (Optional[str]): The backend name for multi-back end dens.
                Defaults to None.

        Returns:
            list[ModelInfo]: The available base models.
        """
        pass

    def list_available_derivative_models(self, model: ModelInfo,
                                         backend_name: Optional[str] = None
                                         ) -> list[ModelInfo]:
        """List the available derivative models for the given model info.

        Args:
            model (ModelInof): The base model.
            backend_name (Optional[str]): The backend name for multi-back end dens.
                Defaults to None.

        Returns:
            list[ModelInfo]: The available deriative models.
        """

    def has_model(self, model: ModelInfo,
                  backend_name: Optional[str] = None) -> bool:
        """Whether the back end in question has the specified model.

        This method generally only compares the model ID / hash.

        Args:
            model (ModelInfo): The model info.
            backend_name (Optional[str]): The back end name. Defaults to None.

        Returns:
            bool: Whether the model is in the back end or not.
        """

    def fetch_model(self, model_info: ModelInfo,
                    backend_name: Optional[str] = None) -> CATWrapper:
        """Fetch the specified model.

        Args:
            model_info (ModelInfo): The model info.
            backend_name (Optional[str]): The backend name for multi-back end dens.
                Defaults to None.

        Returns:
            CAT: The model pack.
        """
        pass

    def push_model(self, cat: CAT, description: str,
                   backend_name: Optional[str] = None,
                   push_unchanged: bool = False) -> None:
        """Push the model pack back to the remote.

        This may be able to take advantage of the initial model info
        of the model to determine some of the details.
        If that is not possible, it will be treated as a brand new base
        model.

        Args:
            cat (CAT): The model pack.
            description (str): The description of the changes.
            backend_name (Optional[str]): The backend name for multi-back end dens.
                Defaults to None.
            push_unchanged (bool). Whether to push with no canges. This can be useful
                when moving models between backends (i.e syncing). Defaults to False.

        Raises:
            DuplicateModelException: If the model by this ID already exists.
        """
        pass

    def _push_model_from_file(self, file_path: str, description: str,
                              backend_name: Optional[str] = None) -> None:
        """Internal method to push a model from a file.

        Normally, if you're pushhing to a remote den, the file needs to
        be saved to disk first (to serialise and archive it).

        So this method should be the one that is called after saving the
        model to disk and it should push the model to the remote storage.

        Args:
            file_path (str): The file path.
            description (str): The description of the changes.
            backend_name (Optional[str]): The backend name for multi-back end dens.
                Defaults to None.
        """

    def delete_model(self, model_info: ModelInfo,
                     allow_delete_base_models: bool = False,
                     backend_name: Optional[str] = None) -> None:
        """Delete the specified model from the den.

        Unless `allow_delete_base_models=True` is provided,
        base models will noe be allowed to deleted.

        Args:
            model_info (ModelInfo): The model info for the model to delete.
            allow_delete_base_models (bool): Whether to allow base models to
                be deleted. Defaults to False.
            backend_name (Optional[str]): The backend name for multi-back end dens.
                Defaults to None.
        """
        pass

    def finetune_model(self, model_info: ModelInfo,
                       data: Union[list[str], MedCATTrainerExport],
                       backend_name: Optional[str] = None
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
            backend_name (Optional[str]): The backend name for multi-back end dens.
                Defaults to None.

        Returns:
            ModelInfo: The resulting model.

        Raises:
            UnsupportedAPIException: If the den does not support this API.
        """

    def evaluate_model(self, model_info: ModelInfo,
                       data: Union[list[str], MedCATTrainerExport],
                       backend_name: Optional[str] = None) -> dict:
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
            backend_name (Optional[str]): The backend name for multi-back end dens.
                Defaults to None.

        Returns:
            dict: The resulting metrics.
        """
        pass

    def move_model(self, model_info: ModelInfo, origin: str, destination: str) -> None:
        """Move a model from the origin to the destination.

        This method is designed to only work with multiple back end and will likely
        raise an exception if used on a specific back end.

        Raises:
            NoSuchBackendException: If one of the back ends does not exist.
            NoSuchModel: If the model does not exist at the origin.
            UnsupportedAPIException: If called on a specific back end.
            DuplicateModelException: If the destination already has the model.

        Args:
            model_info (ModelInfo): The model in question.
            origin (str): The origin back end.
            destination (str): The destination back end.
        """
        pass


    def sync_backend(self, origin: str, destination: str) -> None:
        """Sync models from one backend to another.

        This method is designed to only work with multiple back end and will likely
        raise an exception if used on a specific back end.

        Raises:
            NoSuchBackendException: If one of the back ends does not exist.
            UnsupportedAPIException: If called on a specific back end.

        Args:
            origin (str): The origin back end.
            destination (str): The destination back end.
        """
        pass


class Den(DenBackend):

    def __init__(self, backends: dict[str, DenBackend], default_backend_name: str):
        if not backends:
            raise ValueError("Must provide at least one backend")
        if default_backend_name not in backends:
            raise ValueError(f"Default backend '{default_backend_name}' not found in provided backends")

        self._backends = backends
        self._default_backend_name = default_backend_name
        self._default_backend = self._backends[self._default_backend_name]

    def _get_backend(self, backend_name: Optional[str] = None) -> DenBackend:
        if backend_name is None:
            return self._default_backend
        if backend_name not in self._backends:
            raise ValueError(f"Backend '{backend_name}' not found")
        return self._backends[backend_name]

    @property
    def den_type(self) -> DenType:
        return DenType.MULTI_BACKEND

    def list_available_models(self, backend_name: Optional[str] = None) -> list[ModelInfo]:
        return self._get_backend(backend_name).list_available_models()

    def list_available_base_models(self, backend_name: Optional[str] = None) -> list[ModelInfo]:
        return self._get_backend(backend_name).list_available_base_models()

    def list_available_derivative_models(self, model: ModelInfo, backend_name: Optional[str] = None) -> list[ModelInfo]:
        return self._get_backend(backend_name).list_available_derivative_models(model)

    def has_model(self, model: ModelInfo,
                  backend_name: Optional[str] = None) -> bool:
        return self._get_backend(backend_name).has_model(model)

    def fetch_model(self, model_info: ModelInfo, backend_name: Optional[str] = None) -> CATWrapper:
        return self._get_backend(backend_name).fetch_model(model_info)

    def push_model(self, cat: CAT, description: str, backend_name: Optional[str] = None,
                   push_unchanged: bool = False) -> None:
        self._get_backend(backend_name).push_model(cat, description, push_unchanged=push_unchanged)

    def _push_model_from_file(self, file_path: str, description: str, backend_name: Optional[str] = None) -> None:
        self._get_backend(backend_name)._push_model_from_file(file_path, description)

    def delete_model(self, model_info: ModelInfo, allow_delete_base_models: bool = False, backend_name: Optional[str] = None) -> None:
        self._get_backend(backend_name).delete_model(model_info, allow_delete_base_models)

    def finetune_model(self, model_info: ModelInfo, data: Union[list[str], MedCATTrainerExport], backend_name: Optional[str] = None) -> ModelInfo:
        return self._get_backend(backend_name).finetune_model(model_info, data)

    def evaluate_model(self, model_info: ModelInfo, data: Union[list[str], MedCATTrainerExport], backend_name: Optional[str] = None) -> dict:
        return self._get_backend(backend_name).evaluate_model(model_info, data)

    def move_model(self, model_info: ModelInfo, origin: str, destination: str) -> None:
        if origin not in self._backends:
            raise NoSuchBackendException(f"No backend: '{origin}'")
        if destination not in self._backends:
            raise NoSuchBackendException(f"No backend: '{destination}'")
        if not self.has_model(model_info, backend_name=origin):
            raise NoSuchModel(model_info, origin)
        if self.has_model(model_info, backend_name=destination):
            raise DuplicateModelException(
                "Model %s already exists in %s", model_info.model_id, destination)
        logger.info("Fetching model %s from %s ...", model_info.model_id, origin)
        model = self.fetch_model(model_info, backend_name=origin)
        logger.info("Pushing model %s to %s ...", model_info.model_id, destination)
        self.push_model(model, "Base model", backend_name=destination)

    def sync_backend(self, origin: str, destination: str) -> None:
        if origin not in self._backends:
            raise NoSuchBackendException(f"No backend: '{origin}'")
        if destination not in self._backends:
            raise NoSuchBackendException(f"No backend: '{destination}'")
        dest_model_ids = {model.model_id for model in
                          self.list_available_models(destination)}
        for model in self.list_available_models(origin):
            if model.model_id in dest_model_ids:
                continue
            self.move_model(model, origin, destination)


class NoSuchBackendException(ValueError):
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
    backends, default_backage_name = resolve(
        type_, location, host, credentials, local_cache_path,
        expiration_time, max_size, eviction_policy,
        remote_allow_local_fine_tune, remote_allow_push_fine_tuned)
    return Den(backends=backends, default_backend_name=default_backage_name)


def get_default_user_local_den(
        location: Optional[str] = None) -> Den:
    return get_default_den(DenType.LOCAL_USER, location=location)


def get_default_machine_local_den(
        location: Optional[str] = None) -> Den:
    return get_default_den(DenType.LOCAL_MACHINE, location=location)


class DuplicateModelException(ValueError):

    def __init__(self, *args):
        super().__init__(*args)

class NoSuchModel(ValueError):

    def __init__(self, model_info: ModelInfo,
                 backend_name: str, extra: str = '') -> None:
        super().__init__(
            f"Could not find model {model_info.model_id} "
            f"in backend '{backend_name}'. {extra}")
