from typing import Type, Generic, TypeVar, cast, Optional, Callable
import importlib
import logging


logger = logging.getLogger(__name__)

P = TypeVar('P')


class Registry(Generic[P]):
    def __init__(self, type: Type[P],
                 lazy_defaults: Optional[dict[str, tuple[str, str]]] = None
                 ) -> None:
        self._components: dict[str, Callable[..., P]] = {}
        self._type = type
        self._lazy_components = lazy_defaults.copy() if lazy_defaults else {}

    def register(self, component_name: str,
                 creator: Callable[..., P]):
        if component_name in self._components:
            prev = self._components[component_name]
            raise MedCATRegistryException(
                f"Component '{component_name}' already registered: {prev}")
        self._components[component_name] = creator

    def register_lazy(self, component_name: str, module_path: str,
                      creator_name: str) -> None:
        """Register the component lazily.

        This allows registration without the need to load component internals.
        However, we do not do any prior way of checking to make sure that these
        paths are correct.

        For instance if your class `MySpecialNER` is in the module
        `my_addon.my_module` and uses the class method
        `create_new_component` to initialise (thus the complete path is
        `my_addon.my_module.MySpecialNER.create_new_component`) we
        would expect the following arguments:
            component_name="my_special_ner",
            module_path="my_addon.my_module",
            creator_name="MySpecialNER.create_new_component"

        Args:
            component_name (str): The component name.
            module_path (str): The module name.
            creator_name (str): The creator path.

        Raises:
            MedCATRegistryException: If a component by this name has
                already been registered.
        """
        if component_name in self._components:
            prev = self._components[component_name]
            raise MedCATRegistryException(
                f"Component '{component_name}' already registered: {prev}")
        if component_name in self._lazy_components:
            prev = self._components[component_name]
            raise MedCATRegistryException(
                "Component '{component_name}' already registered (lazily):"
                f" {prev}")
        self._lazy_components[component_name] = (module_path, creator_name)

    def get_component(self, component_name: str
                      ) -> Callable[..., P]:
        """Get the component that's registered.

        The component generally refers to the class, but may
        be another method that creates the object needed.

        Args:
            component_name (str): The name of the component.

        Raises:
            MedCATRegistryException: If no component by requested name
                is registered.

        Returns:
            Callable[..., P]: The creator for the registered component.
        """
        # NOTE: some default implementations may be big imports,
        #       so we only want to import them if/when required.
        if component_name in self._lazy_components:
            self._ensure_lazy_default(component_name)
        if component_name not in self._components:
            raise MedCATRegistryException(
                f"No component registered by name '{component_name}'. "
                f"Available components: {self.list_components()}")
        return self._components[component_name]

    def _ensure_lazy_default(self, component_name: str) -> None:
        module_name, class_name = self._lazy_components.pop(component_name)
        logger.debug("Registering default %s '%s': '%s.%s'",
                     self._type.__name__, component_name, module_name,
                     class_name)
        module_in = importlib.import_module(module_name)
        if "." in class_name:
            cls_name, method_name = class_name.split(".")
        else:
            cls_name, method_name = class_name, None
        cls = getattr(module_in, cls_name)
        if method_name is not None:
            logger.debug("Using creator method %s.%s", cls_name, method_name)
            # use a creator method
            cls = getattr(cls, method_name)
        self.register(component_name, cast(Callable[..., P], cls))

    def register_all_defaults(self) -> None:
        """Register all default (lazily-added) components."""
        for comp_name in list(self._lazy_components):
            self._ensure_lazy_default(comp_name)

    @classmethod
    def translate_name(cls, initialiser: Callable[..., P]) -> str:
        """Translate creator / initialiser name.

        This method will return the method name.
        Or this is a bound method, it'll return the class name
        along with the method name (Class.method)

        Args:
            initialiser (Callable[..., P]): The initialiser

        Returns:
            str: The resulting name
        """
        if isinstance(initialiser, type):
            # type / dunder init
            return initialiser.__name__
        try:
            # probably a bound method
            return (
                initialiser.__self__.__name__ +  # type: ignore
                "." + initialiser.__name__)
        except AttributeError as err:
            logger.warning("Could not translate component name: %s",
                           initialiser, exc_info=err)
            return initialiser.__name__

    def list_components(self) -> list[tuple[str, str]]:
        """List all available component names and class names.

        Returns:
            list[tuple[str, str]]: The list of the names and class names
                for each registered componetn.
        """
        comps = [(comp_name, self.translate_name(comp))
                 for comp_name, comp in self._components.items()]
        for lazy_def_name, (_, lazy_def_class) in self._lazy_components.items():
            comps.append((lazy_def_name, lazy_def_class))
        return comps

    def unregister_component(self, component_name: str
                             ) -> Callable[..., P]:
        """Unregister a component.

        Args:
            component_name (str): The component name.

        Raises:
            MedCATRegistryException: If no component by the name specified
                had been registered.

        Returns:
            Callable[..., P]: The creator of the component.
        """
        if component_name not in self._components:
            raise MedCATRegistryException(
                f"No such component: {component_name}")
        logger.debug("Unregistering %s '%s'", self._type.__name__,
                     component_name)
        return self._components.pop(component_name)

    def unregister_component_lazy(
            self, component_name: str
            ) -> tuple[str, str]:
        """Unregister a lazy component.

        Args:
            component_name (str): The component name.

        Raises:
            MedCATRegistryException: If no component by the name specified
                had been registered.

        Returns:
            tuple[str, str]: The component module and init method.
        """
        if component_name not in self._lazy_components:
            raise MedCATRegistryException(
                f"No such lazy component: {component_name}")
        logger.debug("Unregistering lazy %s '%s'", self._type.__name__,
                     component_name)
        return self._lazy_components.pop(component_name)

    def unregister_all_components(self) -> None:
        """Unregister all components."""
        for comp_name in list(self._components):
            self.unregister_component(comp_name)

    def __contains__(self, component_name: str) -> bool:
        return (component_name in self._components or
                component_name in self._lazy_components)

    def __getitem__(self, component_name: str) -> Callable[..., P]:
        return self.get_component(component_name)


class MedCATRegistryException(Exception):

    def __init__(self, *args: object) -> None:
        super().__init__(*args)
