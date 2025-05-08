"""De-identification model.

This describes a wrapper on the regular CAT model.
The idea is to simplify the use of a DeId-specific model.

It tackles two use cases
1) Creation of a deid model
2) Loading and use of a deid model

I.e for use case 1:

Instead of:
cat = CAT(cdb=ner.cdb, addl_ner=ner)

You can use:
deid = DeIdModel.create(ner)


And for use case 2:

Instead of:
cat = CAT.load_model_pack(model_pack_path)
anon_text = deid_text(cat, text)

You can use:
deid = DeIdModel.load_model_pack(model_pack_path)
anon_text = deid.deid_text(text)

Or if/when structured output is desired:
deid = DeIdModel.load_model_pack(model_pack_path)
anon_doc = deid(text)  # the spacy document

The wrapper also exposes some CAT parts directly:
- config
- cdb
"""
from typing import Union, Any, Optional
import logging

from medcat2.cat import CAT
from medcat2.cdb.cdb import CDB
from medcat2.config.config_transformers_ner import ConfigTransformersNER
from medcat2.components.types import CoreComponentType
from medcat2.components.ner.trf.model import NerModel
from medcat2.components.ner.trf.helpers import replace_entities_in_text
from medcat2.components.ner.trf.transformers_ner import TransformersNER


logger = logging.getLogger(__name__)


class DeIdModel(NerModel):
    """The DeID model.

    This wraps a CAT instance and simplifies its use as a
    de-identification model.

    It provides methods for creating one from a TransformersNER
    as well as loading from a model pack (along with some validation).

    It also exposes some useful parts of the CAT it wraps such as
    the config and the concept database.
    """

    def __init__(self, cat: CAT) -> None:
        self.cat = cat

    def train(self, json_path: Union[str, list, None],
              *args, **kwargs) -> tuple[Any, Any, Any]:
        return super().train(json_path,
                             *args, **kwargs)  # type: ignore

    def deid_text(self, text: str, redact: bool = False) -> str:
        """Deidentify text and potentially redact information.

        De-identified text.
        If redaction is enabled, identifiable entities will be
        replaced with starts (e.g `*****`).
        Otherwise, the replacement will be the CUI or in other words,
        the type of information that was hidden (e.g [PATIENT]).

        Args:
            text (str): The text to deidentify.
            redact (bool): Whether to redact the information.

        Returns:
            str: The deidentified text.
        """
        entities = self.cat.get_entities(text)['entities']
        return replace_entities_in_text(text, entities, self.cat.cdb.get_name,
                                        redact=redact)

    @classmethod
    def load_model_pack(cls, model_pack_path: str,
                        config: Optional[dict] = None) -> 'DeIdModel':
        """Load DeId model from model pack.

        The method first loads the CAT instance.

        It then makes sure that the model pack corresponds to a
        valid DeId model.

        Args:
            config: Config for DeId model pack (primarily for stride of
                overlap window)
            model_pack_path (str): The model pack path.

        Raises:
            ValueError: If the model pack does not correspond to a DeId model.

        Returns:
            DeIdModel: The resulting DeI model.
        """
        ner_model = NerModel.load_model_pack(model_pack_path, config=config)
        cat = ner_model.cat
        if not cls._is_deid_model(cat):
            raise ValueError(
                f"The model saved at {model_pack_path} is not a deid model "
                f"({cls._get_reason_not_deid(cat)})")
        model = cls(ner_model.cat)
        return model

    @classmethod
    def _is_deid_model(cls, cat: CAT) -> bool:
        return not bool(cls._get_reason_not_deid(cat))

    @classmethod
    def _get_reason_not_deid(cls, cat: CAT) -> str:
        if cat.vocab is not None:
            return "Has vocab"
        ner_comp = cat._pipeline.get_component(CoreComponentType.ner)
        if not isinstance(ner_comp, TransformersNER):
            raise ValueError(f"Incorrect NER component: {ner_comp.full_name}")
        return ""

    @classmethod
    def create(cls, cdb: CDB, cnf: ConfigTransformersNER):
        cdb.config.components.ner.comp_name = TransformersNER.name
        cdb.config.components.ner.custom_cnf = cnf
        # no-action linker
        cdb.config.components.linking.comp_name = 'no_action'
        cat = CAT(cdb=cdb, vocab=None, config=cdb.config)
        return cls(cat)
