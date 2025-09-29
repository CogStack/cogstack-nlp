from typing import Callable, Any, Type
from functools import lru_cache, wraps

from pydantic import BaseModel

from medcat_den.base import ModelInfo
from medcat_den.den import Den


def summarise_den(den: Den) -> str:
    """Get a summary of the given den.

    Args:
        den (Den): The den to summarise.

    Returns:
        str: The summary.
    """
    models = den.list_available_models()
    num_models = len(models)
    if num_models:
        summary = summarise_models(models)
    else:
        summary = "No models available"
    return (
        f"Den ({den.den_type.name}) with {num_models} models:\n"
        f"{summary}"
    )


def summarise_models(models: list[ModelInfo]) -> str:
    """Get a summary of the given models.

    Args:
        models (list[ModelInfo]): The models to summarise.

    Returns:
        str: The summary.
    """
    lines: list[str] = []
    for model in models:
        mc = model.model_card
        if mc is None:
            model_summary = "No model card available"
        else:
            last_modified = mc['Last Modified On']
            history = mc['History (from least to most recent)']
            description = repr(mc['Description'])  # hide new lines
            source_onts = mc['Source Ontology']
            _meta_cats = mc['MetaCAT models']
            if isinstance(_meta_cats, list):
                meta_cats = _meta_cats
            elif isinstance(_meta_cats, dict):
                meta_cats = list(_meta_cats.keys())
            else:
                meta_cats = []
            built_in = mc['MedCAT Version']
            model_summary = (
                f"{model.model_id} ({description})\n"
                f" - History: {history}\n"
                f" - Source ontologies: {source_onts}\n"
                f" - Meta models: {meta_cats}\n"
                f" - MedCAT Version: {built_in}\n"
                f" - Last updated: {last_modified}"
            )
        lines.append(model_summary)
    return "\n".join(lines)


def cache_on_model(func: Callable) -> Any:
    @lru_cache(maxsize=None)
    def cached(json_key: str, type_: Type[BaseModel]):
        return func(type_.model_validate_json(json_key))

    @wraps(func)
    def wrapper(model: BaseModel):
        return cached(model.model_dump_json(), type(model))
    return wrapper
