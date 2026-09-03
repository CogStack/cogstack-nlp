## MedCAT LLM component examples

This project aims to provide a few simple examples for LLM based components (for NER and/or linking).

**These are not designed to be the best implementation. They are designed as an example.**

### How to install

```
pip install medcat-llm-components
```

### How to use

#### Add to existing model

This way you can use the CDB already tied to the model.

```python
from medcat.cat import CAT
from medcat_llm_components.ner import LLMNERConfig
from medcat_llm_components.linker import LLMLinkConfig
### INPUT ###
# existing model
model_path = ""
# the URL to the (e.g) ollama instance
base_url = "my_ollama_ip:port/whatever"
# the model to use
llm_model = "gemma:2b"

### AUTOMATION ###
# NOTE: don't need to use both NER and linker
#       we just have one example for both
cat = CAT.load_model_pack(model_path)
# create configs
# ner
ner_cnf = LLMNERConfig(
    base_url=base_url,
    model=llm_model,
    # for other optional arguments such as prompt
    # refer to code or IDE inspection
)
# linker
linking_cnf = LLMLinkConfig(
    base_url=base_url,
    model=llm_model,
    # for other optional arguments such as prompt
    # refer to code or IDE inspection
)
# update model pack
# ner
cat.config.components.ner.comp_name = "llm_ner"
# NOTE: different path for NER and linker
cat.config.components.ner.custom_cnf = ner_cnf
# linking
cat.config.components.linking.comp_name = "llm_linker"
# NOTE: different path for NER and linker
cat.config.components.linking.additional = linking_cnf
# recreate pipe
cat._recreate_pipe()

print(cat.describe_pipeline())
# ready to use!
print(cat.get_entities("Anhedonia"))
```

### Create as part of a new model pack

You can create a new model pack yourself.
This will almost certainly be more involved.

```python
from medcat.cat import CAT
from medcat.cdb import CDB
from medcat.config import Config

from medcat_llm_components.ner import LLMNERConfig
from medcat_llm_components.linker import LLMLinkConfig

# the URL to the (e.g) ollama instance
base_url = "my_ollama_ip:port/whatever"
# the model to use
llm_model = "gemma:2b"

# create configs
# ner
ner_cnf = LLMNERConfig(
    base_url=base_url,
    model=llm_model,
    # for other optional arguments such as prompt
    # refer to code or IDE inspection
)
# linker
linking_cnf = LLMLinkConfig(
    base_url=base_url,
    model=llm_model,
    # for other optional arguments such as prompt
    # refer to code or IDE inspection
)

config = Config()# update model pack
config.components.ner.comp_name = "llm_ner"
config.components.ner.custom_cnf = ner_cnf
config.components.linking.comp_name = "llm_linker"
config.components.linking.additional = linking_cnf

vocab = Vocab()
# or load a CDB on its own with CDB.load("my_cdb.zip")
cdb = CDB(config)

cat = CAT(cdb, vocab)
print(cat.describe_pipeline())
# ready to use!
```
