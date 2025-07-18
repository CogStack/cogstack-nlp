from typing import Optional, Iterable, Union
import logging
import os

from medcat.utils.defaults import COMPONENTS_FOLDER
from medcat.tokenizing.tokenizers import BaseTokenizer, create_tokenizer
from medcat.components.types import (
    CoreComponentType, create_core_component, CoreComponent, BaseComponent,
    AbstractCoreComponent)
from medcat.components.addons.addons import AddonComponent, create_addon
from medcat.tokenizing.tokens import (MutableDocument, MutableEntity,
                                      MutableToken)
from medcat.storage.serialisers import (
    AvailableSerialisers, serialise, deserialise)
from medcat.storage.serialisables import Serialisable
from medcat.vocab import Vocab
from medcat.cdb import CDB
from medcat.config import Config
from medcat.config.config import ComponentConfig
from medcat.config.config_meta_cat import ConfigMetaCAT
from medcat.config.config_rel_cat import ConfigRelCAT


logger = logging.getLogger(__name__)


class DelegatingTokenizer(BaseTokenizer):
    """A delegating tokenizer.

    This can be used to create a tokenizer with some preprocessing
    (i.e components) included.
    """

    def __init__(self, tokenizer: BaseTokenizer,
                 components: list[CoreComponent]):
        self.tokenizer = tokenizer
        self.components = components

    def create_entity(self, doc: MutableDocument,
                      token_start_index: int, token_end_index: int,
                      label: str) -> MutableEntity:
        return self.tokenizer.create_entity(
            doc, token_start_index, token_end_index, label)

    def entity_from_tokens(self, tokens: list[MutableToken]) -> MutableEntity:
        return self.tokenizer.entity_from_tokens(tokens)

    def __call__(self, text: str) -> MutableDocument:
        doc = self.tokenizer(text)
        for comp in self.components:
            doc = comp(doc)
        return doc

    @classmethod
    def create_new_tokenizer(cls, config: Config) -> 'DelegatingTokenizer':
        raise ValueError("Initialise the delegating tokenizer with its initialiser")

    def get_doc_class(self) -> type[MutableDocument]:
        return self.tokenizer.get_doc_class()

    def get_entity_class(self) -> type[MutableEntity]:
        return self.tokenizer.get_entity_class()


