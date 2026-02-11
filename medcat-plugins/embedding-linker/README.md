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

```python
from medcat.cat import CAT
from medcat.config import Config
from medcat.components.types import CoreComponentType

from medcat_embedding_linker import EmbeddingLinking

# Load your MedCAT model
cat = CAT.load_model_pack("path/to/model_pack")

# Configure the embedding linker
cat.config.components.linking = EmbeddingLinking()
cat.config.components.linking.embedding_model_name = "sentence-transformers/all-MiniLM-L6-v2"

# Recreate the pipeline to register the new linker
cat._recreate_pipe()

# Generate embeddings for your concept database
linker = self.get_component(CoreComponentType.linking)
# create 
linker.create_embeddings()

# Use as normal
entities = cat.get_entities("Patient presents with chest pain and dyspnea.")
```

## How It Works

### Component Registration

The embedding linker automatically registers itself as `embedding_linker` when `EmbeddingLinking` config is detected. It implements MedCAT's `AbstractEntityProvidingComponent` interface and is lazily loaded when the pipeline is created.

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

### Key Parameters

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

### Embedding Models

Any HuggingFace model compatible with sentence transformers will work. Popular options:

- `sentence-transformers/all-MiniLM-L6-v2` (default, fast and lightweight)
- `sentence-transformers/all-mpnet-base-v2` (higher quality)
- `UFNLP/gatortron-medium` (biomedical domain)
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

## Limitations

- Does not support `prefer_frequent_concepts` or `prefer_primary_name` from the default linker (logs warnings if set)
- Training mode is not applicable (logs warning if enabled)
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
