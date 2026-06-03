from typing import Optional, Any
from medcat.config import Linking


class EmbeddingLinking(Linking):
    """The config exclusively used for the embedding linker"""

    comp_name: str = "embedding_linker"
    """Changing compoenent name"""
    filter_before_disamb: bool = False
    """Training on names or CUIs. If True all names of all CUIs will be used to train. 
    If false only CUIs preffered (or longest names will be used to train). Training on 
    names is more expensive computationally (and RAM/VRAM), but can lead to better 
    performance."""
    train_on_names: bool = True
    """Filtering CUIs before disambiguation"""
    training_batch_size: int = 32
    """The size of the batch to be used for training."""
    embed_per_n_batches: int = 0
    """How many batches to train on before re-embedding the all names in the context 
    model. This is used to control how often the context model is updated during 
    training."""
    use_similarity_threshold: bool = True
    """Do we have a similarity threshold we care about?"""
    negative_sampling_k: int = 10
    """How many negative samples to generate for each positive sample during 
    training."""
    negative_sampling_candidate_pool_size: int = 4096
    """When generating negative samples, sample top_n candidates to consider when 
    sampling. Higher numbers will make training slower but can provide varied negative 
    samples."""
    negative_sampling_temperature: float = 0.1
    """Temperature to use when generating negative samples in training. Lower 
    temperatures will make the sampling more focused on the highest scoring candidates, 
    while higher temperatures will make it more random. Must be > 0."""
    use_mention_attention: bool = True
    """Improves performance and fun to say. Mention attention can help the model focus 
    on the most relevant parts of the context when making linking decisions. Will only 
    pool on the tokens that contain the entity mention, with no context."""
    long_similarity_threshold: float = 0.0
    """Used in the inference step to choose the best CUI given the
    link candidates. Testing shows a threshold of 0.7 increases precision
    with minimal impact on recall. Default is 0.0 which assumes
    all entities detected by the NER step are true."""
    short_similarity_threshold: float = 0.0
    """Used for generating cui candidates. If a threshold of 0.0
    is selected then only the highest scoring name will provide cuis
    to be link candidates. Use a threshold of 0.95 or higher, as this is
    essentailly string matching and account for spelling errors. Lower 
    thresholds will provide too many candidates and slow down the inference."""
    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    """Name of the embedding model. It must be downloadable from 
    huggingface linked from an appropriate file directory"""
    use_projection_layer: bool = True
    """Projection-layer default for trainable embedding linker."""
    top_n_layers_to_unfreeze: int = 0
    """LM unfreezing default for trainable embedding linker.
    -1 unfreezes all LM layers, 0 freezes all LM layers, 
    n unfreezes the top n layers."""
    max_token_length: int = 64
    """Max number of tokens to be embedded from a name.
    If the max token length is changed then the linker will need to be created
    with a new config."""
    embedding_batch_size: int = 4096
    """How many pieces names can be embedded at once, useful when 
    embedding name2info names, cui2info names"""
    linking_batch_size: int = 512
    """How many entities to be linked at once"""
    gpu_device: Optional[Any] = None
    """Choose a device for the linking model to be stored. If None
    then an appropriate GPU device that is available will be chosen"""
    context_window_size: int = 14
    """Choose the window size to get context vectors."""
    use_ner_link_candidates: bool = True
    """Link candidates are provided by some NER steps. This will flag if 
    you want to trust them or not."""
    learning_rate: float = 1e-4
    """Learning rate for training the embedding linker. Only used if 
    the embedding linker is trainable."""
    weight_decay: float = 0.01
    """Weight decay for training the embedding linker. Only used if
    the embedding linker is trainable."""
