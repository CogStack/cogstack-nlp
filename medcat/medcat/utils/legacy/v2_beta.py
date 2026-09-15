import dill


class RemappingUnpickler(dill.Unpickler):
    # TODO: remove at some point - this only serves to load beta models
    def find_class(self, module: str, name: str):
        # Remap old module path to new one
        module, name = fix_module_and_cls_name(module, name)
        return super().find_class(module, name)


def fix_module_and_cls_name(module_name: str, cls_name: str
                            ) -> tuple[str, str]:
    if module_name.startswith("medcat2"):
        module_name = module_name.replace("medcat2", "medcat", 1)
    return module_name, cls_name
