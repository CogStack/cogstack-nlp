from typing import Callable, Protocol, Any, runtime_checkable

from medcat.components.types import BaseComponent, MutableEntity
from medcat.utils.registry import Registry
from medcat.config.config import ComponentConfig


@runtime_checkable
class AddonComponent(BaseComponent, Protocol):
    """Base/abstract addon component class."""
    NAME_PREFIX: str = "addon_"
    NAME_SPLITTER: str = "."
    config: ComponentConfig

    @property
    def addon_type(self) -> str:
        pass

    def is_core(self) -> bool:
        return False

    def get_folder_name(self) -> str:
        return (self.NAME_PREFIX + self.addon_type +
                self.NAME_SPLITTER + self.name)

    @property
    def full_name(self) -> str:
        return self.addon_type + self.NAME_SPLITTER + str(self.name)

    @property
    def include_in_output(self) -> bool:
        return False  # default to False

    def get_output_key_val(self, ent: MutableEntity
                           ) -> tuple[str, dict[str, Any]]:
        pass


_DEFAULT_ADDONS: dict[str, tuple[str, str]] = {
    'meta_cat': ('medcat.components.addons.meta_cat.meta_cat',
                 'MetaCATAddon.create_new'),
    'rel_cat': ('medcat.components.addons.relation_extraction.rel_cat',
                'RelCATAddon.create_new')
}

# NOTE: type error due to non-concrete type
_ADDON_REGISTRY = Registry(AddonComponent, _DEFAULT_ADDONS)  # type: ignore


def register_addon(addon_name: str,
                   addon_cls: Callable[..., AddonComponent]) -> None:
    """Register a new addon.

    Args:
        addon_name (str): The addon name.
        addon_cls (Callable[..., AddonComponent]): The addon creator.
    """
    _ADDON_REGISTRY.register(addon_name, addon_cls)


def get_addon_creator(addon_name: str) -> Callable[..., AddonComponent]:
    """Get the creator for an addon.

    Args:
        addon_name (str): The name of the addonl

    Returns:
        Callable[..., AddonComponent]: The creator of the addon.
    """
    return _ADDON_REGISTRY.get_component(addon_name)


def create_addon(addon_name: str, cnf: ComponentConfig,
                 *args, **kwargs) -> AddonComponent:
    """Create an addon of the specified name with the specified arguments.

    All the `*args`, and `**kwrags` are passed to the creator.

    Args:
        addon_name (str): The name of the addon.
        cnf (ComponentConfig): The addon config.

    Returns:
        AddonComponent: The resulting / created addon.
    """
    return get_addon_creator(addon_name)(cnf, *args, **kwargs)
