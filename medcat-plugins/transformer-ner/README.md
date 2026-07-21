# MedCAT Transformer NER

A MedCAT plugin that provides an transformer based NER component using transformer models from HuggingFace.

## Overview

This plugin replaces MedCAT's default NER component with a transformer-based approach that uses BIOES token classifcation to identify spans of text that contain medical entities. 

**Key features:**
- BIOES token format for accurate labeling of longer / shorter spans.
- CRF head to ensure consistent label generation.
- Trainable and configurable for all potential transformer huggingface language models.

## Requirements

- **MedCAT**: 2.0+ ([PyPI](https://pypi.org/project/medcat/) | [GitHub](https://github.com/CogStack/MedCAT))
- Python 3.10+
- PyTorch
- Transformers

## Installation

```bash
pip install medcat-transformer-ner
```

## Quick Start

### Replacing current NER with transformer NER

```python
from medcat.cat import CAT
from medcat_transformer_ner.transformer_ner import NER
from medcat_transformer_ner.config import TransformerNER

cat = CAT.load_model_pack("..")

cat.config.components.ner = TransformerNER()
cat.config.components.ner.comp_name = NER.name

cat.config.components.addons.clear()
cat._recreate_pipe()

cat.save_model_pack(target_folder="/data/adam/models/trainable/",
                    pack_name="kch_gstt_v2_NER_BioLinkBERT",
                    add_hash_to_pack_name=False,
                    make_archive=False
)
```

## How It Works

### Component Registration

The transformer NER has a default untrained transformers model from huggingface it downloads. Using `.load_transformers()` with another huggingface model will use that model instead.

### Inference Process

Pass a document through the transformer BIOES model tagging if each entity is:

1. **Beginning Of Entity Span**
2. **Intermediate Of Entity Span**
3. **Outside Of Entity Span**
4. **End Of Entity Span**
5. **Single Span Of Entity** - Meaning it is a single entity within its own token

## Configuration

### Key Parameters
```python
from medcat_transformer_ner.config import TransformerNER
from medcat.cat import CAT
cat = CAT.load_model_pack("..your transformer ner model..")

ner_component = cat._pipeline.get_component(CoreComponentType.ner)

# Do you want to only pass forward detected entities where there is a 
# perfect match in the name vocabulary?
ner_component.cnf_ner.require_link_candidates = True
# What pretrained transformers model would you like to use?
ner_component.load_transformers("michiyasunaga/BioLinkBERT-large")

```

### Suggested Models

Any HuggingFace model will work. However smaller models will be unable to model the task appropriately leading to significantly reduced performances. We strongly reccomend `BioLinkBERT-large`, as this is one of the smaller models that can appropriately detect entities. All models will be worth testing.

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
