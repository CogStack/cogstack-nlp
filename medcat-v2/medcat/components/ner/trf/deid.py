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
from typing import Union, Any, Optional, Iterable
import re
import logging
import warnings

from medcat.cat import CAT
from medcat.cdb.cdb import CDB
from medcat.config.config_transformers_ner import ConfigTransformersNER
from medcat.components.types import CoreComponentType
from medcat.components.ner.trf.model import NerModel
from medcat.components.ner.trf.helpers import replace_entities_in_text
from medcat.components.ner.trf.transformers_ner import TransformersNER
from medcat.data.entities import Entity


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

    def deid_multi_text(self, texts: Iterable[str], redact: bool = False,
                        n_process: Optional[int] = None) -> list[str]:
        warnings.warn(
            "deid_multi_text() is deprecated and will be removed in a "
            "future release. Use deid_multi_texts() instead.",
            DeprecationWarning,
            stacklevel=2
        )
        return self.deid_multi_texts(texts, redact, n_process)

    def deid_multi_texts(self, texts: Iterable[str], redact: bool = False,
                         n_process: Optional[int] = None) -> list[str]:
        if n_process is None:
            n_process = 1

        entities = self.cat.get_entities_multi_texts(
            texts, n_process=n_process)
        out: list[str] = []
        for raw_text, (_, _ents) in zip(texts, entities):
            ents = _ents['entities']
            text: str
            if isinstance(raw_text, tuple):
                text = raw_text[1]
            elif isinstance(raw_text, str):
                text = raw_text
            else:
                raise ValueError("Unknown raw text: "
                                 f"{type(raw_text)}: {raw_text}")
            new_text = replace_entities_in_text(
                text, ents, get_cui_name=self.cat.cdb.get_name, redact=redact)
            out.append(new_text)
        return out

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


def match_rules(rules: list[tuple[str, str]], texts: list[str],
                cui2preferred_name: dict[str, str]) -> list[list[Entity]]:
    """Match a set of rules - pat / cui combos as post processing labels.
    Uses a cat DeID model for pretty name mapping.
    Args:
        rules (list[tuple[str, str]]): List of tuples of pattern and cui
        texts (list[str]): List of texts to match rules on
        cui2preferred_name (dict[str, str]): Dictionary of CUI to
            preferred name, likely to be cat.cdb.cui2preferred_name.
    Examples:
        >>> cat = CAT.load_model_pack(model_pack_path)
        ...
        >>> rules = [
            ('(123) 456-7890', '134'),
            ('1234567890', '134'),
            ('123.456.7890', '134'),
            ('1234567890', '134'),
            ('1234567890', '134'),
        ]
        >>> texts = [
            'My phone number is (123) 456-7890',
            'My phone number is 1234567890',
            'My phone number is 123.456.7890',
            'My phone number is 1234567890',
        ]
        >>> matches = match_rules(rules, texts, cat.cdb.cui2preferred_name)
    Returns:
        List[List[Dict]]: List of lists of predictions from `match_rules`
    """
    # Iterate through each text and pattern combination
    rule_matches_per_text: list[list[Entity]] = []
    for i, text in enumerate(texts):
        matches_in_text: list[Entity] = []
        for pattern, concept in rules:
            # Find all matches of current pattern in current text
            text_matches = re.finditer(pattern, text, flags=re.M)
            # Add each match with its pattern and text info
            for match in text_matches:
                matches_in_text.append({
                    'source_value': match.group(),
                    'pretty_name': cui2preferred_name[concept],
                    'start': match.start(),
                    'end': match.end(),
                    'cui': concept,
                    'acc': 1.0
                })
        rule_matches_per_text.append(matches_in_text)
    return rule_matches_per_text


def merge_all_preds(model_preds_by_text: list[list[Entity]],
                    rule_matches_per_text: list[list[Entity]],
                    accept_preds: bool = True) -> list[list[Entity]]:
    """Conveniance method to merge predictions from rule based and deID model
    predictions.

    Args:
        model_preds_by_text (list[list[Entity]]):
            List of predictions from `cat.get_entities()`, then
            `[list(m['entities'].values()) for m in model_preds]`
        rule_matches_per_text (list[list[Entity]]):
            List of predictions from output of running `match_rules`
        accept_preds (bool):
            Uses the predicted label from the model,
            model_preds_by_text, over the rule matches if they overlap.
            Defaults to using model preds over rules.
    Returns:
        list[list[Entity]]: List of lists of predictions from `merge_all_preds`
    """
    assert len(model_preds_by_text) == len(rule_matches_per_text), (
        "model_preds_by_text and rule_matches_per_text must have the same "
        "length as they should be CAT.get_entities and match_rules outputs of "
        "the same text")
    return [
        merge_preds(model_preds_by_text[i],
                    rule_matches_per_text[i],
                    accept_preds)
        for i in range(len(model_preds_by_text))]


def merge_preds(model_preds: list[Entity],
                rule_matches: list[Entity],
                accept_preds: bool = True) -> list[Entity]:
    """Merge predictions from rule based and deID model predictions.
    Args:
        model_preds (list[Entity]): predictions from `cat.get_entities()`
        rule_matches (list[Entity]): predictions from output of running
            `match_rules` on the same text
        accept_preds (bool): uses the predicted label from the model,
            model_preds, over the rule matches if they overlap.
            Defaults to using model preds over rules.
    Examples:
        >>> # a list of predictions from `cat.get_entities()`
        >>> model_preds = [
            [
                {'cui': '134', 'start': 10, 'end': 20, 'acc': 1.0,
                 'pretty_name': 'Phone Number'},
                {'cui': '134', 'start': 25, 'end': 35, 'acc': 1.0,
                 'pretty_name': 'Phone Number'}
            ]
        ]
        >>> # a list of predictions from `match_rules`
        >>> rule_matches = [
            [
                {'cui': '134', 'start': 10, 'end': 20, 'acc': 1.0,
                 'pretty_name': 'Phone Number'},
                {'cui': '134', 'start': 25, 'end': 35, 'acc': 1.0,
                 'pretty_name': 'Phone Number'}
            ]
        ]
        >>> merged_preds = merge_preds(model_preds, rule_matches)
    Returns:
        list[Entity]: List of predictions from `merge_preds`
    """
    if accept_preds:
        labels1 = model_preds
        labels2 = rule_matches
    else:
        labels1 = rule_matches
        labels2 = model_preds

    # Keep only non-overlapping model predictions
    labels2 = [span2 for span2 in labels2
               if not any(not (span2['end'] <= span1['start'] or
                               span1['end'] <= span2['start'])
                          for span1 in labels1)]
    # merge preds and sort on start
    merged_preds = labels1 + labels2
    merged_preds.sort(key=lambda x: x['start'])
    merged_preds
    return merged_preds
