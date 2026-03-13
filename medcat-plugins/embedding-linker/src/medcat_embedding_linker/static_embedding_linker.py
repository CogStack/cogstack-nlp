from medcat.cdb import CDB
from medcat.config.config import Config, ComponentConfig
from medcat.components.types import CoreComponentType
from medcat.components.types import AbstractEntityProvidingComponent
from medcat.tokenizing.tokens import MutableEntity, MutableDocument
from medcat.tokenizing.tokenizers import BaseTokenizer
from medcat_embedding_linker.embedding_linker import Linker
from typing import Optional, Iterator, Set
from medcat.vocab import Vocab
from medcat.utils.postprocessing import filter_linked_annotations
from tqdm import tqdm
from collections import defaultdict
import logging
import math
import numpy as np

from medcat_embedding_linker.config import EmbeddingLinking

from torch import Tensor
from transformers import AutoTokenizer, AutoModel
import torch.nn.functional as F
import torch

logger = logging.getLogger(__name__)


class StaticEmbeddingLinker(Linker):
    name = "embedding_linker"

    def __init__(self, cdb: CDB, config: Config) -> None:
        """Initializes the embedding linker with a CDB and configuration.
        Args:
            cdb (CDB): The concept database to use.
            config (Config): The base config.
        """
        super().__init__(cdb, config)
        if self.cnf_l.use_projection_layer:
            logger.warning("Projection layer is not supported in the `static_embedding_linker`. " \
            "Project is only available in the `trainable_embedding_linker`. " \
            "Setting use_projection_layer to False.")
            self.cnf_l.use_projection_layer = False


    @classmethod
    def create_new_component(
        cls,
        cnf: ComponentConfig,
        tokenizer: BaseTokenizer,
        cdb: CDB,
        vocab: Vocab,
        model_load_path: Optional[str],
    ) -> "StaticEmbeddingLinker":
        return cls(cdb, cdb.config)
