from typing import Optional

from pydantic import BaseModel


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
