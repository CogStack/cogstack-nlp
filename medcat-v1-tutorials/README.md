# MedCAT Tutorials

[![Build Status](https://github.com/CogStack/MedCATtutorials/actions/workflows/main.yml/badge.svg?branch=main)](https://github.com/CogStack/MedCATtutorials/actions/workflows/main.yml?query=branch%3Amain)

## Introductory tutorials

In this tutorial, we will walk you through each stage of a basic MedCAT project. The blog posts are there to tell a story and explain why several steps or processes which we have decided to take are necessary. While the Jupyter Notebooks are for a hands-on experience building and training your MedCAT models for information extraction tasks.

| Part | Title                                                                       | Google Colab                                                                       | Blog Post |
| ---- |-----------------------------------------------------------------------------|------------------------------------------------------------------------------------|-----------|
| 1    | Introduction                                                               | -                                                                                  | [TDS](https://medium.com/@w_is_h/medcat-introduction-analyzing-electronic-health-records-e1c420afa13a)         |
| 1.1  | [\[OPTIONAL\] Logging With MedCAT](https://htmlpreview.github.io/?https://github.com/CogStack/MedCATtutorials/blob/main/notebooks/introductory/Part_1_1_OPTIONAL_Logging_With_MedCAT.html) | [![Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/CogStack/MedCATtutorials/blob/main/notebooks/introductory/Part_1_1_OPTIONAL_Logging_With_MedCAT.ipynb) | -
| 2    | [Data set Preparation and Basic Statistics](https://htmlpreview.github.io/?https://github.com/CogStack/MedCATtutorials/blob/main/notebooks/introductory/Part_2_Dataset_Analysis_and_Preparation.html)                                    | [![Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/CogStack/MedCATtutorials/blob/main/notebooks/introductory/Part_2_Dataset_Analysis_and_Preparation.ipynb) | [TDS](https://medium.com/towards-data-science/medcat-dataset-analysis-and-preparation-be8bc910bd6d)         |
| 3.1  | [Building a new Concept Database (CDB) and Vocabulary (Vocab)](https://htmlpreview.github.io/?https://github.com/CogStack/MedCATtutorials/blob/main/notebooks/introductory/Part_3_1_Building_a_Concept_Database_and_Vocabulary.html)                 | [![Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/CogStack/MedCATtutorials/blob/main/notebooks/introductory/Part_3_1_Building_a_Concept_Database_and_Vocabulary.ipynb) | [TDS](https://medium.com/towards-data-science/medcat-extracting-diseases-from-electronic-health-records-f53c45b3d1c1)         |
| 3.2  | [Unsupervised training and NER+L](https://htmlpreview.github.io/?https://github.com/CogStack/MedCATtutorials/blob/main/notebooks/introductory/Part_3_2_Extracting_Diseases_from_Electronic_Health_Records.html)                                             | [![Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/CogStack/MedCATtutorials/blob/main/notebooks/introductory/Part_3_2_Extracting_Diseases_from_Electronic_Health_Records.ipynb) | [TDS](https://medium.com/towards-data-science/medcat-extracting-diseases-from-electronic-health-records-f53c45b3d1c1)         |
| 3.3  | [Technical model optimisations](https://htmlpreview.github.io/?https://github.com/CogStack/MedCATtutorials/blob/main/notebooks/introductory/Part_3_3_Model_technical_optimisations.html)                                             | [![Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/CogStack/MedCATtutorials/blob/main/notebooks/introductory/Part_3_3_Model_technical_optimisations.ipynb) | -         |
| 4.1  | [Creating a tokenizer model (huggingface) and embeddings for MetaAnnotations](https://htmlpreview.github.io/?https://github.com/CogStack/MedCATtutorials/blob/main/notebooks/introductory/Part_4_1_ByteLevelBPETokenizer_and_Embeddings.html) | [![Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/CogStack/MedCATtutorials/blob/main/notebooks/introductory/Part_4_1_ByteLevelBPETokenizer_and_Embeddings.ipynb) | -         |
| 4.2  | [Supervised training and fine-tuning + Meta-annotations](https://htmlpreview.github.io/?https://github.com/CogStack/MedCATtutorials/blob/main/notebooks/introductory/Part_4_2_Supervised_Training_and_Meta_annotations.html)                      | [![Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/CogStack/MedCATtutorials/blob/main/notebooks/introductory/Part_4_2_Supervised_Training_and_Meta_annotations.ipynb) | -         |
| 4.3  | [Annotating documents with the full MedCAT pipeline with MetaAnnotations](https://htmlpreview.github.io/?https://github.com/CogStack/MedCATtutorials/blob/main/notebooks/introductory/Part_4_3_Annotating_documents_with_the_full_MedCAT_pipeline_with_MetaAnnotations.html)     | [![Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/CogStack/MedCATtutorials/blob/main/notebooks/introductory/Part_4_3_Annotating_documents_with_the_full_MedCAT_pipeline_with_MetaAnnotations.ipynb) | -         |
| 5    | [Analysing the results](https://htmlpreview.github.io/?https://github.com/CogStack/MedCATtutorials/blob/main/notebooks/introductory/Part_5_Prevalence_of_Physical_and_Mental_Diseases.html)                                                       | [![Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/CogStack/MedCATtutorials/blob/main/notebooks/introductory/Part_5_Prevalence_of_Physical_and_Mental_Diseases.ipynb) | [TDS](https://medium.com/@w_is_h/prevalence-of-physical-and-mental-diseases-450c0f4f5851)         |
| 6.1  | [Supervised training Relation-annotations](https://htmlpreview.github.io/?https://github.com/CogStack/MedCATtutorials/blob/rel_cat_tutorials/notebooks/introductory/Part_6_1_Supervised_Training_Relation_Extraction.html) | - | - |
| 6.2  | [Infering relationships from annotations](https://htmlpreview.github.io/?https://github.com/CogStack/MedCATtutorials/blob/rel_cat_tutorials/notebooks/introductory/Part_6_2_Infering_relations_from_annotations_with_Relation_toolkit.html) | - | - |

## Specialised tutorials

These tutorials expand upon specific aspects of the topics covered across the introductory tutorials. If there is anything in particular you would like us to cover in the future, let us know!

| Part | Title                                                             | Google Colab                                                                                 |
| ---- |-------------------------------------------------------------------|----------------------------------------------------------------------------------------------|
| -    |[Working with SNOMED CT and building a custom Concept Database (CDB)](https://htmlpreview.github.io/?https://github.com/CogStack/MedCATtutorials/blob/main/notebooks/specialised/Preprocessing_SNOMED_CT.html)| [![Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/CogStack/MedCATtutorials/blob/main/notebooks/specialised/Preprocessing_SNOMED_CT.ipynb)|
| -    |[Comparing models using regression test tooling](https://htmlpreview.github.io/?https://github.com/CogStack/MedCATtutorials/blob/main/notebooks/specialised/Comparing_Models_with_RegressionSuite.html)| [![Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/CogStack/MedCATtutorials/blob/main/notebooks/specialised/Comparing_Models_with_RegressionSuite.ipynb)|


## Development/Editing

Make sure [jupyter](https://docs.jupyter.org/en/latest/install.html) and [jq](https://stedolan.github.io/jq/download/) are installed and available on your path. Modifying the companion HTML version directly is discouraged and instead install the following pre-commit hook which will generate them during committing your change on `.ipynb` files:
```
git config --local core.hooksPath git-config/hooks
```

To inspect change during code review, visit [Colab](https://colab.research.google.com/github/CogStack/MedCATtutorials/blob) and select the target branch and tutorial. After it is opened, click `File | Revision history` and select start and end revisions you are interested in.


## Known Issues:
* For ContextualVersionConflict on Google Colab, you need to restart the runtime and run the cell again.
* The pre-commit hook requires nbconvert<6 and jinja2<=3.0.