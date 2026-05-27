from typing import Optional

from pydantic import BaseModel, field_validator


from medcat.cat import CAT
from medcat.data.model_card import ModelCard


class ModelInfo(BaseModel):
    model_id: str
    model_card: Optional[ModelCard]
    base_model: Optional['ModelInfo']

    @classmethod
    def from_model_pack(cls, cat: CAT) -> 'ModelInfo':
        mc = cat.get_model_card(True)
        hist = mc['History (from least to most recent)']
        model_hash = mc["Model ID"]
        bm = (
            ModelInfo(model_id=hist[0], model_card=None, base_model=None)
            if (len(hist) > 0 and hist[0] != model_hash) else None
        )
        return cls(
            model_id=mc["Model ID"],
            model_card=mc,
            base_model=bm,
        )

    @field_validator('model_card', mode='before')
    @classmethod
    def make_permissive(cls, v: dict) -> dict:
        """Accept dict even if it's missing new optional fields"""
        if isinstance(v, dict):
            defaults = {
                'Pipeline Description': {"core": {}, "addons": []},
                'Required Plugins': [],
                "Location": "N/A",
                "Basic CDB Stats": {
                    "Unsupervised training history": [],
                    "Supervised training history": [],
                },
                "Source Ontology": ["unknown"],
            }
            out_dict = {**defaults, **v}  # v overwrites defaults
            cls._check_key_value_recursively(out_dict, defaults)
            return out_dict
        return v

    @classmethod
    def _check_key_value_recursively(
            cls, out_dict: dict, defaults: dict) -> None:
        for key, def_val in defaults.items():
            # NOTE: this should be mostly for nested stuff
            if key not in out_dict:
                out_dict[key] = def_val
                continue
            cur_val = out_dict[key]
            if cur_val is None or type(cur_val) is not type(def_val):
                out_dict[key] = def_val
            elif isinstance(def_val, dict):
                cls._check_key_value_recursively(cur_val, def_val)
