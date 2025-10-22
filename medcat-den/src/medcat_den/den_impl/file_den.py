from typing import Optional, cast, Any, Union

import json
from datetime import datetime
import os
import sqlite3
import shutil

from medcat.cat import CAT
from medcat.data.mctexport import MedCATTrainerExport

from medcat_den.den import (
    Den, DuplicateModelException, UnsupportedAPIException)
from medcat_den.backend import DenType
from medcat_den.base import ModelInfo
from medcat_den.wrappers import CATWrapper
from medcat_den.config import LocalDenConfig


class SqliteModel:
    registry_name = 'registry.db'

    def __init__(self, parent_folder: str):
        self.db_path = os.path.join(parent_folder, self.registry_name)
        self._conn = sqlite3.connect(self.db_path)
        self._init_tables()

    def _init_tables(self):
        cur = self._conn.cursor()
        cur.execute("""CREATE TABLE IF NOT EXISTS
                        models(
                        id TEXT PRIMARY KEY,
                        root_id TEXT REFERENCES models(id),
                        model_card JSON NOT NULL,
                        created_at TIMESTAMP
                        )
                    """)
        self._conn.commit()

    def insert_model(self, model_info: ModelInfo) -> None:
        """Insert a new model entry."""
        cur = self._conn.cursor()
        cur.execute(
            """
            INSERT INTO models (id, root_id, model_card, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                model_info.model_id,
                model_info.base_model.model_id if
                model_info.base_model else None,
                json.dumps(model_info.model_card),
                datetime.now().isoformat(),
            ),
        )
        self._conn.commit()

    def get_model(self, model_id: str) -> Optional[ModelInfo]:
        """Fetch a model by ID."""
        cur = self._conn.cursor()
        cur.execute("""SELECT id, root_id, model_card, created_at
                        FROM models WHERE id=?""", (model_id,))
        row = cur.fetchone()
        if not row:
            return None

        return ModelInfo(
            model_id=row[0],
            model_card=json.loads(row[2]),
            base_model=ModelInfo(model_id=row[1], model_card=None,
                                 base_model=None) if row[1] else None,
        )

    def list_models(self) -> list[ModelInfo]:
        """List all models in registry."""
        cur = self._conn.cursor()
        cur.execute("SELECT id, root_id, model_card, created_at FROM models")
        rows = cur.fetchall()
        return [
            ModelInfo(
                model_id=row[0],
                model_card=json.loads(row[2]),
                base_model=ModelInfo(model_id=row[1], model_card=None,
                                     base_model=None) if row[1] else None,
            )
            for row in rows
        ]

    def list_derivatives(self, root_id: str) -> list[ModelInfo]:
        """List all models derived from a given base model."""
        cur = self._conn.cursor()
        cur.execute("""SELECT id, model_card, created_at
                        FROM models WHERE root_id=?""", (root_id,))
        rows = cur.fetchall()
        return [
            ModelInfo(
                model_id=row[0],
                base_model=ModelInfo(model_id=root_id, model_card=None,
                                     base_model=None),
                model_card=json.loads(row[1]),
            )
            for row in rows
        ]

    def delete_model(self, model_id: str) -> None:
        """Delete a model from the database.

        Args:
            model_id (str): The model ID.
        """
        cur = self._conn.cursor()
        cur.execute("""
                    DELETE FROM models WHERE id=?
                    """, (model_id,))
        self._conn.commit()


class LocalFileDen(Den):
    folder_name = '.medcat-den'
    models_folder_name = 'models'

    def __init__(self, cnf: LocalDenConfig):
        self._cnf = cnf
        if not os.path.exists(cnf.location):
            os.makedirs(cnf.location, exist_ok=True)
        self._folder_path = os.path.join(cnf.location, self.folder_name)
        if not os.path.exists(self._folder_path):
            os.mkdir(self._folder_path)
        self._sqlite = SqliteModel(self._folder_path)
        self._models_folder = os.path.join(self._folder_path,
                                           self.models_folder_name)
        if not os.path.exists(self._models_folder):
            os.mkdir(self._models_folder)
        self._den_type = DenType.LOCAL_USER

    @property
    def den_type(self) -> DenType:
        return self._den_type

    def list_available_models(self) -> list[ModelInfo]:
        return self._sqlite.list_models()

    def list_available_base_models(self) -> list[ModelInfo]:
        return [model for model in self.list_available_models()
                # base models don't have a base model defined
                if model.base_model is None]

    def list_available_derivative_models(self, model: ModelInfo
                                         ) -> list[ModelInfo]:
        return self._sqlite.list_derivatives(model.model_id)

    def _get_model_zip_name(self, model_hash: str) -> str:
        return f"{model_hash}.zip"

    def _get_model_zip_path(self, model_info: ModelInfo) -> str:
        return os.path.join(self._models_folder,
                            self._get_model_zip_name(model_info.model_id))

    def fetch_model(self, model_info: ModelInfo) -> CATWrapper:
        db_info = self._sqlite.get_model(model_id=model_info.model_id)
        if db_info is None:
            raise ValueError(f"The model info {model_info} does not "
                             "correspond to a model that exists the back end")
        model_path = self._get_model_zip_path(model_info)
        return cast(
            CATWrapper,
            CATWrapper.load_model_pack(model_path, model_info=model_info,
                                       den_cnf=self._cnf))

    def push_model(self, cat: CAT, description: str) -> None:
        if isinstance(cat, CATWrapper):
            model_info = cat._model_info
        else:
            model_info = ModelInfo.from_model_pack(cat)
        # calc new hash
        new_hash = cat._get_hash()
        if (new_hash == model_info.model_id and
                self._sqlite.get_model(new_hash)):
            # NOTE: if there's no model in databae, treat as new one
            raise DuplicateModelException(
                "Duplicate model: ", model_info)
        zip_name = self._get_model_zip_name(new_hash)
        kwargs: dict[Any, Any] = {}
        if isinstance(cat, CATWrapper):
            kwargs["force_save_local"] = True
        full_model_pack_path = cat.save_model_pack(
            self._models_folder,
            pack_name=zip_name.removesuffix(".zip"),
            add_hash_to_pack_name=False,
            change_description=description,
            **kwargs)
        # NOTE: the updated one should have the updated history and the like
        updated_mi = ModelInfo.from_model_pack(cat)
        if isinstance(cat, CATWrapper):
            cat._model_info = updated_mi
        self._sqlite.insert_model(updated_mi)
        if not full_model_pack_path.endswith(".zip"):
            # NOTE: it should not actually end with .zip coming
            #       out of the above unless only archive is requested
            full_model_pack_path += ".zip"
        # NOTE: only calling the below so that any overrides can use it
        #       if needed - e.g for local cache (i.e in testing -
        #       otherwise it doesn't make sense to use local cache)
        self._push_model_from_file(full_model_pack_path, description)

    def _push_model_from_file(self, file_path: str, description: str) -> None:
        # NOTE: for local file den this is not needed, but will still be called
        pass

    def delete_model(self, model_info: ModelInfo,
                     allow_delete_base_models: bool = False):
        if not model_info.model_card:
            raise ValueError(
                "Need to specify a model info with a model card for deletion")
        if (len(model_info.model_card[
                "History (from least to most recent)"]) <= 1
                and not allow_delete_base_models):
            raise ValueError("Unable to delete base model. Pass "
                             "allow_delete_base_models=True to force.")
        self._sqlite.delete_model(model_info.model_id)
        zip_path = self._get_model_zip_path(model_info)
        os.remove(zip_path)
        folder_path = zip_path.removesuffix(".zip")
        if os.path.exists(folder_path):
            shutil.rmtree(folder_path)

    def finetune_model(self, model_info: ModelInfo,
                       data: Union[list[str], MedCATTrainerExport]):
        raise UnsupportedAPIException(
            "Local den does not support finetuning on the den. "
            "Use a remote den instead or perform training locally."
        )

    def evaluate_model(self, model_info: ModelInfo,
                       data: Union[list[str], MedCATTrainerExport]) -> dict:
        raise UnsupportedAPIException(
            "Local den does not support evaluation on the den. "
            "Use a remote den instead or perform evaluation locally."
        )
