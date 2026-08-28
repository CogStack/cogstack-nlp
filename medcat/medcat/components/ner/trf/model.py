from typing import Any, Union, Optional

from medcat.components.ner.trf.transformers_ner import TransformersNER
from medcat.components.types import CoreComponentType
from medcat.tokenizing.tokens import MutableDocument
from medcat.cat import CAT
from medcat.cdb import CDB
from medcat.config import Config
from medcat.data.entities import Entities, OnlyCUIEntities


class NerModel:

    """The NER model.

    This wraps a CAT instance and simplifies its use as a
    NER model.

    It provides methods for creating one from a TransformersNER
    as well as loading from a model pack (along with some validation).

    It also exposes some useful parts of the CAT it wraps such as
    the config and the concept database.
    """

    def __init__(self, cat: CAT) -> None:
        self.cat = cat

    def train(self, json_path: Union[str, list, None],
              *args, **kwargs) -> tuple[Any, Any, Any]:
        """Train the underlying transformers NER model.

        All the extra arguments are passed to the TransformersNER train method.

        Args:
            json_path (Union[str, list, None]): The JSON file path to read the
                training data from.
            *args: Additional arguments for TransformersNER.train .
            **kwargs: Additional keyword arguments for TransformersNER.train .

        Returns:
            Tuple[Any, Any, Any]: df, examples, dataset
        """
        return self.trf_ner._component.train(json_path, *args, **kwargs)

    def eval(self, json_path: Union[str, list, None],
             *args, **kwargs) -> tuple[Any, Any, Any]:
        """Evaluate the underlying transformers NER model.
        All the extra arguments are passed to the TransformersNER eval method.
        Args:
            json_path (Union[str, list, None]):
                The JSON file path to read the training data from.
            *args: Additional arguments for TransformersNER.eval .
            **kwargs: Additional keyword arguments for TransformersNER.eval .
        Returns:
            Tuple[Any, Any, Any]: df, examples, dataset
        """
        return self.trf_ner._component.eval(json_path, *args, **kwargs)

    def __call__(self, text: Optional[str], *args, **kwargs
                 ) -> Optional[MutableDocument]:
        """Get the annotated document for text.

        Undefined arguments and keyword arguments get passed on to
        the equivalent `CAT` method.

        Args:
            text (Optional[str]): The input text.
            *args: Additional arguments for cat.__call__ .
            **kwargs: Additional keyword arguments for cat.__call__ .

        Returns:
            Optional[Doc]: The annotated document.
        """
        return self.cat(str(text), *args, **kwargs)

    def get_entities(self, text: str, *args, **kwargs
                     ) -> Union[dict, Entities, OnlyCUIEntities]:
        """Gets the entities recognized within a given text.

        The output format is identical to `CAT.get_entities`.

        Undefined arguments and keyword arguments get passed on to
        CAT.get_entities.

        Args:
            text (str): The input text.
            *args: Additional arguments for cat.get_entities .
            **kwargs: Additional keyword arguments for cat.get_entities .

        Returns:
            dict: The output entities.
        """
        return self.cat.get_entities(text, *args, **kwargs)

    def add_new_concepts(self,
                         cui2preferred_name: dict[str, str],
                         with_random_init: bool = False) -> None:
        """Add new concepts to the model and the concept database.

        Invoking this requires subsequent retraining on the model.

        Args:
            cui2preferred_name(dict[str, str]): Dictionary where each key is
                the literal ID of the concept to be added and each value is
                    its preferred name.
            with_random_init (bool): Whether to use the random init strategy
                for the new concepts. Defaults to False.
        """
        self.trf_ner._component.expand_model_with_concepts(
            cui2preferred_name, use_avg_init=not with_random_init)

    @property
    def trf_ner(self) -> TransformersNER:
        ner_comp = self.cat._pipeline.get_component(CoreComponentType.ner)
        if not isinstance(ner_comp, TransformersNER):
            raise ValueError(f"Incorrect NER component: {ner_comp.full_name}")
        return ner_comp

    @property
    def config(self) -> Config:
        return self.cat.config

    @property
    def cdb(self) -> CDB:
        return self.cat.cdb

    # @classmethod
    # def create(cls, ner: Union[TransformersNER, List[TransformersNER]]
    #            ) -> 'NerModel':
    #     """Create a NER model with a TransformersNER

    #     Args:
    #         ner (Union[TransformersNER, List[TransformersNER]]):
    #             The TransformersNER instance(s).

    #     Returns:
    #         NerModel: The resulting model
    #     """
    #     # expecting all to have the same CDB
    #     cdb = ner.cdb if isinstance(ner, TransformersNER) else ner[0].cdb
    #     cat = CAT(cdb=cdb, addl_ner=ner)
    #     return cls(cat)

    @classmethod
    def load_model_pack(cls, model_pack_path: str,
                        config: Optional[dict] = None) -> 'NerModel':
        """Load NER model from model pack.

        The method first wraps the loaded CAT instance.

        Args:
            config: Config for DeId model pack (primarily for stride of
                overlap window)
            model_pack_path (str): The model pack path.

        Returns:
            NerModel: The resulting DeI model.
        """
        cat = CAT.load_model_pack(model_pack_path)  # , ner_config_dict=config)
        return cls(cat)
