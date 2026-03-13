from typing import Optional, Any

from medcat.config import Linking


class EmbeddingLinking(Linking):
    """The config exclusively used for the embedding linker"""
    comp_name: str = "embedding_linker"
    """Changing compoenent name"""
    filter_before_disamb: bool = False
    """Filtering CUIs before disambiguation"""
    train: bool = False
    """The embedding linker never needs to be trained in its 
    current implementation."""
    use_projection_layer: bool = True
    """Whether to use a projection layer in the embedding linker. This
    option can only be used on trainable embedding models. """
    top_n_layers_to_unfreeze: int = -1
    """The number of top layers of the embedding model to unfreeze for training.
    Set to -1 to unfreeze all layers, 0 to freeze all layers, or any positive integer 
    to unfreeze that many top layers. Only used if train is True."""
    negative_sampling_k: int = 10
    """The number of negative samples to generate during training."""
    negative_sampling_temperature: float = 0.1
    """The temperature parameter for negative sampling. Higher values will make the 
    sampling distribution more uniform, while lower values will make it more 
    focused on the top-ranked candidates."""
    embed_per_n_batches: int = 200
    """How often to re-embed names during training, in terms of number of batches. This 
    is due to re-embedding being very expensive, and you can afford to get away with stale names
    for a time."""
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
    max_token_length: int = 64
    """Max number of tokens to be embedded from a name.
    If the max token length is changed then the linker will need to be created
    with a new config.
    """
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
    use_similarity_threshold: bool = True
    """Do we have a similarity threshold we care about?"""
