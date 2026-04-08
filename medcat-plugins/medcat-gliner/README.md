# MedCAT-gliner

This provides [gliner](https://github.com/urchade/GLiNER) based NER step for MedCAT core library.

# Usage

First install from PyPI, e.g:
```
pip install medcat-gliner
```
Subsequently, if you have an existing model, you should be able to just change the NER component:
```
cat = CAT.load_model_pack("path/to/existing/model")
# change component
from medcat_gliner import GLiNERConfig
cat.config.components.ner.comp_name = "gliner_ner"
cat.config.components.ner.custom_cnf = GLiNERConfig()
# recreate pipe with new NER component
cat._recreate_pipe()
# use as needed
```

## NER recall comparison (linkable SNOMED entities)

The following results compare the existing NER (vocab based NER with spell checking) implementation with the gliner implementation when used as the NER component within MedCAT.
Evaluation was performed on the **2023 SNOMED CT Linking Challenge** dataset.

> **Important caveat**
> This is **not a measure of general NER quality**.
> Recall is computed only with respect to annotated, linkable SNOMED CT entities present in the linking dataset.
> Mentions outside the annotation scope are treated as false positives by construction, so precision is not meaningful here.

| Implementation         | True Positives | False Negatives | Recall | Runtime |
| ---------------------- | -------------- | --------------- | ------ | ------- |
| Vocab based NER        | 10,545         | 3,917           | 0.729  | ~5m 50s |
| GliNER implementation  | 7,971          | 6,491           | 0.551  | ~34m    |

As we can see, for this dataset, GliNER is significantly slower and performs worse than the standard vocab based implementation. This is likely because the vocab based NER step has been configured and tuned to work best within the MedCAT pipeline. It is likely that with additional tuning the GliNER implementation could perform as good or better than the vocab based linker does.
