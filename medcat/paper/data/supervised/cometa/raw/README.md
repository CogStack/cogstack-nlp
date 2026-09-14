First, we need to download the dataset:
https://metatext.io/datasets/cometa

Then we need to convert to a format MedCAT understands:
```python
python conversion/converter.py chv.csv ../mct_export.json
```