# MedCAT Embedding Linker

A MedCAT plugin that provides an a Rawstring tokenizer, essentially splitting on whitespace characters (" ", "\n", "\t") only.

## Overview

This plugin replaces MedCAT's default tokenizing components with with rawstring, that are not limited by requiring SpaCy representations that perform linking.

## Requirements

- **MedCAT**: 2.0+ ([PyPI](https://pypi.org/project/medcat/) | [GitHub](https://github.com/CogStack/MedCAT))
- Python 3.10+

## Installation

```bash
pip install medcat-rawstring-tokenizer
```

## Quick Start

### Replacing current tokenizer with a rawstring_tokenizer

```python
from medcat.cat import CAT
from medcat_rawstring_tokenizer.tokenizer import RawstringTokenizer
from medcat.tokenizing.tokenizers import register_tokenizer

MODEL_PACK_PATH = ".."
TARGET_FOLDER = ".."
TARGET_PACK_NAME = ".."
TOKENIZER_NAME = "rawstring_tokenizer"

# The custom tokenizer must be registered before we rebuild the pipeline.
register_tokenizer(TOKENIZER_NAME, RawstringTokenizer)

cat = CAT.load_model_pack(MODEL_PACK_PATH)
print("Tokenizer provider before:", cat.config.general.nlp.provider)

# Switch tokenizer provider in config, then recreate pipeline to apply it.
cat.config.general.nlp.provider = TOKENIZER_NAME

cat.config.components.addons.clear()
cat._recreate_pipe()

print("Tokenizer provider after:", cat.config.general.nlp.provider)

cat.save_model_pack(
    target_folder=TARGET_FOLDER,
    pack_name=TARGET_PACK_NAME,
    add_hash_to_pack_name=False,
    make_archive=False,
)
print("Saved model pack to:", f"{TARGET_FOLDER.rstrip('/')}/{TARGET_PACK_NAME}")
```

## How It Works

### Component Registration

Register the tokenizer by name before trying to add the tokenizer to the pipeline. If loading a model with a rawstring tokenizer register it beforehand.

### Embedding Generation

## Limitations

- Can NOT be used with the default `context_based_linker` as, that uses spacy tokens and spacy embeddings for linking. Which are not used with this tokenizer.

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