class Pipeline:
    """The pipeline for the NLP process.

    This class is responsible to initial creation of the NLP document,
    as well as running through of all the components and addons.
    """

    def __init__(self, cdb: CDB, vocab: Optional[Vocab],
                 model_load_path: Optional[str],
                 # NOTE: upon reload, old pipe can be useful
                 old_pipe: Optional['Pipeline'] = None,
                 addon_config_dict: Optional[dict[str, dict]] = None):
        self.cdb = cdb
        # NOTE: Vocab is None in case of DeID models and thats fine then,
        #       but it should be non-None otherwise
        self.vocab: Vocab = vocab  # type: ignore
        self.config = self.cdb.config
        self._tokenizer = self._init_tokenizer()
        self._components: list[CoreComponent] = []
        self._addons: list[AddonComponent] = []
        self._init_components(model_load_path, old_pipe, addon_config_dict)

    @property
    def tokenizer(self) -> BaseTokenizer:
        """The raw tokenizer (with no components)."""
        return self._tokenizer

    @property
    def tokenizer_with_tag(self) -> BaseTokenizer:
        """The tokenizer with the tagging component."""
        tag_comp = self.get_component(CoreComponentType.tagging)
        return DelegatingTokenizer(self.tokenizer, [tag_comp])

    def _init_tokenizer(self) -> BaseTokenizer:
        nlp_cnf = self.config.general.nlp
        try:
            return create_tokenizer(nlp_cnf.provider, self.config)
        except TypeError as type_error:
            if nlp_cnf.provider == 'spacy':
                raise type_error
            raise IncorrectArgumentsForTokenizer(
                nlp_cnf.provider) from type_error

    def _init_component(self, comp_type: CoreComponentType,
                        model_load_path: Optional[str]) -> CoreComponent:
        comp_config: ComponentConfig = getattr(self.config.components,
                                               comp_type.name)
        comp_name = comp_config.comp_name
        try:
            comp = create_core_component(
                comp_type, comp_name, comp_config, self.tokenizer, self.cdb,
                self.vocab, model_load_path)
        except TypeError as type_error:
            if comp_name == 'default':
                raise type_error
            raise IncorrectArgumentsForComponent(
                comp_type, comp_name) from type_error
        return comp

    def _get_loaded_components_paths(self, model_load_path: Optional[str]
                                     ) -> tuple[dict[str, str],
                                                dict[tuple[str, str], str]]:
        loaded_core_component_paths: dict[str, str] = {}
        loaded_addon_component_paths: dict[tuple[str, str], str] = {}
        if not model_load_path:
            return loaded_core_component_paths, loaded_addon_component_paths
        components_folder = os.path.join(
            model_load_path, COMPONENTS_FOLDER)
        if not os.path.exists(components_folder):
            return loaded_core_component_paths, loaded_addon_component_paths
        for folder_name in os.listdir(components_folder):
            cur_folder_path = os.path.join(
                components_folder, folder_name)
            if folder_name.startswith(AbstractCoreComponent.NAME_PREFIX):
                loaded_core_component_paths[
                    folder_name[len(AbstractCoreComponent.NAME_PREFIX):]
                    ] = cur_folder_path
            elif folder_name.startswith(AddonComponent.NAME_PREFIX):
                addon_folder_name = folder_name[
                    len(AddonComponent.NAME_PREFIX):]
                addon_type, addon_name = addon_folder_name.split(
                    AddonComponent.NAME_SPLITTER, 1)
                loaded_addon_component_paths[
                    (addon_type, addon_name)] = cur_folder_path
            else:
                raise ValueError()
        return loaded_core_component_paths, loaded_addon_component_paths

    def _load_saved_core_component(self, cct_name: str, comp_folder_path: str
                                   ) -> CoreComponent:
        logger.info("Using loaded component for '%s' for", cct_name)
        cnf: ComponentConfig = getattr(self.config.components, cct_name)
        comp = deserialise(
            comp_folder_path,
            # NOTE: the following are keyword arguments used
            #       for manual deserialisation
            cnf=cnf, tokenizer=self.tokenizer, cdb=self.cdb,
            vocab=self.vocab, model_load_path=os.path.dirname(
                os.path.dirname(comp_folder_path)))
        if not isinstance(comp, CoreComponent):
            raise IncorrectFolderUponLoad(
                f"Did not find a CoreComponent at {comp_folder_path} "
                f"when loading '{cct_name}'. Found "
                f"'{type(comp)}' instead.")
        if comp.get_type() != CoreComponentType[cct_name]:
            raise IncorrectFolderUponLoad(
                "Did not find the correct CoreComponent at "
                f"{comp_folder_path} for '{cct_name}'. Found "
                f"'{comp.get_type().name}' instead.")
        return comp

    @classmethod
    def _attempt_merge(
            cls, addon_cnf: ComponentConfig,
            addon_config_dict: dict[str, dict]) -> None:
        for name, config_dict in addon_config_dict.items():
            if not name.startswith(addon_cnf.comp_name):
                continue
            # TODO: is there an option to do this in a more general way?
            #       right now it's an implementation-specific code smell
            if isinstance(addon_cnf, ConfigMetaCAT):
                full_name = f"{addon_cnf.comp_name}.{addon_cnf.general.category_name}"
                if name == full_name:
                    addon_cnf.merge_config(config_dict)
                    return
                continue
            logger.warning(
                "No implementation specified for defining if/when %s"
                "should apply to addon config (e.g %s)",
                type(addon_cnf).__name__, name)
            # if only 1 of the type, then just merge
            similars = [cd for oname, cd in addon_config_dict.items()
                        if oname.startswith(addon_cnf.comp_name)]
            if len(similars) == 1:
                logger.warning(
                    "Since there is only 1 config for this type (%s) specified "
                    "we will just merge the configs (@%s).",
                    addon_cnf.comp_name, name)
                addon_cnf.merge_config(config_dict)
                return
            else:
                logger.warning(
                    "There are %d similar configs (%s) specified, so unable to "
                    "merge the config since it's ambiguous (@%s)",
                    len(similars), addon_cnf.comp_name, name)

    def _init_components(self, model_load_path: Optional[str],
                         old_pipe: Optional['Pipeline'],
                         addon_config_dict: Optional[dict[str, dict]],
                         ) -> None:
        (loaded_core_component_paths,
         loaded_addon_component_paths) = self._get_loaded_components_paths(
             model_load_path)
        for cct_name in self.config.components.comp_order:
            if cct_name in loaded_core_component_paths:
                comp = self._load_saved_core_component(
                    cct_name, loaded_core_component_paths.pop(cct_name))
            else:
                comp = self._init_component(
                    CoreComponentType[cct_name], model_load_path)
            self._components.append(comp)
        for addon_cnf in self.config.components.addons:
            if addon_config_dict:
                self._attempt_merge(addon_cnf, addon_config_dict)
            addon = self._init_addon(
                addon_cnf, loaded_addon_component_paths, old_pipe)
            # mark as not dirty at loat / init time
            addon.config.mark_clean()
            self._addons.append(addon)

    def _get_loaded_addon_path(
            self, cnf: ComponentConfig,
            loaded_addon_component_paths: dict[tuple[str, str], str]
            ) -> Optional[str]:
        for key, folder in list(loaded_addon_component_paths.items()):
            comp_name, subname = key
            if comp_name != cnf.comp_name:
                continue
            if not isinstance(cnf, (ConfigMetaCAT, ConfigRelCAT)):
                raise UnkownAddonConfig(cnf, ConfigMetaCAT)
            if isinstance(cnf, ConfigMetaCAT):
                if cnf.general.category_name == subname:
                    del loaded_addon_component_paths[key]
                    return folder
            elif isinstance(cnf, ConfigRelCAT):
                if subname == 'rel_cat':
                    # NOTE: there can currently only ever be 1 RelCAT
                    #       this wasn't a limitation in v1
                    del loaded_addon_component_paths[key]
                    return folder
        return None

    def _load_addon(self, cnf: ComponentConfig, load_from: str
                    ) -> AddonComponent:
        # config is implicitly required argument
        model_load_path = os.path.dirname(os.path.dirname(load_from))
        addon = deserialise(
            load_from,
            # NOTE: the following are keyword arguments used
            #       for manual deserialisation
            cnf=cnf, tokenizer=self.tokenizer, cdb=self.cdb,
            vocab=self.vocab, model_load_path=model_load_path)
        if not isinstance(addon, AddonComponent):
            raise IncorrectAddonLoaded(
                f"Expected {AddonComponent.__name__}, but goet "
                f"{type(addon).__name__}")
        return addon

    def _init_addon(
            self, cnf: ComponentConfig,
            loaded_addon_component_paths: dict[tuple[str, str], str],
            old_pipe: Optional['Pipeline'],
            ) -> AddonComponent:
        if old_pipe:
            # If we are recreating a pipe and the addon configs haven't
            # changed then we can reuse existing addon instances.
            # This can be useful since otherwise we may need to load them
            # back off of disk, but we do not (necessarily) know where they
            # are or they may have changed after loading
            for old_addon in old_pipe._addons:
                if old_addon.config is cnf and not cnf.is_dirty:
                    return old_addon
                elif old_addon.config is cnf and cnf.is_dirty:
                    logger.warning(
                        "Not reusing existing addon '%s' because its config "
                        "has changed", old_addon.config.comp_name)
        loaded_path = self._get_loaded_addon_path(
            cnf, loaded_addon_component_paths)
        if loaded_path:
            return self._load_addon(cnf, loaded_path)
        return create_addon(
            cnf.comp_name, cnf=cnf, tokenizer=self.tokenizer, cdb=self.cdb,
            vocab=self.vocab, model_load_path=None)

    def get_doc(self, text: str) -> MutableDocument:
        """Get the document for this text.

        This essentially runs the tokenizer over the text.

        Args:
            text (str): The input text.

        Returns:
            MutableDocument: The resulting document.
        """
        doc = self._tokenizer(text)
        for comp in self._components:
            logger.info("Running component %s for %d of text (%s)",
                        comp.full_name, len(text), id(text))
            doc = comp(doc)
        for addon in self._addons:
            doc = addon(doc)
        return doc

    def entity_from_tokens(self, tokens: list[MutableToken]) -> MutableEntity:
        """Get the entity from the list of tokens.

        This effectively turns a list of (consecutive) documents
        into an entity.

        Args:
            tokens (list[MutableToken]): The tokens to use.

        Returns:
            MutableEntity: The resulting entity.
        """
        return self._tokenizer.entity_from_tokens(tokens)

    def get_component(self, ctype: CoreComponentType) -> CoreComponent:
        """Get the core component by the component type.

        Args:
            ctype (CoreComponentType): The core component type.

        Raises:
            ValueError: If no component by that type is found.

        Returns:
            CoreComponent: The corresponding core component.
        """
        for comp in self._components:
            if not comp.is_core() or not isinstance(comp, CoreComponent):
                continue
            if comp.get_type() is ctype:
                return comp
        raise ValueError(f"No component found of type {ctype}")

    def add_addon(self, addon: AddonComponent) -> None:
        self._addons.append(addon)
        # mark clean as of adding
        addon.config.mark_clean()

    def save_components(self,
                        serialiser_type: Union[AvailableSerialisers, str],
                        components_folder: str) -> None:
        for component in self.iter_all_components():
            if not isinstance(component, Serialisable):
                continue
            if not os.path.exists(components_folder):
                os.mkdir(components_folder)
            if isinstance(component, CoreComponent):
                comp_folder = os.path.join(
                    components_folder,
                    AbstractCoreComponent.NAME_PREFIX +
                    component.get_type().name)
            elif isinstance(component, AddonComponent):
                comp_folder = os.path.join(
                    components_folder,
                    f"{AddonComponent.NAME_PREFIX}{component.addon_type}"
                    f"{AddonComponent.NAME_SPLITTER}{component.name}")
            else:
                raise ValueError(
                    f"Unknown component: {type(component)} - does not appear "
                    "to be a CoreComponent or an AddonComponent")
            serialise(serialiser_type, component, comp_folder)

    def iter_all_components(self) -> Iterable[BaseComponent]:
        for component in self._components:
            yield component
        for addon in self._addons:
            yield addon

    def iter_addons(self) -> Iterable[AddonComponent]:
        yield from self._addons


class IncorrectArgumentsForTokenizer(TypeError):

    def __init__(self, provider: str):
        super().__init__(
            f"Incorrect arguments for tokenizer ({provider}).")


class IncorrectArgumentsForComponent(TypeError):

    def __init__(self, comp_type: CoreComponentType, comp_name: str):
        super().__init__(
            f"Incorrect arguments for core component {comp_type.name} "
            f"({comp_name}).")


class IncorrectCoreComponent(ValueError):

    def __init__(self, *args):
        super().__init__(*args)


class IncorrectFolderUponLoad(ValueError):

    def __init__(self, *args):
        super().__init__(*args)


class UnkownAddonConfig(ValueError):

    def __init__(self, cnf: ComponentConfig,
                 *existing_types: type[ComponentConfig]):
        super().__init__(
            f"Found unknown Addon config of type {type(cnf)}. "
            f"Existing types: {[etype.__name__ for etype in existing_types]}")


class IncorrectAddonLoaded(ValueError):

    def __init__(self, *args):
        super().__init__(*args)
