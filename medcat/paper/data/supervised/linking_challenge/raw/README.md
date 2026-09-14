First, we need to download the 2023 Snomed linking challenge dataset:
https://www.drivendata.org/competitions/258/competition-snomed-ct/

Then, ocnvert to MedCAT supported format:
```python
python convert_to_mct_export.py mimic-iv_notes_training_set.csv train_annotations.csv ../mct_export.json
```