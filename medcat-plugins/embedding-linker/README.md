# MedCAT Embedding Linker

A MedCAT plugin that provides an embedding-based entity linking component using transformer models from HuggingFace.

## Overview

This plugin replaces MedCAT's default linking component with a transformer-based approach that uses semantic similarity between entity contexts and concept embeddings to perform entity disambiguation.

**Key features:**
- Semantic similarity-based linking using transformer embeddings
- Support for any HuggingFace sentence-transformer model
- Efficient batch processing with GPU acceleration
- Configurable similarity thresholds and context windows
- CUI-based filtering (include/exclude lists)

## Requirements

- **MedCAT**: 2.0+ ([PyPI](https://pypi.org/project/medcat/) | [GitHub](https://github.com/CogStack/MedCAT))
- Python 3.10+
- PyTorch
- Transformers

## Installation

```bash
pip install medcat-embedding-linker
```

## Quick Start

### Replacing current linker with a static embedding linker

```python
from medcat.cat import CAT
from medcat.config import Config
from medcat.components.types import CoreComponentType
from medcat_embedding_linker.embedding_linker import Linker as StaticEmbeddingLinker
from medcat_embedding_linker.config import EmbeddingLinking

# Load your MedCAT model
cat = CAT.load_model_pack("path/to/model_pack")

# Configure the embedding linker
cat.config.components.linking = EmbeddingLinking()
cat.config.components.linking.comp_name = StaticEmbeddingLinker.name

# Recreate the pipeline to register the new linker
cat._recreate_pipe()

# Generate embeddings for your concept database
linker = self.get_component(CoreComponentType.linking)
# create 
linker.create_embeddings()

# Use as normal
entities = cat.get_entities("Patient presents with chest pain and dyspnea.")
```

### Replacing current linker with a trainable embedding linker AND training

```python
from medcat.cat import CAT
from medcat_embedding_linker.trainable_embedding_linker import TrainableEmbeddingLinker
from medcat_embedding_linker.config import EmbeddingLinking

# Load your MedCAT model
cat = CAT.load_model_pack("path/to/model_pack")

# Configure the embedding linker
cat.config.components.linking = EmbeddingLinking()
cat.config.components.linking.comp_name = TrainableEmbeddingLinker.name

# Recreate the pipeline to register the new linker
cat._recreate_pipe()

# Generate embeddings for your concept database
linker = self.get_component(CoreComponentType.linking)
# create 
linker.create_embeddings()

# load required data into MedCATTrainerExport format
train_projects, test_projects = your_dataset_loading_method()

# Training loop - four is probably a nice stopping point
num_epochs = 4

# the first epoch is done out of the loop incase new concepts / names are detected
cat.trainer.train_supervised_raw(train_projects, test_size=0, nepochs=1)
# refreshing the structure here is required for new cuis/names that have been detected
# so the efficient lookup lists need to be recreated
linker.refresh_structure()
linker.create_embeddings()
get_stats(cat=cat, data=test_projects, use_project_filters=False)
for i in range(num_epochs - 1):
    cat.trainer.train_supervised_raw(train_projects, test_size=0, nepochs=1)
    linker.create_embeddings()
    get_stats(cat=cat, data=test_projects, use_project_filters=False)
```

## How It Works

### Component Registration

The embedding linker automatically requires the name of the trainable or static component when `EmbeddingLinking` config is detected. It implements MedCAT's `AbstractEntityProvidingComponent` interface and is lazily loaded when the pipeline is created.

### Embedding Generation

The linker operates on two types of embeddings:

**1. Concept Embeddings** (pre-computed)
- Each CUI is represented by its longest name's embedding
- Stored in `cdb.addl_info["cui_embeddings"]`
- Used for final disambiguation between candidate CUIs

**2. Name Embeddings** (pre-computed)
- Each concept name in the CDB gets its own embedding
- Stored in `cdb.addl_info["name_embeddings"]`
- Used for initial candidate retrieval

Both are generated via `linker.create_embeddings()` and cached for inference.

### Inference Process

For each detected entity:

1. **Context Vector Calculation**: Extract a text snippet around the entity (size controlled by `context_window_size`) and embed it
2. **Candidate Retrieval**: Compare context embedding against all name embeddings to find top matches above `short_similarity_threshold`
3. **Disambiguation**: If multiple CUIs are associated with the best-matching name, compare against CUI embeddings to select the final concept
4. **Filtering**: Apply CUI include/exclude filters and check against `long_similarity_threshold`

## Configuration

### Key Parameters - Static and Trainable
```python
config.components.linking = EmbeddingLinking(
    # Model settings
    embedding_model_name="sentence-transformers/all-MiniLM-L6-v2",
    max_token_length=128,
    
    # Context settings
    context_window_size=10,  # tokens on each side of entity
    
    # Similarity thresholds
    short_similarity_threshold=0.3,  # for candidate retrieval
    long_similarity_threshold=0.5,   # for final linking
    
    # Batch sizes
    embedding_batch_size=4096,
    linking_batch_size=512,
    
    # Filtering
    filters=Filters(
        cuis={"C0018802", "C0011849"},  # include only these
        cuis_exclude={"C0000001"}        # or exclude these
    ),
    
    # Advanced options
    use_ner_link_candidates=True,
    always_calculate_similarity=False,
    filter_before_disamb=True,
    gpu_device="cuda:0"  # or None for auto-detect
)
```
### Key Parameters - Trainable ONLY

```python
config.components.linking = EmbeddingLinking(
    # Training settings
    train_on_names: bool = True
    training_batch_size: int = 32
    embed_per_n_batches: int = 0

    # Model settings
    use_mention_attention: bool = True
    use_projection_layer: bool = True
    top_n_layers_to_unfreeze: int = 0
)
```

### Embedding Models

Any HuggingFace model compatible with sentence transformers will work. Popular options:

- `sentence-transformers/all-MiniLM-L6-v2` (default, fast and lightweight)
- `sentence-transformers/all-mpnet-base-v2` (higher quality)
- `UFNLP/gatortron-medium` (biomedical domain)
- `abhinand/MedEmbed-small-v0.1` (often the best performing)
- `microsoft/BiomedNLP-PubMedBERT-base-uncased-abstract-fulltext`

## Advanced Usage

### Re-generating Embeddings

If you modify your CDB or want to try a different model:

```python
linker = cat.get_component("embedding_linker")
linker.create_embeddings(
    embedding_model_name="microsoft/BiomedNLP-PubMedBERT-base-uncased-abstract-fulltext",
    max_length=256
)
```

### GPU Configuration

```python
# Use specific GPU
cat.config.components.linking.gpu_device = "cuda:1"

# Force CPU
cat.config.components.linking.gpu_device = "cpu"
```

### Filtering

```python
# Include only specific CUIs
cat.config.components.linking.filters.cuis = {"C0011849", "C0018802"}

# Exclude specific CUIs
cat.config.components.linking.filters.cuis_exclude = {"C0000001"}

# Note: If both are set, only include filters are applied
```

## Performance Considerations

- **First-time embedding generation**: Can take several minutes for large CDBs (millions of concepts)
- **GPU recommended**: 10-50x faster inference with CUDA
- **Batch sizes**: Increase if you have GPU memory available
- **Model selection**: Smaller models (e.g., MiniLM) are faster but may be less accurate than larger domain-specific models
- **Unfreezing layers**: The more layers you unfreeze of a model - the better the predictive power of the model _should_ increase. This will come at the cost of increased computation.
- **Using a projection layer**: This will have no (or a slightly negative) impact on static embeddings. On trainable embeddings this will result in a large performance increase (i.e. 50-75% increase in recall or more). This is always trainable, as that is the point of it. The computational cost is minimal.
- **Mention Attention**: This will generate embeddings for the tokens of interest based on the sourounding context - not the entire context of detected entity. This should always result in a performance increase, at zero computational cost. The only case where this might not be true is if the entire detected context is all of a detected entity, at which case performance will be exactly equal to not using mention attention.
- **embed_per_n_batches**: This is how many training batches have been completed before re-embedding all names / cuis. Setting this to 0 means that re-embedding will never occur, and must be done manually. Re-embedding more often can result in a slight performance increase. However this is a long process and should probably be avoided / tested. It's recomended to set this to 0, and re-embed manually every epoch.

## Limitations

- Does not support `prefer_frequent_concepts` or `prefer_primary_name` from the default linker (logs warnings if set)
- Requires pre-computed embeddings before inference

## Citation

If you use this plugin, please cite MedCAT:

```bibtex
@article{medcat2021,
    title={Medical Concept Annotation Tool (MedCAT)},
    author={Kraljevic, Zeljko and et al.},
    journal={arXiv preprint arXiv:2010.01165},
    year={2021}
}
```
