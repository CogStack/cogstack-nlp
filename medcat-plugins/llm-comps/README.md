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
from medcat.vocab import Vocab
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

config = Config()
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

### Instruct an existing LLM-component-saved model:

If you've already got a model that's saved with the config specific to your
use case (e.g URL and model and the like) then you can just load it up and use
it like any other model.

However, if you've got a model saved with the right components, but the wrong
URL or model (or you just wish to change it) you can load and change these in
one go as follows:

```python
from medcat.cat import CAT

MODEL_PATH = "my_model_path"

LLM_URL = "api_endpoint_url:80/v1"
LLM_MODEL = "gemma:2b"

config_dict = {
    "components": {
        # for NER
        "ner": {
            "custom_cnf": {
                "base_url": LLM_URL,
                "model": LLM_MODEL,
            }
        },
        # for linking
        "linking": {
            "additional": {
                "base_url": LLM_URL,
                "model": LLM_MODEL,
            }
        }
    }
}

cat = CAT.load_model_pack(
    MODEL_PATH, config_dict=config_dict,
)
print(
    "CAT.get_entities",
    cat.get_entities("Patient had kidney disease")['entities']
)
```