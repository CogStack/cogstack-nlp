from typing import Optional

from medcat.config.config import SerialisableBaseModel
from medcat.utils.hasher import Hasher


class General(SerialisableBaseModel):
    """The general part of the Transformers NER config"""
    name: str = 'deid'
    model_name: str = 'roberta-base'
    """Can be path also"""
    seed: int = 13
    description: str = "No description"
    """Should provide a basic description of this MetaCAT model"""
    pipe_batch_size_in_chars: int = 20000000
    """How many characters are piped at once into the meta_cat class"""
    ner_aggregation_strategy: str = 'simple'
    """Agg strategy for HF pipeline for NER"""
    chunking_overlap_window: Optional[int] = 5
    """Size of the overlap window used for chunking"""
    test_size: float = 0.2
    last_train_on: Optional[float] = None
    verbose_metrics: bool = False

    class Config:
        extra = 'allow'
        validate_assignment = True
        protected_namespaces = ()


class ConfigTransformersNER(SerialisableBaseModel):
    """The transformer NER config"""
    general: General = General()

    class Config:
        extra = 'allow'
        validate_assignment = True

    def get_hash(self, hasher: Optional[Hasher] = None) -> str:
        if hasher is None:
            hasher = Hasher()
        for v in self.model_dump().values():
            hasher.update(v)
        return hasher.hexdigest()
