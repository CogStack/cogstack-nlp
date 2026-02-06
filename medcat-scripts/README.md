# medcat-scripts

This project contains the relevant tools and notebooks to help users work with MedCAT models.
This includes instructions on finetuning models in an unsupervised or supervised manner as well as evaluating MedCATtrainer exports and run models on data.

Some tutorials in [medcat-v2-tutorials](../medcat-v2-tutorials/) may also be of help.

# Setup

To gain access to these scripts you simply:
```
git clone https://github.com/CogStack/cogstack-nlp.git
cd cogstack-nlp/medcat-scripts
```
OR (in `medcat>=2.3.0`) you can have `medcat` download the appropriate scripts for you by running:
```
# NOTE: by default this gets installed to your local directory, but a path can be provided
python -m medcat download-scripts
```
You may subsequently need to install the relevant requirements
```
python -m pip install -r requirements.txt
```