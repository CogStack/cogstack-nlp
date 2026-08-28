from typing import Union
import os
import logging

import pickle

from medcat.data.entities import Entities, OnlyCUIEntities


logger = logging.getLogger(__name__)


class BatchAnnotationSaver:
    def __init__(self, save_dir: str, batches_per_save: int):
        self.save_dir = save_dir
        self.batches_per_save = batches_per_save
        self._batch_cache: list[list[
            tuple[str, Union[dict, Entities, OnlyCUIEntities]]]] = []
        os.makedirs(save_dir, exist_ok=True)
        self.part_number = 0
        self.annotated_ids_path = os.path.join(
            save_dir, "annotated_ids.pickle")

    def _load_existing_ids(self) -> tuple[list[str], int]:
        if not os.path.exists(self.annotated_ids_path):
            return [], -1
        with open(self.annotated_ids_path, 'rb') as f:
            return pickle.load(f)

    def _save_cache(self):
        annotated_ids, prev_part_num = self._load_existing_ids()
        if (prev_part_num + 1) != self.part_number:
            logger.info(
                "Found part number %d off disk. Previously %d was kept track "
                "of in code. Updating to %d off disk.",
                prev_part_num, self.part_number, prev_part_num)
            self.part_number = prev_part_num
        for batch in self._batch_cache:
            for doc_id, _ in batch:
                annotated_ids.append(doc_id)
        logger.debug("Saving part %d with %d batches",
                     self.part_number, len(self._batch_cache))
        with open(self.annotated_ids_path, 'wb') as f:
            pickle.dump((annotated_ids, self.part_number), f)
        # Save batch as part_<num>.pickle
        part_path = os.path.join(self.save_dir,
                                 f"part_{self.part_number}.pickle")
        part_dict = {id: val for
                     batch in self._batch_cache for
                     id, val in batch}
        with open(part_path, 'wb') as f:
            pickle.dump(part_dict, f)
        self._batch_cache.clear()
        self.part_number += 1

    def __call__(self, batch: list[
            tuple[str, Union[dict, Entities, OnlyCUIEntities]]]):
        self._batch_cache.append(batch)
        if len(self._batch_cache) >= self.batches_per_save:
            self._save_cache()
