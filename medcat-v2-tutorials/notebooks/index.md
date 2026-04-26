# MedCAT Tutorials

The MedCAT Tutorials provide an interactive learning path for using MedCAT.

These tutorials are aimed at developers and / or people creating their own models.
For every day usage (e.g inference) the [medcat-scripts](https://github.com/CogStack/cogstack-nlp/tree/main/medcat-scripts) portion would probably be more useful.

## Learning Path

Get started by going to the [basic tutorials](introductory/basic/). Here you will learn about Concept Databases, Vocabularies, and perform supervised and unsupervised training.

After that you can continue to see the other features of medcat, such as configuring MetaCAT and RelCAT.

Finally you can look at advanced tutorials where you will dig into the internals of MedCAT.

## Interactive Usage

!!! tip

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
