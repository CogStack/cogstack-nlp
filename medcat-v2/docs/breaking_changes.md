# Breaking changes compared to v1

There's a number of breaking changes to the API compared to v1.
This will attempt to list them all.
If something was missed, don't hesitate to create PR with the addition.
Though do note, that only the major API-level changes will be listed.

## API changes to CAT

### Training

Training is now separated from the main `CAT` class into its own class (`Trainer`) and module (`trainer.py`).
This affects the following methods (assumption is that `cat` is an instance of `CAT`):
|          v1 method          |           v2 method                |
| --------------------------- | ---------------------------------- |
| `cat.train`                 | `cat.trainer.train_unsupervised`   |
| `cat.train_supervised_raw`  | `cat.trainer.train_supervised_raw` |

### Model saving

|          v1 method          |           v2 method                |
| --------------------------- | ---------------------------------- |
| `cat.create_model_pack`     | `cat.save_model_pack`              |

### Removals

These methods were removed either due to a difference in approach or due to preceived unimportance.
Protected (starting with `_`) or private (starting with `__`) methods won't be recorded here.
If you were previously relying on some of the behaviour provided by these, don't hesitate to get in touch.

|            v1 method           |              Reason removed                   |
| ------------------------------ | --------------------------------------------- |
| `cat.train_supervised_from_json` | Don't want to be tightly coupled to a file format here |
| `cat.multiprocessing_batch_char_size` | There is currently only one multiprocessing method |
| `cat.multiprocessing_batch_docs_size` | and that is `CAT.get_entities_multi_texts` |
| `cat.get_json`                 | Unclear usecases                              |
| `def destroy_pipe`             | Unclear usecases                              |

## API Changes to CDB

The `CDB` class is now located in `medcat.cdb.cdb` module.
However, it can be imported from the package directly as well, same as before (`from medcat.cdb import CDB`).

### Names and CUIs are now mapped to variables differently

Instead of `cui2<stuff>` and `name2stuff` `dict`s, v2 provides `cui2info` and `name2info` mappings.
Either of these have a `dict` that defines per concept or name information.
Below you can see how to access the same things in the new version.

|          v1 method                |           v2 method                            | Notes |
| --------------------------------- | ---------------------------------------------- | ----- |
| `cdb.cui2names[cui]`              | `cdb.cui2info[cui]['names']`                   |       |
| `cdb.cui2snames[cui]`             | `cdb.cui2info[cui]['subnames']`                |       |
| `cdb.cui2count_train[cui]`        | `cdb.cui2info[cui]['count_train']`             |       |
| `cdb.cui2context_vectors[cui]`    | `cdb.cui2info[cui]['context_vectors']`         |       |
| `cdb.cui2type_ids[cui]`           | `cdb.cui2info[cui]['type_ids']`                |       |
| `cdb.cui2preferred_name[cui]`     | `cdb.cui2info[cui]['preferred_name']`          |       |
| `cdb.cui2average_confidence[cui]` | `cdb.cui2info[cui]['average_confidence']`      |       |
| `cdb.name2cuis[name]`             | `cdb.name2info[name]['per_cui_status'].keys()` | There's no need to track per CUI status (on a per name basis) and per name CUIs separately |
| `cdb.name2cuis2status[name]`      | `cdb.name2info[name]['per_cui_status']`        |       |
| `cdb.name2count_train[name]`      | `cdb.name2info[name]['count_train']`           |       |
| `cdb.snames`                      | `cdb._subnames`                                |       |
| `cdb.make_stats()`                | `cdb.get_basic_info()`                         |       |
| `CDB.load`                        | `cdb: CDB deserialise(<path>)`                 | Most end users shouldn't need to load the CDB on its own |


## API changes for Config

Some config parts have been moved around for clarity.
The below is the list of config parts that have been relocated.
**It must be noted that the ability to use `config[path] = value` was also removed.**

|          v1 location                    |           v2 location                                        | Notes |
| --------------------------------------- | ------------------------------------------------------------ | ----- |
| `config.linking`                        | `config.components.linking`                                  |       |
| `config.ner`                            | `config.components.ner`                                      |       |
| `config.ner`                            | `config.components.ner`                                      |       |


## API changes for Vocab

There weren't many changes to `Vocab`.
But we'll list them here nonetheless.

|          v1 method                |           v2 method                            | Notes |
| --------------------------------- | ---------------------------------------------- | ----- |
| `Vocab.load`                      | `vocab: Vocab = deserialise(<path>)`         | Most end users shouldn't need to load the Vocab on its own |


## Relocated packages / modules

Some packages and modules were relocated.
We can see the list of relocations here.

|          v1 location                    |           v2 location                                        | Notes |
| --------------------------------------- | ------------------------------------------------------------ | ----- |
| `medcat.meta_cat`                       | `medcat.components.addons.meta_cat.meta_cat`                |       |
| `medcat.utils.meta_cat`                 | `medcat.components.addons.meta_cat`                         |       |
| `medcat.config_meta_cat`                | `medcat.config.config_meta_cat`                             |       |
| `medcat.cdb_maker`                      | `medcat.model_creation.cdb_maker`                           |       |
| `medcat.tokenizers.meta_cat_tokenizers` | `medcat.components.addons.meta_cat.mctokenizers.tokenizers` | All MetACAT stuff now here |
| `medcat.rel_cat`                        | `medcat.components.addons.relation_extraction.rel_cat`      | All RelCAT stuff now here |
| `medcat.utils.relation_extraction.*`    | `medcat.components.addons.relation_extraction.*`            |       |
| `medcat.utils.ner.deid`                 | `medcat.components.ner.trf.deid`                            | Most DeID stuff now here |
| `medcat.utils.ner.model`                | `medcat.components.ner.trf.model`                           |       |
| `medcat.utils.ner.helpers`              | `medcat.components.ner.trf.helpers`                         |       |
| `medcat.tokenizer.transformers_ner`     | `medcat.components.ner.trf.tokenizer`                       |       |
| `medcat.ner.transformers_ner`           | `medcat.components.ner.tf.transformers_ner`                 |       |
| `medcat.datasets.transformers_ner`      | `medcat.utils.ner.transformers_ner`                         |       |
| `medcat.datasets.data_collator`         | `medcat.utils.ner.data_collator`                            |       |
