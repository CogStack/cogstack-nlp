First we need to download the MedMentions dataset:
https://github.com/chanzuckerberg/MedMentions

Then, we need to convert it to a format MedCAT understands:
```python
python src/medmentions_converter.py corpus_pubtator.txt medmentions_umls.json
```

However, this still has UMLS codes instead of Snomed ones.
For that we also need UMLS (`MRCONSO.RRF`) to do the mappingp.

To do the conversion into Snomed we do:
```python
python src/medmen_umls2snomed_converter.py medmentions_umls.json <path to MedCAT CDB> <folder path with MRCONSO.RRF> ../medmentions_snomed_stricter.json
```