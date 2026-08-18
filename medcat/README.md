# Medical  <img src="https://github.com/CogStack/cogstack-nlp/blob/main/media/cat-logo.png?raw=true" width=45> oncept Annotation Tool

MedCAT can be used to extract information from Electronic Health Records (EHRs) and link it to biomedical ontologies like SNOMED-CT, UMLS, or HPO (and potentially other ontologies).
Original paper for v1 on [arXiv](https://arxiv.org/abs/2010.01165). 

Coming from MedCAT v1? See [here](docs/v1_info.md) for more info.

[![Build Status](https://github.com/CogStack/cogstack-nlp/actions/workflows/medcat-v2_main.yml/badge.svg?branch=main)](https://github.com/CogStack/cogstack-nlp/actions/workflows/medcat-v2_main.yml/badge.svg?branch=main)
[![Documentation Status](https://readthedocs.org/projects/cogstack-nlp/badge/?version=latest)](https://readthedocs.org/projects/cogstack-nlp/badge/?version=latest)
[![Latest release](https://img.shields.io/github/v/release/CogStack/cogstack-nlp?filter=medcat/*)](https://github.com/CogStack/cogstack-nlp/releases/latest)
[![pypi Version](https://img.shields.io/pypi/v/medcat.svg?style=flat-square&logo=pypi&logoColor=white)](https://pypi.org/project/medcat/)

**Official Docs [here](https://cogstack-nlp.readthedocs.io/)**

**Discussion Forum [discourse](https://discourse.cogstack.org/)**

## Available Models

We have 2 public v2 models available:
1) SnomedCT UK Clinical edition 39.0 (Oct 2024) and UK Drug Extension 39.0 (July 2024) based model enriched with UMLS 2024AA; trained only on MIMIC-IV
2) SnomedCT UK Clinical edition 40.2 (June 2025) and UK Drug Extension 40.3 (July 2024) based model enriched with UMLS 2024AA; trained only on MIMIC-IV

There are also a number of MedCAT v1 models available that can automatically be converted if required.

To download any of these models, please [follow this link](https://medcat.sites.er.kcl.ac.uk/auth-callback-api) and sign in using your NIH / UMLS API key. You will then be redirected to the MedCAT model download form. Please complete this form and you will be provided a download link.

While we encourage you use MedCAT v2 and the models in that native format, if you download an older version MedCAT v2 will be able to load it and covnert it to the format it knows. However, the loading process will be considerably longerin those cases.

If you wish you can also convert the v1 models into the v2 format (see [tutorial](../medcat-tutorials/notebooks/introductory/migration/1._Migrate_v1_model_to_v2.ipynb)).

```python
from medcat.utils.legacy import legacy_converter
from medcat.storage.serialisers import AvailableSerialisers
old_model = '<path to old v1 model>'
new_model_dir = '<dir to place new model in>'
legacy_converter.do_conversion(old_model_path, new_model_dir, AvailableSerialisers.dill)
```
OR
```bash
model_path = "models/medcat1_model_pack.zip"
new_model_folder = "models"  # file in this folder
! python -m  medcat.utils.legacy.legacy_converter $model_path $new_model_folder --verbose
```

## News
- **New public 2024 and 2025** Snomed models were uploaded and made available 7. October 2025.
- **MedCAT 2.0.0**  was released 18. August 2025.

[News pre v2.0.0](docs/v1_news.md).

## Installation

MedCAT v2 has its first full release
```
pip install medcat
```
Do note that **this installs only the core MedCAT v2**.
**It does not necessary dependencies for `spacy`-based tokenizing or MetaCATs or DeID**.
However, all of those are supported as well.
You can install them as follows:
```
pip install "medcat[spacy]" # for spacy-based tokenizer
pip install "medcat[meta-cat]"  # for MetaCAT
pip install "medcat[deid]"  # for DeID models
pip install "medcat[spacy,meta-cat,deid,rel-cat,dict-ner]"  # for all of the above
```

### Installing plugins

MedCAT v2 supports **external plugins** that can provide new components (e.g. alternative NER models, addons, tokenizers) via Python entry points.

- **Curated plugins**: The `medcat.plugins.catalog` module ships with a curated plugin catalog that can be updated from a remote JSON file.
- **Installer**: The `medcat.plugins.installer.PluginInstallationManager` wraps a `pip`-based installer and knows how to resolve a compatible plugin version for your current MedCAT version.
- **CLI**: You can install curated plugins directly from the command line:

```bash
python -m medcat plugins install medcat-gliner
```

This will:

- look up `medcat-gliner` in the curated catalog,
- resolve a version compatible with your installed MedCAT,
- and install it using `pip`.

You can also:

- pass `--dry-run` to show what would be installed without making changes:

  ```bash
  python -m medcat plugins install --dry-run medcat-gliner
  ```

- override the version/ref explicitly (e.g. when testing a branch or tag):

  ```bash
  python -m medcat plugins install medcat-gliner --force-version main
  ```

If a plugin requires authentication (for example, private Git repositories), MedCAT will log a warning and the installer will surface pip’s error messages if credentials are missing or incorrect.

### Version / update checking

MedCAT now has the ability to check for newer versions of itself on PyPI (or a local mirror of it).
This is so users don't get left behind too far with older versions of our software.
This is configurable by evnironmental variables so that sys admins (e.g for JupyterHub) can specify the settings they wish.
Version checks are done once a week and the results are cached.

Below is a table of the environmental variables that govern the version checking and their defaults.

| Variable | Default | Description |
|-----------|----------|-------------|
| **`MEDCAT_DISABLE_VERSION_CHECK`** | *(unset)* | When set to `true`, `yes` or `disable`, disables the version update check entirely. Useful for CI environments, offline setups, or deployments where external network access is restricted. |
| **`MEDCAT_PYPI_URL`** | `https://pypi.org/pypi` | Base URL used to query package metadata. Can be changed to a PyPI mirror or internal repository that exposes the `/pypi/{pkg}/json` API. |
| **`MEDCAT_MINOR_UPDATE_THRESHOLD`** | `3` | Number of newer **minor** versions (e.g. `1.4.x`, `1.5.x`) that must exist before MedCAT emits a “newer version available” log message. |
| **`MEDCAT_PATCH_UPDATE_THRESHOLD`** | `3` | Number of newer **patch** versions (e.g. `1.3.1`, `1.3.2`, `1.3.3`) on the same minor line required before emitting an informational update message. |
| **`MEDCAT_VERSION_UPDATE_LOG_LEVEL`** | `INFO` | Logging level used when reporting available newer versions (minor/patch thresholds). Accepts any valid `logging` level string (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`). |
| **`MEDCAT_VERSION_UPDATE_YANKED_LOG_LEVEL`** | `WARNING` | Logging level used when reporting that the current version has been **yanked** on PyPI. Accepts the same values as above. |

## Demo

The MedCAT v2 demo web app is available [here](https://medcat.sites.er.kcl.ac.uk/).

## Key Concepts

- **Components**: The building blocks of MedCAT (NER, Entity Linking, preprocessing, etc.)
- **Addons**: Components that extend the core NER+EL pipeline with additional processing stages
- **Plugins**: External packages that provide new component implementations or other functionality via entry points

See [Architecture Documentation](docs/architecture.md) for detailed information.

## Tutorials
A guide on how to use MedCAT v2 is available at on the medcat documentation page on [docs.cogstack.org](https://docs.cogstack.org)

## Acknowledgements
Entity extraction was trained on [MedMentions](https://github.com/chanzuckerberg/MedMentions) In total it has ~ 35K entites from UMLS

The vocabulary was compiled from [Wiktionary](https://en.wiktionary.org/wiki/Wiktionary:Main_Page) In total ~ 800K unique words

## Powered By
A big thank you goes to [spaCy](https://spacy.io/) and [Hugging Face](https://huggingface.co/) - who made life a million times easier.


## Citation
MedCAT v2 citation:
```
@inproceedings{ratas-etal-2026-medcat,
    title = "{M}ed{CAT} v2: a modular, extensible architecture for clinical named entity recognition and linking under real-world privacy and compute constraints",
    author = "Ratas, Mart  and
      Searle, Thomas  and
      Sutton, Adam  and
      Dobson, Richard",
    editor = "Demner-Fushman, Dina  and
      Ananiadou, Sophia  and
      Roberts, Kirk  and
      Tsujii, Junichi",
    booktitle = "{B}io{NLP} 2026",
    month = jul,
    year = "2026",
    address = "San Diego, California",
    publisher = "Association for Computational Linguistics",
    url = "https://aclanthology.org/2026.bionlp-1.17/",
    doi = "10.18653/v1/2026.bionlp-1.17",
    pages = "191--198",
    ISBN = "979-8-89176-434-7",
    abstract = "MedCAT is an open-source framework for clinical named entity recognition and linking (NER+L) widely used in research and healthcare settings. We present MedCAT v2, a re-engineered version designed to improve modularity, extensibility, and maintainability while preserving the core functionality and performance of previous releases. The new architecture introduces a registry-based component system and a flexible pipeline that enables easy substitution of components, integration of alternative methods, and future expansion, including support for pre-trained components across the full NER+L and contextualisation workflow. This enables systematic exploration of clinical NER+L design trade-offs by evaluating different components in the pipeline. Evaluation across multiple public datasets shows equivalent or improved performance compared to earlier versions, with reduced integration overhead and improved runtime flexibility. The framework also supports optional extensions such as meta-annotation, relation extraction, providing a unified and reproducible environment for clinical NLP in real-world settings."
}
```
<details>
<summary>MedCAT v1 citation</summary>

```
@ARTICLE{Kraljevic2021-ln,
  title="Multi-domain clinical natural language processing with {MedCAT}: The Medical Concept Annotation Toolkit",
  author="Kraljevic, Zeljko and Searle, Thomas and Shek, Anthony and Roguski, Lukasz and Noor, Kawsar and Bean, Daniel and Mascio, Aurelie and Zhu, Leilei and Folarin, Amos A and Roberts, Angus and Bendayan, Rebecca and Richardson, Mark P and Stewart, Robert and Shah, Anoop D and Wong, Wai Keong and Ibrahim, Zina and Teo, James T and Dobson, Richard J B",
  journal="Artif. Intell. Med.",
  volume=117,
  pages="102083",
  month=jul,
  year=2021,
  issn="0933-3657",
  doi="10.1016/j.artmed.2021.102083"
}
</details>
```
