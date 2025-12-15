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
