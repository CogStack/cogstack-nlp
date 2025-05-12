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
| `cat.get_entities_multi_texts` | Multiprocessing will be addressed differently |
| `cat.multiprocessing_batch_char_size` |                 ==||==                 |
| `cat.multiprocessing_batch_docs_size` |                 ==||==                 |
| `cat.get_json`                 | Unclear usecases                              |
| `def destroy_pipe`             | Unclear usecases                              |
