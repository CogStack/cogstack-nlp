# MedCAT v2 Migration Guide

Welcome to [MedCAT v2](https://docs.cogstack.org/projects/nlp/en/latest/)!

This guide is for users upgrading from **v1.x** to **v2.x** of MedCAT.
It covers what’s changed, what steps one needs to do to upgrade, and what to expect from the new version.
For most single threaded inference users, things will continue to work as before.
Though APIs for training (both supervised and unsupervised) have been **refactored** somewhat.

---

## Why v2?

MedCAT v2 is a refactor designed to:
- Increase modularity
  - The core library is a lot more light weight and only includes essential components
  - Additional features (many of which were always provided in v1) that need to explicitly be specified upon install
    - `spacy` for tokenizing
    - `deid` for transformers based NER / deidentification
    - `meta-cat` for meta annotations (both LSTM and BERT)
    - `rel-cat` for relation extraction
  - The above means that `pip install medcat>=2.0` will **not** include everything that came with v1
    - And **models built / saved in v1 will not be able to loaded** in this install
    - There will be more details on installs in the next section(s)
  - This comes with a number of clear advantages
    - Smaller installs
      - You don't need to install components you're not going to use
    - Better separation / grouping of dependencies
      - Each separate feature defines their own dependencies
- Lower internal coupling with `spacy`
  - This allows us to use other tokenizers, at least for the built in NER and Linker
  - There's now registration available for other tokenizers
  - There's even an example of a regular expression based tokenizer built into the library
    - This serves more as a sample rather than an actual alternative
- Increase extensibility and flexibility
  - It's now a lot easier to create new components
    - Core components (NER, Linker)
    - Addons (MetaCAT, RelCAT)
- Improve maintainability of code and models
- Prepare for future use cases and integrations

---

## Who should read this?

If you're:
- Using MedCAT v1 (almost everything prior to **August 2025**)
- Loading or training models saved before that date
- Calling internal APIs (beyond basic `cat.get_entities`)

...then this guide is for you.

---

## How to install v2

Upgrading to the latest MedCAT version depends a little bit on which features you want / need.
If you want an identical experience to v1, you should be able to simply:

```bash
pip install -U "medcat[spacy,meta-cat,rel-cat,deid]>=2.0"
```

However, you may want to avoid installing of some of the additional features if you do not need them.
Here's a list of the additional features you can opt for with what they're used for.
| Feature Group       | Install Name | Description                                                                |
| ------------------- | ------------ | -------------------------------------------------------------------------- |
| `spaCy` Tokenizer   | `spacy`      | Enables `spacy`-based tokenization, as used in MedCAT v1                   |
| MetaCAT Annotations | `meta-cat`   | Supports meta-annotations like temporality, presence, and relevance        |
| Transformer NER     | `deid`       | Enables transformer-based NER, primarily used for de-identification models |
| Relation Extraction | `rel-cat`    | Adds support for extracting relations between entities                     |
| Dictionary NER      | `dict-ner`   | Example dictionary NER module (experimental and rarely needed)             |

## Summary of Changes

See the full list of breaking changes [here](breaking_changes.md).
This is just a small summary

### What hasn’t changed
- Core single threaded inference APIs (`cat.get_entities`, `cat.__call__`)
- Model loading: `CAT.load_model_pack` still works very similarly
- Your existing v1 models are still usable
  - They will be converted on the fly when loaded

### What _has_ changed
- Training goes through a new class-based API
  - Instead of `cat.train` you can use `cat.trainer.train_unsupervised`
  - Instead of `cat.train_supervised_raw` you can use `cat.trainer.train_supervised_raw`
- Save method renamed somewhat to be
  - Renamed from `cat.create_model_pack` to `cat.save_model_pack`
- Internal structure of concepts / names is more structured
  - There's the `cdb.cui2info` and `cdb.name2info` maps
  - More details in the breaking changes overview
- Models are saved in a new format
  - The idea was to simplify the (potential) addition of other serialisation options
  - Most of the model handling is still the same
    - There's a `.zip` to move around if/when needed
    - The model pack unpacks into its components
- Model components are saved differently
  - This mostly affects MetaCAT and RelCAT models
  - Components are saved in the `saved_components` folder within the model folder
  - E.g `saved_components/addon_meta_cat.Presence` for MetaCAT and `addon_rel_cat.rel_cat` for RelCAT

## ⚠️ Loading v1 models

MedCAT v2 supports loading v1 models.
There is no need to retrain them.
However, loading will:
- be significantly slower due to on-the-fly conversion
- show a warning message about this slowdown

We recommend re-saving v1 models using `cat.save_model_pack` in v2 format to mitigate this.


## Updated Tutorials

All v2 tutorials have been completely redone.
They do not go as far into detail in everything as the v1 tutorials did.
But they should hopefully cover most of the use cases
The v2 tutorials are available [here](https://github.com/CogStack/cogstack-nlp/tree/main/medcat-v2-tutorials).

## Updated `working_with_cogstack` scripts

The `working_with_cogstack` scripts have also been upgraded to support v2.
The changes are currently in [this PR](https://github.com/CogStack/working_with_cogstack/pull/20).
They have not yet been merged in to the `main` branch but will be in the near future.
At that point, there will probably be a separate branch to keep track of v1-specific scripts.

## MedCATtrainer

MedCATtrainer has been modified to work with v2 in [this PR](https://github.com/CogStack/MedCATtrainer/pull/253).
However, as of writing, this change has not yet been merged in or been released.
The v2-supporting release will most likely be released as **v3** on the trainer side.

## Feedback welcome!

We’d love your input / feedback!
Please report any issues or feature requests you encounter.
That includes (but is not limited to)
- Inability to use / run / load old models
- Missing or unclear documentation
- Unexpected errors or regressions
- Confusing logs or error messages
- Any other usability feedback

Create a [GitHub issue](https://github.com/CogStack/cogstack-nlp/issues/new) or start a thread on [Discourse](https://discourse.cogstack.org/).

## FAQ

**Q: Do I need to retrain my model?**

A: v1 models still work, but loading them is slower. We recommend re-saving after loading.

**Q: Why is model loading slower than before?**

A: v1 models are converted at load time to the new internal format. Once re-saved, load speed will be similar to before

**Q: Does inference break in v2?**

A: Using `cat.get_entities` should be identical, but multiprocessing is somewhat different, see [breaking changes](breaking_changes.md) for details.

**Q: What extras do I need for a converted NER+EL model (no MetaCAT)?**

A: You just need `spacy`. So `pip install "medcat[spacy]>=2.0"` should be sufficient.

**Q: What extras do I need for a converted DeID model?**

A: You need `spacy` (for base tokenization) as well as `deid`. So `pip install "medcat[spacy,deid]>=2.0"` should be sufficient.

**Q: What extras do I need for a converted NER+L model with MetaCAT?**

A: You need `spacy` (for base tokenization) as well as `meta-cat`. So `pip install "medcat[spacy,meta-cat]>=2.0"` should be sufficient.

**Q: What extras do I need for a converted NER+L model with RelCAT?**

A: You need `spacy` (for base tokenization) as well as `rel-cat`. So `pip install "medcat[spacy,rel-cat]>=2.0"` should be sufficient.

**Q: How do I train in v2?**

A: Training now uses a dedicated `medcat.trainer.Trainer` class. See tutorials and/or [breaking changes](breaking_changes.md) for details.

**Q: Are v1 `working_with_cogstack` scripts still supported?**

A: No. Many will break due to internal changes. Please refer to the new scripts in the [relevant branch](https://github.com/CogStack/working_with_cogstack/pull/20).


**Q: Does MedCATtrainer work out of the box for v2?**

A: No. While the [changes have been ported](https://github.com/CogStack/MedCATtrainer/pull/253), there is currently no release for these changes and it is unlikely to already be spun up yet. But it will be soon.


**Q: Does `medcat-service` work for serving a model?**

A: The [service](https://github.com/CogStack/cogstack-nlp/tree/main/medcat-service) has been fully ported to v2.


**Q: Does the demo app work with v2?**

A: The [demo web app](https://github.com/CogStack/cogstack-nlp/tree/main/medcat-demo-app) has been fully ported to v2.
