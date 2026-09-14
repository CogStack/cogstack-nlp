from typing import Type, Protocol
from types import ModuleType
from inspect import isclass
import re
import os
import pkgutil
import importlib

from pydantic_core import ValidationError
from transformers import AutoTokenizer, AutoModel

from medcat import config as config_pkg


def get_cnf_models() -> tuple[list[tuple[Type, str]], set[str]]:
    print("Getting CNF / default models...")
    models: set[str] = set()
    keys: list[tuple[Type, str]] = []
    cnf_pkg_path = os.path.dirname(config_pkg.__file__)
    print("Looking in", cnf_pkg_path)
    for module_info in pkgutil.iter_modules([cnf_pkg_path]):
        module_path = f"medcat.config.{module_info.name}"
        print(" - Checking module", module_path)
        cur_module = importlib.import_module(module_path)
        cur_keys, cur_models = get_models_in_module(cur_module)
        keys.extend(cur_keys)
        models.update(cur_models)
    return keys, models


def get_models_in_module(cur_module: ModuleType
        ) -> tuple[list[tuple[Type, str]], set[str]]:
    models: set[str] = set()
    keys: list[tuple[Type, str]] = []
    for key in dir(cur_module):
        cur_cls = getattr(cur_module, key)
        if not isclass(cur_cls):
            continue
        # avoid imports
        if cur_cls.__module__ != cur_module.__name__:
            continue
        # avoid exception classes
        if issubclass(cur_cls, BaseException):
            continue
        # avoid protocols
        if issubclass(cur_cls, Protocol):
            pass
        try:
            inst = cur_cls()
        except (TypeError, ValidationError) as err:
            # Some config classes may require arguments, skip them for now
            print("   Could not check", cur_cls, 'due to', err)
            continue
        for k, val in inst.model_dump().items():
            if isinstance(val, str) and val.count("/") == 1:
                print("   Found[1]", k, ":", val)
                models.add(val)
                keys.append((cur_cls, k))
            elif isinstance(val, str) and "name" in k and "model" in k:
                print("   Found[2]", k, ":", val)
                models.add(val)
                keys.append((cur_cls, k))

    return keys, models


def get_test_models(keys: list[tuple[Type, str]]) -> set[str]:
    models: set[str] = set()
    tests_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

    for root, _, files in os.walk(tests_dir):
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r') as f:
                        content = f.read()
                        for cls_type, attribute_path in keys:
                            # Construct a regex to find assignments to the attribute_path
                            # This regex handles cases like: variable.attribute = 'model_name' or attribute = 'model_name'
                            # It also handles both single and double quotes.
                            pattern = rf"\b\w*\.?\s*{re.escape(attribute_path)}\s*=\s*[\"'](.*?)(?<!\\)[\"']"
                            matches = re.findall(pattern, content)
                            for match in matches:
                                print("   FOUND", match, ", hopefully matching",
                                      f"{cls_type.__name__}.{attribute_path}", "within", file)
                                models.add(match)
                except Exception as e:
                    print(f"Error reading or processing file {file_path}: {e}")
    return models


def remove_non_models(models: set[str]) -> None:
    for model in list(models):
        if model.endswith(".log"):
            print("Removing .log file:", model)
            models.remove(model)
        elif model.upper() == "N/A":
            print("Removing N/A model:", model)
            models.remove(model)
        elif model.startswith("en_core_web"):
            print("Removing spacy model:", model)
            models.remove(model)
        elif " " in model:
            print("Removing model with whitespace:", model)
            models.remove(model)


def download_all_models(models: set[str]) -> None:
    # Download and cache all unique models
    downloaded = 0
    for model_name in models:
        try:
            print(f"Downloading and caching model: {model_name}...")
            _ = AutoTokenizer.from_pretrained(model_name)
            _ = AutoModel.from_pretrained(model_name)
            print(f"Successfully downloaded and cached {model_name}")
            downloaded += 1
        except Exception as e:
            print(f"Error downloading {model_name}: {e}")
    print(f"Downloaded a total of {downloaded}/{len(models)} models")


def main():
    # model defaults
    keys, cnf_models = get_cnf_models()

    print(f"Found {len(cnf_models)} unique default HF models: {cnf_models}")

    # model vals in tests
    test_models = get_test_models(keys)

    print(f"Found {len(test_models)} unique TEST HF models: {test_models}")

    models = cnf_models.union(test_models)

    print(f"Combined to {len(models)} unique HF models: {models}")

    # clean data
    remove_non_models(models)

    print(f"FINAL: {len(models)} unique HF models: {models}")
    print("Start downloads...\n\n")

    download_all_models(models)


if __name__ == "__main__":
    main()
