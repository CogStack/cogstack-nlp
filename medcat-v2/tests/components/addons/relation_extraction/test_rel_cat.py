import os
import shutil
import unittest
import json
import logging

from transformers.models.auto.tokenization_auto import AutoTokenizer

from medcat2.cdb import CDB
from medcat2.storage.serialisers import deserialise
from medcat2.config.config_rel_cat import ConfigRelCAT
from medcat2.components.addons.relation_extraction.rel_cat import RelCAT
from medcat2.components.addons.relation_extraction.bert.tokenizer import (
    BaseTokenizerWrapper)
from medcat2.tokenizing.tokenizers import create_tokenizer
from medcat2.components.addons.relation_extraction.rel_dataset import RelData

from .... import UNPACKED_EXAMPLE_MODEL_PACK_PATH, RESOURCES_PATH


class RelCATTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        config = ConfigRelCAT()
        config.general.device = "cpu"
        config.general.model_name = "bert-base-uncased"
        config.train.batch_size = 1
        config.train.nclasses = 3
        config.model.hidden_size = 256
        config.model.model_size = 2304
        config.general.log_level = logging.DEBUG

        tokenizer = BaseTokenizerWrapper(AutoTokenizer.from_pretrained(
            pretrained_model_name_or_path=config.general.model_name,
            config=config), add_special_tokens=True)

        SPEC_TAGS = ["[s1]", "[e1]", "[s2]", "[e2]"]

        tokenizer.hf_tokenizers.add_tokens(SPEC_TAGS, special_tokens=True)
        config.general.annotation_schema_tag_ids = (
            tokenizer.hf_tokenizers.convert_tokens_to_ids(SPEC_TAGS))

        cls.tmp_dir = os.path.join(
            os.path.dirname(os.path.realpath(__file__)), "tmp")
        os.makedirs(cls.tmp_dir, exist_ok=True)

        cls.save_model_path = os.path.join(cls.tmp_dir, "test_model")
        os.makedirs(cls.save_model_path, exist_ok=True)

        cdb: CDB = deserialise(
            os.path.join(UNPACKED_EXAMPLE_MODEL_PACK_PATH, "cdb"))

        cls.medcat_export_with_rels_path = os.path.join(
            RESOURCES_PATH,
            "medcat_trainer_export_relations.json")
        cls.medcat_rels_csv_path_train = os.path.join(
            RESOURCES_PATH,
            "medcat_rel_train.csv")
        cls.medcat_rels_csv_path_test = os.path.join(
            RESOURCES_PATH,
            "medcat_rel_test.csv")

        cls.mct_file_test = {}
        with open(cls.medcat_export_with_rels_path, "r+") as f:
            cls.mct_file_test = json.loads(
                f.read())["projects"][0]["documents"][1]

        cls.config_rel_cat: ConfigRelCAT = config
        cls.base_tokenizer = create_tokenizer(
            cdb.config.general.nlp.provider,
            # NOTE: the following only required for spacy models
            #       but the saved model should be a spacy model
            cdb.config.general.nlp.modelname,
            cdb.config.general.nlp.disabled_components,
            cdb.config.general.diacritics,
            cdb.config.preprocessing.max_document_length)
        cls.rel_cat: RelCAT = RelCAT(cls.base_tokenizer, cdb, config=config,
                                     init_model=True)

        cls.rel_cat.component.model.hf_model.resize_token_embeddings(
            len(tokenizer.hf_tokenizers))
        cls.rel_cat.component.model_config.hf_model_config.vocab_size = (
            tokenizer.get_size())

        cls.finished = False
        cls.tokenizer = tokenizer

    def test_dataset_relation_parser(self) -> None:

        samples = [
            "The [s1]45-year-old male[e1] was diagnosed with [s2]hypertension[e2] during his routine check-up.",  # noqa
            "The patient’s [s1]chest pain[e1] was associated with [s2]shortness of breath[e2].",  # noqa
            "[s1]Blood pressure[e1] readings of [s2]160/90 mmHg[e2] indicated possible hypertension.",  # noqa
            "His elevated [s1]blood glucose[e1] level of [s2]220 mg/dL[e2] raised concerns about his diabetes management.",  # noqa
            "The doctor recommended a [s1]cardiac enzyme test[e1] to assess the risk of [s2]myocardial infarction[e2].",  # noqa
            "The patient’s [s1]ECG[e1] showed signs of [s2]ischemia[e2]",
            "To manage his [s1]hypertension[e1], the patient was advised to [s2]reduce salt intake[e2].",  # noqa
            "[s1]Increased physical activity[e1][s2]type 2 diabetes[e2]."
        ]

        rel_dataset = RelData(cdb=self.rel_cat.cdb, config=self.config_rel_cat,
                              tokenizer=self.tokenizer)

        rels = []

        for idx in range(len(samples)):
            tkns = self.tokenizer(samples[idx])["tokens"]
            ent1_ent2_tokens_start_pos = (
                tkns.index("[s1]"), tkns.index("[s2]"))
            rels.append(rel_dataset.create_base_relations_from_doc(
                samples[idx], idx,
                ent1_ent2_tokens_start_pos=ent1_ent2_tokens_start_pos))

        self.assertEqual(len(rels), len(samples))

    def test_train_csv_no_tags(self) -> None:
        self.rel_cat.component.relcat_config.train.epochs = 2
        self.rel_cat.train(
            train_csv_path=self.medcat_rels_csv_path_train,
            test_csv_path=self.medcat_rels_csv_path_test,
            checkpoint_path=self.tmp_dir)
        self.rel_cat.save(self.save_model_path)

    def test_train_mctrainer(self) -> None:
        self.rel_cat = RelCAT.load(self.save_model_path)
        self.rel_cat.component.relcat_config.general.create_addl_rels = True
        self.rel_cat.component.relcat_config.general.addl_rels_max_sample_size = 10  # noqa
        self.rel_cat.component.relcat_config.train.test_size = 0.1
        self.rel_cat.component.relcat_config.train.nclasses = 3

        self.rel_cat.train(export_data_path=self.medcat_export_with_rels_path,
                           checkpoint_path=self.tmp_dir)

    def test_train_predict(self) -> None:
        # print("TEST TRAIN PREDICT")
        tknizer = self.base_tokenizer
        doc = tknizer(self.mct_file_test["text"])

        for ann in self.mct_file_test["annotations"]:
            # debug = ann["start"] == 2039 and ann["end"] == 2054
            # if debug:
            #     print("ANN", ann)
            tkn_idx = []
            for ind, word in enumerate(doc):
                # if debug:
                #     print("WORD", ind, ':', word)
                end_char = word.base.char_index + len(word.base.text)
                # if debug:
                #     print(" ",
                #           end_char, "<=", ann['end'],
                #           f"{end_char <= ann['end']}", "and",
                #           end_char, ">", ann['start'],
                #           f"{end_char > ann['start']}")
                if end_char <= ann['end'] and end_char > ann['start']:
                    tkn_idx.append(ind)
            entity = tknizer.create_entity(
                doc, min(tkn_idx), max(tkn_idx) + 1, label=ann["value"])
            entity.cui = ann["cui"]
            doc.all_ents.append(entity)

        self.rel_cat.component.model.hf_model.resize_token_embeddings(
            len(self.tokenizer.hf_tokenizers))

        doc = self.rel_cat(doc)
        self.finished = True

        self.assertGreater(len(doc.get_addon_data("relations")), 0)

    @classmethod
    def tearDownClass(cls) -> None:
        if os.path.exists(cls.tmp_dir):
            shutil.rmtree(cls.tmp_dir)


if __name__ == '__main__':
    unittest.main()
