# Medical  <img src="https://github.com/CogStack/cogstack-nlp/blob/main/media/cat-logo.png?raw=true" width=45> oncept Annotation Tool (version 2)

**There's a number of breaking changes in MedCAT v2 compared to v1.**
When moving from v1 to v2, please refer to the [migration guide](docs/migration_guide_v2.md).
Details on breaking are outlined [here](docs/breaking_changes.md).

[![Build Status](https://github.com/CogStack/cogstack-nlp/actions/workflows/medcat-v2_main.yml/badge.svg?branch=main)](https://github.com/CogStack/cogstack-nlp/actions/workflows/medcat-v2_main.yml/badge.svg?branch=main)
[![Documentation Status](https://readthedocs.org/projects/cogstack-nlp/badge/?version=latest)](https://readthedocs.org/projects/cogstack-nlp/badge/?version=latest)
[![Latest release](https://img.shields.io/github/v/release/CogStack/cogstack-nlp?filter=medcat/*)](https://github.com/CogStack/cogstack-nlp/releases/latest)
<!-- [![pypi Version](https://img.shields.io/pypi/v/medcat.svg?style=flat-square&logo=pypi&logoColor=white)](https://pypi.org/project/medcat/) -->

MedCAT can be used to extract information from Electronic Health Records (EHRs) and link it to biomedical ontologies like SNOMED-CT, UMLS, or HPO (and potentially other ontologies).
Original paper for v1 on [arXiv](https://arxiv.org/abs/2010.01165).

**Official Docs [here](https://cogstack-nlp.readthedocs.io/)**

**Discussion Forum [discourse](https://discourse.cogstack.org/)**

## Available Models

As MedCAT v2 is still in early release, we do not currently have any models publically available.
You can still use models for v1, however (see the [README](https://github.com/CogStack/cogstack-nlp/blob/main/medcat-v2/README.md) there).

If you wish you can also convert the v1 models into the v2 format (see [tutorial](https://github.com/CogStack/cogstack-nlp/blob/main/medcat-v2-tutorials/notebooks/introductory/migration/1._Migrate_v1_model_to_v2.ipynb)).

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
- **MedCAT 2.0.0**  was released 18. August 2025.
<!-- - **Paper** van Es, B., Reteig, L.C., Tan, S.C. et al. [Negation detection in Dutch clinical texts: an evaluation of rule-based and machine learning methods](https://doi.org/10.1186/s12859-022-05130-x). BMC Bioinformatics 24, 10 (2023).
- **New tool in the Cogstack ecosystem \[19. December 2022\]** [Foresight -- Deep Generative Modelling of Patient Timelines using Electronic Health Records](https://arxiv.org/abs/2212.08072)
- **New Paper using MedCAT \[21. October 2022\]**: [A New Public Corpus for Clinical Section Identification: MedSecId.](https://aclanthology.org/2022.coling-1.326.pdf)
- **Major Change to the Permissions of Use \[4. August 2022\]** MedCAT now uses the [Elastic License 2.0](https://github.com/CogStack/MedCAT/pull/271/commits/c9f4e86116ec751a97c618c97dadaa23e1feb6bc). For further information please click [here.](https://www.elastic.co/licensing/elastic-license)
- **New Downloader \[15. March 2022\]**: You can now [download](https://uts.nlm.nih.gov/uts/login?service=https://medcat.rosalind.kcl.ac.uk/auth-callback) the latest SNOMED-CT and UMLS model packs via UMLS user authentication.
- **New Feature and Tutorial \[7. December 2021\]**: [Exploring Electronic Health Records with MedCAT and Neo4j](https://towardsdatascience.com/exploring-electronic-health-records-with-medcat-and-neo4j-f376c03d8eef)
- **New Minor Release \[20. October 2021\]** Introducing model packs, new faster multiprocessing for large datasets (100M+ documents) and improved MetaCAT.
- **New Release \[1. August 2021\]**: Upgraded MedCAT to use spaCy v3, new scispaCy models have to be downloaded - all old CDBs (compatble with MedCAT v1) will work without any changes.
- **New Feature and Tutorial \[8. July 2021\]**: [Integrating 🤗 Transformers with MedCAT for biomedical NER+L](https://towardsdatascience.com/integrating-transformers-with-medcat-for-biomedical-ner-l-8869c76762a)
- **General \[1. April 2021\]**: MedCAT is upgraded to v1, unforunately this introduces breaking changes with older models (MedCAT v0.4),
  as well as potential problems with all code that used the MedCAT package. MedCAT v0.4 is available on the legacy
  branch and will still be supported until 1. July 2021
  (with respect to potential bug fixes), after it will still be available but not updated anymore.
- **Paper**: [What’s in a Summary? Laying the Groundwork for Advances in Hospital-Course Summarization](https://www.aclweb.org/anthology/2021.naacl-main.382.pdf)
- ([more...](https://github.com/CogStack/cogstack-nlp/blob/main/medcat-v2/media/news.md)) -->

## Installation

MedCAT v2 has its first full release
```
pip install medcat~=2.0.0
```
Do note that **this installs only the core MedCAT v2**.
**It does not necessary dependencies for `spacy`-based tokenizing or MetaCATs or DeID**.
However, all of those are supported as well.
You can install them as follows:
```
pip install "medcat[spacy]~=2.0.0" # for spacy-based tokenizer
pip install "medcat[meta-cat]~=2.0.0"  # for MetaCAT
pip install "medcat[deid]~=2.0.0"  # for DeID models
pip install "medcat[spacy,meta-cat,deid,rel-cat,dict-ner]~=2.0.0"  # for all of the above
```

## Demo

The MedCAT v2 demo web app is available [here](https://medcatv2.sites.er.kcl.ac.uk/).

## Tutorials
A guide on how to use MedCAT v2 is available at [MedCATv2 Tutorials](https://github.com/CogStack/cogstack-nlp/tree/main/medcat-v2-tutorials).
However, the tutorials are a bit of a work in progress at this point in time.


## Acknowledgements
Entity extraction was trained on [MedMentions](https://github.com/chanzuckerberg/MedMentions) In total it has ~ 35K entites from UMLS

The vocabulary was compiled from [Wiktionary](https://en.wiktionary.org/wiki/Wiktionary:Main_Page) In total ~ 800K unique words

## Powered By
A big thank you goes to [spaCy](https://spacy.io/) and [Hugging Face](https://huggingface.co/) - who made life a million times easier.


<!-- ## Citation
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
``` -->
