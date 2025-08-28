import pandas as pd
import numpy as np
import datetime
import logging
import re
from typing import Optional, Union, Any

from medcat.pipeline import Pipeline
from medcat.cdb import CDB
from medcat.config import Config
from medcat.preprocessors.cleaners import prepare_name

PH_REMOVE = re.compile(r"(\s)\([a-zA-Z]+[^\)\(]*\)($)")


logger = logging.getLogger(__name__)


class CDBMaker(object):
    """Given a CSV it creates a CDB or updates an existing one.

    The CSV is expected to have

    Args:
        config (medcat.config.Config):
            Global config for MedCAT.
        cdb (medcat.cdb.CDB):
            If set the `CDBMaker` will update the existing `CDB` with
            new concepts in the CSV (Default value `None`).
    """

    def __init__(self, config: Config, cdb: Optional[CDB] = None) -> None:
        self.config = config
        # Set log level
        logger.setLevel(self.config.general.log_level)

        # To make life a bit easier
        self.cnf_cm = config.cdb_maker

        if cdb is None:
            self.cdb = CDB(config=self.config)
        else:
            self.cdb = cdb

        # Build the required spacy pipeline
        self.pipeline = Pipeline(self.cdb, vocab=None, model_load_path=None)

    def reset_cdb(self) -> None:
        """This will re-create a new internal CDB based on the same config.

        This will be necessary if/when you're wishing to call `prepare_csvs`
        multiple times on the same object `CDBMaker` instance.
        """
        self.cdb = CDB(config=self.config)

    def prepare_csvs(self,
                     csv_paths: Union[pd.DataFrame, list[str]],
                     sep: str = ',',
                     encoding: Optional[str] = None,
                     escapechar: Optional[str] = None,
                     index_col: bool = False,
                     full_build: bool = False,
                     only_existing_cuis: bool = False, **kwargs: Any) -> CDB:
        r"""Compile one or multiple CSVs into a CDB.

        Note: This class/method generally uses the same instance of the CDB.
              So if you're using the same CDBMaker and calling `prepare_csvs`
              multiple times, you are likely to get leakage from prior calls
              into new ones.
              To reset the CDB, call `reset_cdb`.

        Args:
            csv_paths (Union[pd.DataFrame, list[str]]):
                An array of paths to the csv files that should be processed.
                Can also be an array of pd.DataFrames
            sep (str):
                If necessary a custom separator for the csv files
                Defaults to ','.
            encoding (Optional[str]):
                Encoding to be used for reading the CSV file
                Defaults to `None`.
            escapechar (Optional[str]):
                Escape char for the CSV (Default value None).
            index_col (bool):
                Index column for pandas read_csv (Default value False).
            full_build (bool):
                If False only the core portions of the CDB will be built (the
                ones required for the functioning of MedCAT). If True,
                everything will be added to the CDB - this
                usually includes concept descriptions, various forms of names
                etc (take care that this option produces a much larger CDB).
                Defaults to False.
            only_existing_cuis (bool):
                If True no new CUIs will be added, but only linked names will
                be extended. Mainly used when enriching names of a CDB (e.g.
                SNOMED with UMLS terms). Default to `False`.
            kwargs (Any):
                Will be passed to pandas for CSV reading

        Note:
            \*\*kwargs:
                Will be passed to pandas for CSV reading

        Returns:
            CDB: CDB with the new concepts added.
        """

        useful_columns = ['cui', 'name', 'ontologies', 'name_status',
                          'type_ids', 'description']
        name_status_options = {'A', 'P', 'N'}
        pn_cnf_parts = (self.config.general, self.config.preprocessing,
                        self.config.cdb_maker)

        for csv_path in csv_paths:
            # Read CSV, everything is converted to strings
            if isinstance(csv_path, str):
                logger.info("Started importing concepts from: {}".format(
                    csv_path))
                df = pd.read_csv(csv_path, sep=sep, encoding=encoding,
                                 escapechar=escapechar, index_col=index_col,
                                 dtype=str, **kwargs)
            else:
                # Not very clear, but csv_path can be a pre-loaded csv
                df = csv_path
            df = df.fillna('')

            # Find which columns to use from the CSV
            cols: list = []
            col2ind = {}
            for col in list(df.columns):
                if str(col).lower().strip() in useful_columns:
                    col2ind[str(col).lower().strip()] = len(cols)
                    cols.append(col)

            _time = None  # Used to check speed
            _logging_freq = np.ceil(len(df[cols]) / 100)
            multi_sep = self.cnf_cm.multi_separator
            for row_id, row in enumerate(df[cols].values):
                if row_id % _logging_freq == 0:
                    # Print some stats
                    if _time is None:
                        # Add last time if it does not exist
                        _time = datetime.datetime.now()
                    # Get current time
                    ctime = datetime.datetime.now()
                    # Get time difference
                    timediff = ctime - _time
                    logger.info(
                        "Current progress: %.0f%% at %.3fs per %d rows",
                        (row_id / len(df)) * 100,
                        timediff.microseconds / 10**6 + timediff.seconds,
                        (len(df[cols]) // 100))
                    # Set previous time to current time
                    _time = ctime

                # This must exist
                cui = row[col2ind['cui']].strip().upper()

                if not only_existing_cuis or (only_existing_cuis and
                                              cui in self.cdb.cui2info):
                    if 'ontologies' in col2ind:
                        ontologies = set(
                            [ontology.strip()
                             for ontology in row[col2ind['ontologies']
                                                 ].upper().split(multi_sep)
                             if len(ontology.strip()) > 0])
                    else:
                        ontologies = set()

                    if 'name_status' in col2ind:
                        name_status = row[col2ind['name_status']
                                          ].strip().upper()

                        # Must be allowed
                        if name_status not in name_status_options:
                            name_status = 'A'
                    else:
                        # Defaults to A - meaning automatic
                        name_status = 'A'

                    if 'type_ids' in col2ind:
                        type_ids = set(
                            [type_id.strip()
                             for type_id in row[col2ind['type_ids']
                                                ].upper().split(multi_sep)
                             if len(type_id.strip()) > 0])
                    else:
                        type_ids = set()

                    # Get the ones that do not need any changing
                    if 'description' in col2ind:
                        description = row[col2ind['description']].strip()
                    else:
                        description = ""

                    # We can have multiple versions of a name
                    # {'name': {'tokens': [<str>], 'snames': [<str>]}}
                    names: dict = {}

                    raw_names = [
                        raw_name.strip()
                        for raw_name in row[col2ind['name']].split(multi_sep)
                        if len(raw_name.strip()) > 0]
                    for raw_name in raw_names:
                        raw_name = raw_name.strip()
                        prepare_name(
                            raw_name, self.pipeline.tokenizer_with_tag,
                            names, pn_cnf_parts)

                        if (self.config.cdb_maker.remove_parenthesis > 0 and
                                name_status == 'P'):
                            # Should we remove the content in parenthesis
                            # from primary names and add them also
                            raw_name = PH_REMOVE.sub(" ", raw_name).strip()
                            if len(raw_name) >= self.cnf_cm.remove_parenthesis:
                                prepare_name(
                                    raw_name, self.pipeline.tokenizer_with_tag,
                                    names, pn_cnf_parts)

                    self.cdb._add_concept(
                        cui=cui, names=names, ontologies=ontologies,
                        name_status=name_status, type_ids=type_ids,
                        description=description, full_build=full_build)
                    # DEBUG
                    logger.debug(
                        "\n\n**** Added\n CUI: %s\n Names: %s\n Ontologies: %s"
                        "\n Name status: %s\n Type IDs: %s\n Description: %s\n"
                        " Is full build: %s",
                        cui, names, ontologies, name_status, type_ids,
                        description, full_build)

        return self.cdb
