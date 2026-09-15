import re
from dataclasses import dataclass
from typing import Protocol

from medcat.tokenizing.tokens import MutableDocument
from medcat.tokenizing.tokenizers import BaseTokenizer


@dataclass
class NameDescriptor:
    tokens: list[str]
    snames: set[str]
    raw_name: str
    is_upper: bool


class LGeneral(Protocol):
    separator: str


class LPreprocessing(Protocol):
    min_len_normalize: int
    do_not_normalize: set[str]


class LCDBMaker(Protocol):
    name_versions: list[str]
    min_letters_required: int


def _get_tokens(config: LPreprocessing,
                sc_name: MutableDocument,
                version: str) -> list[str]:
    if version == "LOWER":
        return [tkn.base.lower for tkn in sc_name if not tkn.to_skip]
    if version == "CLEAN":
        min_norm_len = config.min_len_normalize
        tokens = []
        for tkn in sc_name:
            if not tkn.to_skip:
                if len(tkn.base.lower) < min_norm_len:
                    tokens.append(tkn.base.lower)
                elif (config.do_not_normalize and
                        tkn.tag is not None and
                        tkn.tag in config.do_not_normalize):
                    tokens.append(tkn.base.lower)
                else:
                    tokens.append(tkn.lemma.lower())
        return tokens
    raise UnknownTokenVersion(version)


def _update_dict(configs: tuple[LGeneral, LPreprocessing, LCDBMaker],
                 raw_name: str,
                 names: dict[str, NameDescriptor],
                 tokens: list[str], is_upper: bool) -> None:
    general, _, cdb_maker = configs
    snames = set()
    name = general.separator.join(tokens)
    mlr = cdb_maker.min_letters_required
    if (mlr and len(re.sub("[^A-Za-z]*", '', name)) < mlr):
        return  # too short
    if name in names:
        return  # already exists
    sname = ""
    for token in tokens:
        if sname:
            sname = sname + general.separator + token
        else:
            sname = token
        snames.add(sname.strip())

    names[name] = NameDescriptor(tokens=tokens, snames=snames,
                                 raw_name=raw_name, is_upper=is_upper)


def prepare_name(raw_name: str, nlp: BaseTokenizer,
                 names: dict[str, NameDescriptor],
                 configs: tuple[LGeneral, LPreprocessing, LCDBMaker],
                 ) -> dict[str, NameDescriptor]:
    """Generates different forms of a name. Will edit the provided `names`
    dictionary and add information generated from the `name`.

    Args:
        nlp (BaseTokenizer): The tokenizer.
        names (dict[str, NameDescriptor]):
            Dictionary of existing names for this concept in this row of a CSV.
            The new generated name versions and other required information will
            be added here.
        configs (tuple[LGeneral, LPreprocessing, LCDBMaker]):
            Applicable configs for medcat.

    Returns:
        names (dict):
            The updated dictionary of prepared names.
    """
    sc_name = nlp(raw_name)
    _, preprocessing, cdb_maker = configs

    for version in cdb_maker.name_versions:
        tokens = None

        tokens = _get_tokens(preprocessing, sc_name, version)

        if tokens is not None and tokens:
            _update_dict(configs, raw_name, names, tokens,
                         sc_name.base.isupper())

    return names


class UnknownTokenVersion(ValueError):

    def __init__(self, version: str) -> None:
        super().__init__(f"Unknown token version: '{version}'")
