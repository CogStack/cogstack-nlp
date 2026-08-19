from typing import Protocol

import numpy as np
from medcat.cdb import CDB


class TrainingFetcher(Protocol):

    def get_cui_train_count(self, cui: str) -> int:
        pass

    def get_name_train_count(self, name: str) -> int:
        pass

    def get_cui_context_vector(self, cui: str) -> dict[str, np.ndarray]:
        pass

    def get_cui2count_train(self) -> dict[str, int]:
        pass

    def get_name2count_train(self) -> dict[str, int]:
        pass

    def get_cui2context_vector(self) -> dict[str, dict[str, np.ndarray]]:
        pass


class CDBTrainingFetcher:

    def __init__(self, cdb: CDB) -> None:
        self.cdb = cdb

    def get_cui_train_count(self, cui: str) -> int:
        if cui not in self.cdb.cui2info:
            return 0
        return self.cdb.cui2info[cui]['train_count']

    def get_name_train_count(self, name: str) -> int:
        if name not in self.cdb.name2info:
            return 0
        return self.cdb.name2info[name]['train_count']

    def get_cui_context_vector(self, cui: str) -> dict[str, np.ndarray]:
        if cui not in self.cdb.cui2info:
            return {}
        return self.cdb.cui2info[cui]['context_vector']

    def get_cui2count_train(self) -> dict[str, int]:
        return self.cdb.get_cui2count_train()

    def get_name2count_train(self) -> dict[str, int]:
        return self.cdb.get_name2count_train()

    def get_cui2context_vector(self) -> dict[str, dict[str, np.ndarray]]:
        return self.cdb.get_cui2context_vectors()
