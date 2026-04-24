# MedCAT Tutorials

The MedCAT Tutorials provide an interactive learning path for using MedCAT.

NOTE: These tutorials are aimed at developers and / or people creating their own models.
For every day usage (e.g inference) the [medcat-scripts](https://github.com/CogStack/cogstack-nlp/tree/main/medcat-scripts) portion would probably be more useful.

## Interactive Tutorials

These tutorials are written as real, executable code in jupyter notebooks. The version on docs.cogstack.org is read only, but you could instead choose to follow along and run the code as you go.

To get set up to run the tutorials interactively, clone the repo and install the tutorial dependencies.

```bash
git clone https://github.com/CogStack/cogstack-nlp.git
cd cogstack-nlp/medcat-v2-tutorials

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```
You can now open the notebook in vscode and run the tutorials. Alternatively you could use `pip install jupyter` and run `jupyter lab` to do this on the command line. 

## Introductory tutorials

### Migration of v1 models

| Part | Title                                                                       |
| ---- |-----------------------------------------------------------------------------|
| 1.   |  [Migrate a v1 model to v2](introductory/migration/1._Migrate_v1_model_to_v2/)                                    |

### Basic (regex-tokenizer) tutorials

| Part | Title                                                                       |
| ---- |-----------------------------------------------------------------------------|
| 1.   |  [Building a Concept Database and a Vocab](introductory/basic/1._Build_a_Concept_Database_and_a_Vocabulary/)                                    |
| 2.   | [Unsupervised training on model](introductory/basic/2._Unsupervised_training_on_model/) |
| 3.   | [Supervised training on model](introductory/basic/3._Supervised_training_on_model/) |
| 4.   | [Evaluating perfromance on dataset](introductory/basic/4._Evaluating_performance_on_dataset/) |

### MetaCAT (meta-annotation) tutorials

| Part | Title                                                                       |
| ---- |-----------------------------------------------------------------------------|
| 1.   |  [Add a MetaCAT to a Model](introductory/meta/1._Add_a_MetaCat_to_a_Model/)                                    |

## Advanced tutorials

| Part | Title                                                                       |
| ---- |-----------------------------------------------------------------------------|
| 1.   |  [Creating and using a custom tokenizer](advanced/1._Creating_and_using_a_custom_tokenizer/)                               |
| 2.   |  [Create and use component](advanced/2._Create_and_use_component/)                                    |
