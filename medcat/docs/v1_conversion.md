# Converting a v1 model to v2 format

While we encourage you use MedCAT v2 and the models in that native format, if you download an older version MedCAT v2 will be able to load it and covnert it to the format it knows. However, the loading process will be considerably longer in those cases.

If you wish you can also convert the v1 models into the v2 format (see [tutorial](../../medcat-tutorials/notebooks/introductory/migration/1._Migrate_v1_model_to_v2.ipynb)).

```python
from medcat.utils.legacy import legacy_converter
from medcat.storage.serialisers import AvailableSerialisers
old_model = '<path to old v1 model>'
new_model_dir = '<dir to place new model in>'
legacy_converter.do_conversion(old_model_path, new_model_dir, AvailableSerialisers.dill)
```
OR
```bash
model_path = "models/medcat1_model_pack.zip"
new_model_folder = "models"  # file in this folder
! python -m  medcat.utils.legacy.legacy_converter $model_path $new_model_folder --verbose
```

