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

