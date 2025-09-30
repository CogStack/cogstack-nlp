from typing import Optional
from medcat.cat import CAT
import json
import os

import logging
medcat_logger = logging.getLogger('medcat')
fh = logging.FileHandler('medcat.log')
medcat_logger.addHandler(fh)


def run_model(model_hash_or_path: str, data: list[str],
              save_dir_path: str,
              snomed_filter_path: Optional[str] = None,
              n_process: int = 1,
              ):
    cat = CAT.load_model_pack(model_hash_or_path)
    if snomed_filter_path:
        with open(snomed_filter_path) as f:
            snomed_filter = json.load(f)
    else:
        snomed_filter = set()  # no filter
    cat.config.components.linking.filters.cuis = snomed_filter

    if not os.path.exists(save_dir_path):
        os.makedirs(save_dir_path)
    list(cat.get_entities_multi_texts(
        data, n_process=n_process,
        save_dir_path=save_dir_path))
