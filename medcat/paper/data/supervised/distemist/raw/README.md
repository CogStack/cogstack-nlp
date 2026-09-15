First we need to download and extract the distemist dataset:
https://temu.bsc.es/distemist/distemist-linking/

Subsequently, we convert to MedCAT supported format:
```python
python convert_to_mct_export.py distemist_zenodo/multilingual_resources/training_text_files/en distemist_zenodo/multilingual_resources/en ../mct_export.json
```

NOTE:
The underlying dataset (at least in some cases) links to multiple concepts per annotation.
And because of that the output also allows a subset of concepts.
