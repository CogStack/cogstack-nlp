from typing import Optional, Any
from medcat.config import Ner

class TransformerNER(Ner):
    """The config exclusively used for the transformer NER"""
    language_model_name: str = "michiyasunaga/BioLinkBERT-large"
    """Name/path of the language model. It must be downloadable from 
    huggingface or linked from an appropriate file directory. NOTE:
    use ner_component.load_transformers to load the model, changing this
    does nothing."""
    training_batch_size: int = 32
    """The size of the batch to be used for training."""
    max_token_length: int = 512
    """Max number of tokens to be passed to the language model.
    Longer sequences will be chunked"""
    overlap_chunking: float = 0.2
    """Max number of tokens to be passed to the language model.
    Longer sequences will be chunked"""
    gpu_device: Optional[Any] = None
    """Choose a device for the model to be stored / computed on. If None
    then an appropriate GPU device that is available will be chosen"""
    require_link_candidates: bool = True
    """Generate ent.link_candidates based on detected names. This requires
    checking the CDB.name2info, and is required for vocab based linking.
    Set to true becuase even if you don't use it, whats the harm?"""
    learning_rate: float = 2e-5
    """The learning rate to be used for training the model"""
    weight_decay: float = 0.01
    """The weight decay to be used for training the model"""