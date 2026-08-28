First we download the MDACE dataset and prepare it with MIMIC-IV as per instructions:
https://github.com/3mcloud/MDACE

Then, we need to convert the data to a format MedCAT can understand using:
```python
python convert_to_mct_export.py  # no need for arguments if in this folder
```

However, that still only has ICD-10 codes.
Yet the models we're comparing to use SNOMED.

So we then need to convert to SNOMED by doing:
```python
python map_from_icd_to_snomed.py <model_pack_path> ../icd10_convert.json ../mct_export_with_candidates.json
```

This will create a trainer export that has multiple CUIs as options for each annotation.
That is because ICD-10 codes can map to multiple different Snomed concepts and there is no automated way to create a 1 to 1 mapping.
