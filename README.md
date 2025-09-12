# Cogstack NLP

[![Build Status](https://github.com/CogStack/cogstack-nlp/actions/workflows/medcat-v2_main.yml/badge.svg?branch=main)](https://github.com/CogStack/cogstack-nlp/actions/workflows/medcat-v2_main.yml/badge.svg?branch=main)
[![Documentation Status](https://readthedocs.org/projects/cogstack-nlp/badge/?version=latest)](https://readthedocs.org/projects/cogstack-nlp/badge/?version=latest)
[![Latest release](https://img.shields.io/github/v/release/CogStack/cogstack-nlp?filter=medcat/*)](https://github.com/CogStack/cogstack-nlp/releases/latest)
<!-- [![pypi Version](https://img.shields.io/pypi/v/medcat.svg?style=flat-square&logo=pypi&logoColor=white)](https://pypi.org/project/medcat/) -->

CogStack Natural Language Processing offers tools to process and extract information from clinical text and documents in Electronic Health Records (EHRs).

The primary NLP focus is the [Medical Concept Annotation Tool](medcat-v2/README.md) (MedCAT), a self-supervised machine learning algorithm for extracting concepts using any concept vocabulary including UMLS/SNOMED-CT. See the paper on [arXiv](https://arxiv.org/abs/2010.01165).


**Official Docs [here](https://docs.cogstack.org)**

**Discussion Forum [discourse](https://discourse.cogstack.org/)**


## Projects

### NLP
- [Medical Concept Annotation Tool](medcat-v2/README.md): MedCAT can be used to extract information from Electronic Health Records (EHRs) and link it to biomedical ontologies like SNOMED-CT, UMLS, or HPO (and potentially other ontologies).
- [Medical Concept Annotation Tool Trainer](medcat-trainer/README.md): MedCATTrainer is an interface for building, improving and customising a given Named Entity Recognition and Linking (NER+L) model (MedCAT) for biomedical domain text.
- [MedCAT Service](medcat-service/README.md): A REST API wrapper for [MedCAT](https://github.com/CogStack/cogstack-nlp/blob/main/medcat-v2/), allowing you to send text for processing and receive structured annotations in response.

### Learning and Demos
- [Deidentify app](anoncat-demo-app/README.md): Demo for AnonCAT. It uses [MedCAT](https://github.com/CogStack/cogstack-nlp/tree/main/medcat-v2), an advanced natural language processing tool, to identify and classify sensitive information, such as names, addresses, and medical terms.
- [MedCAT Demo App](medcat-demo-app/README.md): A simple web application showcasing how to use MedCAT for clinical text annotation.
- [MedCAT Tutorials](medcat-v2-tutorials/README.md): The MedCAT Tutorials privde an interactive learning path for using MedCAT