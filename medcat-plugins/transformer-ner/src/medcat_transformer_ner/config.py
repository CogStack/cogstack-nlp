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
    overlap_chunking: float = 0.1
    """How much each chunk should overlap with the previous one.
    This is important to avoid missing entities that are on the border of two chunks."""
    gpu_device: Optional[Any] = None
    """Choose a device for the model to be stored / computed on. If None
    then an appropriate GPU device that is available will be chosen"""
    require_link_candidates: bool = True
    """Generate ent.link_candidates based on detected names. This requires
    checking the CDB.name2info, and is required for vocab based linking.
    Enabling this will lower recall, and most likely increase precision, 
    it will also decrease computation time."""
    use_prefix_token: bool = False
    """Given a detected span, include one token previous to improve recall.
    This helps with low signal words not being detected by the model. This will
    increase computation time, and could reduce precision."""
    learning_rate: float = 1e-5
    """The learning rate to be used for training the model. Set via
    TransformerNER.set_learning_rate on a loaded model so the change is propagated 
    to the optimizer."""
    weight_decay: float = 0.001
    """The weight decay to be used for training the model. Set via
    TransformerNER.set_weight_decay on a loaded model so the change is propagated 
    to the optimizer."""
    class_weights: dict[str, float] = {
        "O": 1.0,
        "B-ENT": 1.0,
        "I-ENT": 1.0,
        "E-ENT": 1.0,
        "S-ENT": 1.0,
    }
    """Per-label weights for the token-level cross entropy loss, keyed by
    label name. Uniform by default. Set via TransformerNER.set_class_weights so the 
    change is propagated to the loaded model."""
    crf_loss_weight: float = 1.0
    """Multiplier on the CRF loss in the total loss:
    crf_loss_weight * crf_loss + weighted_cross_entropy. Changing this will proioritize 
    different metrics over the other. Set via TransformerNER.set_crf_loss_weight so the
    change is propagated to the loaded model."""