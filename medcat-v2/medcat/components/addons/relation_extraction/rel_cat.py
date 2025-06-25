import json
import logging
import os
import random
from typing import Optional

from sklearn.utils import compute_class_weight
import torch
import torch.nn as nn

from tqdm import tqdm
from datetime import date, datetime
from typing import Iterable, Iterator, cast
from torch.utils.data import DataLoader, Sampler
from torch.optim import AdamW
from torch.optim.lr_scheduler import MultiStepLR
import numpy

from medcat.cdb import CDB
from medcat.vocab import Vocab
from medcat.config.config import Config, ComponentConfig
from medcat.config.config_rel_cat import ConfigRelCAT
from medcat.storage.serialisers import deserialise
from medcat.storage.serialisables import SerialisingStrategy
from medcat.components.addons.addons import AddonComponent
from medcat.components.addons.relation_extraction.base_component import (
    RelExtrBaseComponent)
from medcat.components.addons.meta_cat.ml_utils import set_all_seeds
from medcat.components.addons.relation_extraction.ml_utils import (
    load_results, load_state, save_results, save_state,
    split_list_train_test_by_class)
from medcat.components.addons.relation_extraction.rel_dataset import RelData
from medcat.tokenizing.tokenizers import BaseTokenizer, create_tokenizer
from medcat.tokenizing.tokens import MutableDocument
from medcat.utils.defaults import COMPONENTS_FOLDER


logger = logging.getLogger(__name__)


class RelCATAddon(AddonComponent):
    addon_type = 'rel_cat'
    output_key = 'relations'
    config: ConfigRelCAT

    def __init__(self, config: ConfigRelCAT,
                 rel_cat: "RelCAT"):
        self.config = config
        self._rel_cat = rel_cat

    @classmethod
    def create_new(cls, config: ConfigRelCAT, base_tokenizer: BaseTokenizer,
                   cdb: CDB) -> 'RelCATAddon':
        """Factory method to create a new MetaCATAddon instance."""
        return cls(config,
                   RelCAT(base_tokenizer, cdb, config=config, init_model=True))

    @classmethod
    def create_new_component(
            cls, cnf: ComponentConfig, tokenizer: BaseTokenizer,
            cdb: CDB, vocab: Vocab, model_load_path: Optional[str]
            ) -> 'RelCATAddon':
        if not isinstance(cnf, ConfigRelCAT):
            raise ValueError(f"Incompatible config: {cnf}")
        config = cnf
        if model_load_path is not None:
            load_path = os.path.join(model_load_path, COMPONENTS_FOLDER,
                                     cls.NAME_PREFIX + cls.addon_type)
            return cls.load_existing(config, tokenizer, cdb, load_path)
        return cls.create_new(config, tokenizer, cdb)

    @classmethod
    def load_existing(cls, cnf: ConfigRelCAT,
                      base_tokenizer: BaseTokenizer,
                      cdb: CDB,
                      load_path: str) -> 'RelCATAddon':
        """Factory method to load an existing RelCAT addon from disk."""
        rc = RelCAT.load(load_path)
        # set the correct base tokenizer and redo data paths
        rc.base_tokenizer = base_tokenizer
        rc._init_data_paths()
        return cls(cnf, rc)

    def serialise_to(self, folder_path: str) -> None:
        os.mkdir(folder_path)
        self._rel_cat.save(folder_path)

    @property
    def name(self) -> str:
        return str(self.addon_type)

    # for ManualSerialisable:

    @classmethod
    def deserialise_from(cls, folder_path: str, **init_kwargs
                         ) -> 'RelCATAddon':
        # NOTE: model load path sent by kwargs
        return cls.load_existing(
            load_path=folder_path,
            base_tokenizer=init_kwargs['tokenizer'],
            cnf=init_kwargs['cnf'],
            cdb=init_kwargs['cdb'],
        )

    def get_strategy(self) -> SerialisingStrategy:
        return SerialisingStrategy.MANUAL

    @classmethod
    def get_init_attrs(cls) -> list[str]:
        return []

    @classmethod
    def ignore_attrs(cls) -> list[str]:
        return []

    @classmethod
    def include_properties(cls) -> list[str]:
        return []

    def __call__(self, doc: MutableDocument):
        return self._rel_cat(doc)


class BalancedBatchSampler(Sampler):

    def __init__(self, dataset, classes,
                 batch_size, max_samples, max_minority):
        self.dataset = dataset
        self.classes = classes
        self.batch_size = batch_size
        self.num_classes = len(classes)
        self.indices = list(range(len(dataset)))

        self.max_minority = max_minority

        self.max_samples_per_class = max_samples

    def __len__(self):
        return (len(self.indices) + self.batch_size - 1) // self.batch_size

    def __iter__(self):
        batch_counter = 0
        indices = self.indices.copy()
        while batch_counter != self.__len__():
            batch = []

            class_counts = {c: 0 for c in self.classes}
            while len(batch) < self.batch_size:

                index = random.choice(indices)
                # Assuming label is at index 1
                label = self.dataset[index][2].numpy().tolist()[0]
                if class_counts[label] < self.max_samples_per_class[label]:
                    batch.append(index)
                    class_counts[label] += 1
                    if self.max_samples_per_class[label] > self.max_minority:
                        indices.remove(index)

            yield batch
            batch_counter += 1


class RelCAT:
    """The RelCAT class used for training 'Relation-Annotation' models, i.e.,
    annotation of relations between clinical concepts.

    Args:
        cdb (CDB): cdb, this is used when creating relation datasets.

        tokenizer (TokenizerWrapperBERT):
            The Huggingface tokenizer instance. This can be a pre-trained
            tokenzier instance from a BERT-style model. For now, only
            BERT models are supported.

        config (ConfigRelCAT):
            the configuration for RelCAT. Param descriptions available in
            ConfigRelCAT class docs.

        task (str, optional): What task is this model supposed to handle.
            Defaults to "train"
        init_model (bool, optional): loads default model. Defaults to False.

    """
    addon_type = 'rel_cat'
    output_key = 'rel_'

    def __init__(self, base_tokenizer: BaseTokenizer,
                 cdb: CDB, config: ConfigRelCAT = ConfigRelCAT(),
                 task: str = "train", init_model: bool = False):
        self.base_tokenizer = base_tokenizer
        self.component = RelExtrBaseComponent()
        self.task: str = task
        self.checkpoint_path: str = "./"

        set_all_seeds(config.general.seed)

        if init_model:
            self.component = RelExtrBaseComponent(
                config=config, task=task, init_model=True)

        self.cdb = cdb
        logging.basicConfig(
            level=self.component.relcat_config.general.log_level)
        logger.setLevel(self.component.relcat_config.general.log_level)

        self.is_cuda_available = torch.cuda.is_available()
        self.device = torch.device(
            "cuda" if self.is_cuda_available and
            self.component.relcat_config.general.device != "cpu" else "cpu")
        self._init_data_paths()

    def _init_data_paths(self):
        doc_cls = self.base_tokenizer.get_doc_class()
        doc_cls.register_addon_path('relations', def_val=[], force=True)

    def save(self, save_path: str = "./") -> None:
        self.component.save(save_path=save_path)

    @classmethod
    def load(cls, load_path: str = "./") -> "RelCAT":

        if os.path.exists(os.path.join(load_path, "cdb.dat")):
            cdb = cast(CDB, deserialise(os.path.join(load_path, "cdb.dat")))
        else:
            cdb = CDB(config=Config())
            logger.info(
                "The default CDB file name 'cdb.dat' doesn't exist in the "
                "specified path, you will need to load & set "
                "a CDB manually via rel_cat.cdb = CDB.load('path') ")

        component = RelExtrBaseComponent.load(
            pretrained_model_name_or_path=load_path)

        device = torch.device(
            "cuda" if torch.cuda.is_available() and
            component.relcat_config.general.device != "cpu" else "cpu")

        rel_cat = RelCAT(
            # NOTE: this is a throaway tokenizer just for registrations
            create_tokenizer(cdb.config.general.nlp.provider, cdb.config),
            cdb=cdb, config=component.relcat_config, task=component.task)
        rel_cat.device = device
        rel_cat.component = component

        return rel_cat

    def __call__(self, doc: MutableDocument) -> MutableDocument:
        doc = next(self.pipe(iter([doc])))
        return doc

    def _create_test_train_datasets(self, data: dict,
                                    split_sets: bool = False):
        train_data: dict = {}
        test_data: dict = {}

        if split_sets:
            rc_cnf = self.component.relcat_config
            (train_data["output_relations"],
             test_data["output_relations"]) = split_list_train_test_by_class(
                 data["output_relations"],
                 test_size=rc_cnf.train.test_size,
                 shuffle=rc_cnf.train.shuffle_data,
                 sample_limit=rc_cnf.general.limit_samples_per_class)

            test_data_label_names = [
                rec[4] for rec in test_data["output_relations"]]

            (test_data["nclasses"], test_data["labels2idx"],
             test_data["idx2label"]) = RelData.get_labels(
                test_data_label_names, self.component.relcat_config)

            for idx in range(len(test_data["output_relations"])):
                test_data["output_relations"
                          ][idx][5] = test_data["labels2idx"][
                              test_data["output_relations"][idx][4]]
        else:
            train_data["output_relations"] = data["output_relations"]

        for k, v in data.items():
            if k != "output_relations":
                train_data[k] = []
                test_data[k] = []

        train_data_label_names = [rec[4]
                                  for rec in train_data["output_relations"]]

        (train_data["nclasses"], train_data["labels2idx"],
         train_data["idx2label"]) = RelData.get_labels(
            train_data_label_names, self.component.relcat_config)

        for idx in range(len(train_data["output_relations"])):
            train_data["output_relations"
                       ][idx][5] = train_data["labels2idx"][
                           train_data["output_relations"][idx][4]]

        return train_data, test_data

    def train(self, export_data_path: str = "", train_csv_path: str = "",
              test_csv_path: str = "", checkpoint_path: str = "./"):

        if self.is_cuda_available:
            logger.info("Training on device: %s%s",
                        str(torch.cuda.get_device_name(0)), str(self.device))

        self.component.model = self.component.model.to(self.device)

        rc_cnf = self.component.relcat_config

        # resize vocab just in case more tokens have been added
        self.component.model_config.vocab_size = (
            self.component.tokenizer.get_size())

        train_rel_data = RelData(
            cdb=self.cdb, config=rc_cnf,
            tokenizer=self.component.tokenizer)
        test_rel_data = RelData(
            cdb=self.cdb, config=rc_cnf,
            tokenizer=self.component.tokenizer)

        if train_csv_path != "":
            if test_csv_path != "":
                train_rel_data.dataset, _ = self._create_test_train_datasets(
                    train_rel_data.create_base_relations_from_csv(
                        train_csv_path), split_sets=False)
                test_rel_data.dataset, _ = self._create_test_train_datasets(
                    train_rel_data.create_base_relations_from_csv(
                        test_csv_path), split_sets=False)
            else:
                (train_rel_data.dataset,
                 test_rel_data.dataset) = self._create_test_train_datasets(
                    train_rel_data.create_base_relations_from_csv(
                        train_csv_path), split_sets=True)

        elif export_data_path != "":
            export_data = {}
            with open(export_data_path) as f:
                export_data = json.load(f)
            (train_rel_data.dataset,
             test_rel_data.dataset) = self._create_test_train_datasets(
                train_rel_data.create_relations_from_export(export_data),
                split_sets=True)
        else:
            raise ValueError(
                "NO DATA HAS BEEN PROVIDED (MedCAT Trainer export "
                "JSON/CSV/spacy_DOCS)")

        train_dataset_size = len(train_rel_data)
        batch_size = (
            train_dataset_size if train_dataset_size < rc_cnf.train.batch_size
            else rc_cnf.train.batch_size)

        # to use stratified batching
        if rc_cnf.train.stratified_batching:
            sampler = BalancedBatchSampler(
                train_rel_data, [
                    i for i in
                    range(rc_cnf.train.nclasses)],
                batch_size,
                rc_cnf.train.batching_samples_per_class,
                rc_cnf.train.batching_minority_limit)

            train_dataloader = DataLoader(
                train_rel_data, num_workers=0,
                collate_fn=self.component.padding_seq,
                batch_sampler=sampler,
                pin_memory=rc_cnf.general.pin_memory)
        else:
            train_dataloader = DataLoader(
                train_rel_data, batch_size=batch_size,
                shuffle=rc_cnf.train.shuffle_data,
                num_workers=0,
                collate_fn=self.component.padding_seq,
                pin_memory=rc_cnf.general.pin_memory)

        test_dataset_size = len(test_rel_data)
        test_batch_size = (
            test_dataset_size if
            test_dataset_size < rc_cnf.train.batch_size
            else rc_cnf.train.batch_size)
        test_dataloader = DataLoader(
            test_rel_data,
            batch_size=test_batch_size,
            shuffle=rc_cnf.train.shuffle_data,
            num_workers=0,
            collate_fn=self.component.padding_seq,
            pin_memory=rc_cnf.general.pin_memory)

        if (rc_cnf.train.class_weights is not None and
                rc_cnf.train.enable_class_weights):
            criterion = nn.CrossEntropyLoss(weight=torch.FloatTensor(
                numpy.asarray(rc_cnf.train.class_weights)
                ).to(self.device))
        elif rc_cnf.train.enable_class_weights:
            all_class_lbl_ids = [
                rec[5] for rec in train_rel_data.dataset["output_relations"]]
            rc_cnf.train.class_weights = (
                compute_class_weight(class_weight="balanced",
                                     classes=numpy.unique(all_class_lbl_ids),
                                     y=all_class_lbl_ids).tolist())
            criterion = nn.CrossEntropyLoss(weight=torch.FloatTensor(
                rc_cnf.train.class_weights).to(
                    self.device))
        else:
            criterion = nn.CrossEntropyLoss()

        if self.component.optimizer is None:
            parameters = filter(lambda p: p.requires_grad,
                                self.component.model.parameters())
            self.component.optimizer = AdamW(
                parameters, lr=self.component.relcat_config.train.lr,
                weight_decay=rc_cnf.train.adam_weight_decay,
                betas=rc_cnf.train.adam_betas, eps=rc_cnf.train.adam_epsilon)

        if self.component.scheduler is None:
            self.component.scheduler = MultiStepLR(
                self.component.optimizer,
                milestones=rc_cnf.train.multistep_milestones,
                gamma=rc_cnf.train.multistep_lr_gamma)

        self.epoch, self.best_f1 = load_state(
            self.component.model, self.component.optimizer,
            self.component.scheduler, load_best=False, path=checkpoint_path,
            relcat_config=rc_cnf)

        logger.info("Starting training process...")

        losses_per_epoch, accuracy_per_epoch, f1_per_epoch = load_results(
            path=checkpoint_path)

        if train_rel_data.dataset["nclasses"] > rc_cnf.train.nclasses:
            rc_cnf.train.nclasses = train_rel_data.dataset["nclasses"]
            self.component.model.relcat_config.train.nclasses = (
                rc_cnf.train.nclasses)

        rc_cnf.general.labels2idx.update(train_rel_data.dataset["labels2idx"])
        rc_cnf.general.idx2labels = {
            int(v): k for k, v in rc_cnf.general.labels2idx.items()}

        gradient_acc_steps = (
            rc_cnf.train.gradient_acc_steps)
        max_grad_norm = rc_cnf.train.max_grad_norm

        _epochs = self.epoch + rc_cnf.train.nepochs

        for epoch in range(0, _epochs):
            epoch_losses, epoch_precision, epoch_f1 = self._train_epoch(
                epoch, gradient_acc_steps, max_grad_norm, train_dataset_size,
                train_dataloader, test_dataloader, criterion, _epochs,
                checkpoint_path)
            losses_per_epoch.extend(epoch_losses)
            accuracy_per_epoch.extend(epoch_precision)
            f1_per_epoch.extend(epoch_f1)

    def _train_epoch(self, epoch: int,
                     gradient_acc_steps: int,
                     max_grad_norm: float,
                     train_dataset_size: int,
                     train_dataloader: DataLoader,
                     test_dataloader: DataLoader,
                     criterion: nn.CrossEntropyLoss,
                     _epochs: int,
                     checkpoint_path: str) -> tuple[list, list, list]:
        rc_cnf = self.component.relcat_config
        start_time = datetime.now().time()
        total_loss = 0.0

        loss_per_batch = []
        accuracy_per_batch = []

        logger.info(
            "Total epochs on this model: %d | currently training "
            "epoch %d", _epochs, epoch)

        pbar = tqdm(total=train_dataset_size)

        for i, data in enumerate(train_dataloader, 0):
            self.component.model.train()
            self.component.model.zero_grad()

            current_batch_size = len(data[0])
            token_ids, e1_e2_start, labels, _, _ = data

            attention_mask = (
                token_ids != self.component.pad_id).float().to(self.device)

            token_type_ids = torch.zeros(
                (token_ids.shape[0], token_ids.shape[1])).long().to(
                    self.device)

            labels = labels.to(self.device)

            model_output, classification_logits = self.component.model(
                input_ids=token_ids,
                token_type_ids=token_type_ids,
                attention_mask=attention_mask,
                e1_e2_start=e1_e2_start
            )

            batch_loss = criterion(
                classification_logits.view(
                    -1, rc_cnf.train.nclasses).to(self.device),
                labels.squeeze(1))

            batch_loss.backward()
            batch_loss = batch_loss / gradient_acc_steps

            total_loss += batch_loss.item() / current_batch_size

            (batch_acc, _, batch_precision, batch_f1,
                _, _, batch_stats_per_label) = self.evaluate_(
                classification_logits, labels, ignore_idx=-1)

            loss_per_batch.append(batch_loss / current_batch_size)
            accuracy_per_batch.append(batch_acc)

            torch.nn.utils.clip_grad_norm_(
                self.component.model.parameters(), max_grad_norm)

            if (i % gradient_acc_steps) == 0:
                self.component.optimizer.step()
                self.component.scheduler.step()
            if ((i + 1) % current_batch_size == 0):
                logger.debug(
                    "[Epoch: %d, loss per batch, accuracy per batch: %.3f,"
                    " %.3f, average total loss %.3f , total loss %.3f]",
                    epoch, loss_per_batch[-1], accuracy_per_batch[-1],
                    total_loss / (i + 1), total_loss)

            pbar.update(current_batch_size)

        pbar.close()

        losses_per_epoch = []
        accuracy_per_epoch = []
        f1_per_epoch = []
        if len(loss_per_batch) > 0:
            losses_per_epoch.append(
                sum(loss_per_batch) / len(loss_per_batch))
            logger.info("Losses at Epoch %d: %.5f" %
                        (epoch, losses_per_epoch[-1]))

        if len(accuracy_per_batch) > 0:
            accuracy_per_epoch.append(
                sum(accuracy_per_batch) / len(accuracy_per_batch))
            logger.info("Train accuracy at Epoch %d: %.5f" %
                        (epoch, accuracy_per_epoch[-1]))

        total_loss = total_loss / (i + 1)

        end_time = datetime.now().time()

        logger.info(
            "========================"
            " TRAIN SET TEST RESULTS "
            "========================")
        _ = self.evaluate_results(train_dataloader, self.component.pad_id)

        logger.info(
            "========================"
            " TEST SET TEST RESULTS "
            "========================")
        results = self.evaluate_results(
            test_dataloader, self.component.pad_id)

        f1_per_epoch.append(results['f1'])

        logger.info("Epoch finished, took %s seconds",
                    str(datetime.combine(date.today(), end_time)
                        - datetime.combine(date.today(), start_time)))

        self.epoch += 1

        if len(f1_per_epoch) > 0 and f1_per_epoch[-1] > self.best_f1:
            self.best_f1 = f1_per_epoch[-1]
            save_state(
                self.component.model, self.component.optimizer,
                self.component.scheduler, self.epoch, self.best_f1,
                checkpoint_path, model_name=rc_cnf.general.model_name,
                task=self.task, is_checkpoint=False)

        if (epoch % 1) == 0:
            save_results(
                {
                    "losses_per_epoch": losses_per_epoch,
                    "accuracy_per_epoch": accuracy_per_epoch,
                    "f1_per_epoch": f1_per_epoch,
                    "epoch": epoch
                }, file_prefix="train", path=checkpoint_path)
            save_state(self.component.model, self.component.optimizer,
                       self.component.scheduler, self.epoch, self.best_f1,
                       checkpoint_path,
                       model_name=rc_cnf.general.model_name,
                       task=self.task, is_checkpoint=True)
        return losses_per_epoch, accuracy_per_epoch, f1_per_epoch

    def evaluate_(self, output_logits, labels, ignore_idx):
        # ignore index (padding) when calculating accuracy
        idxs = (labels != ignore_idx).squeeze()
        labels_ = labels.squeeze()[idxs].to(self.device)
        pred_labels = torch.softmax(output_logits, dim=1).max(1)[1]
        pred_labels = pred_labels[idxs].to(self.device)

        true_labels = labels_.cpu().numpy().tolist(
        ) if labels_.is_cuda else labels_.numpy().tolist()
        pred_labels = pred_labels.cpu().numpy().tolist(
        ) if pred_labels.is_cuda else pred_labels.numpy().tolist()

        unique_labels = set(true_labels)

        batch_size = len(true_labels)

        stat_per_label = dict()

        total_tp, total_fp, total_tn, total_fn = 0, 0, 0, 0
        acc, micro_recall, micro_precision, micro_f1 = 0, 0, 0, 0

        for label in unique_labels:
            stat_per_label[label] = {
                "tp": 0, "fp": 0, "tn": 0, "fn": 0,
                "f1": 0.0, "acc": 0.0, "prec": 0.0, "recall": 0.0}

            for true_label_idx in range(len(true_labels)):
                if true_labels[true_label_idx] == label:
                    if pred_labels[true_label_idx] == label:
                        stat_per_label[label]["tp"] += 1
                        total_tp += 1
                    if pred_labels[true_label_idx] != label:
                        stat_per_label[label]["fp"] += 1
                        total_fp += 1
                elif (true_labels[true_label_idx] != label and
                      label == pred_labels[true_label_idx]):
                    stat_per_label[label]["fn"] += 1
                    total_fn += 1
                else:
                    stat_per_label[label]["tn"] += 1
                    total_tn += 1

            lbl_tp_tn = stat_per_label[label]["tn"] + \
                stat_per_label[label]["tp"]

            lbl_tp_fn = stat_per_label[label]["fn"] + \
                stat_per_label[label]["tp"]
            lbl_tp_fn = lbl_tp_fn if lbl_tp_fn > 0.0 else 1.0

            lbl_tp_fp = stat_per_label[label]["tp"] + \
                stat_per_label[label]["fp"]
            lbl_tp_fp = lbl_tp_fp if lbl_tp_fp > 0.0 else 1.0

            stat_per_label[label]["acc"] = lbl_tp_tn / batch_size
            stat_per_label[label]["prec"] = (stat_per_label[label]["tp"] /
                                             lbl_tp_fp)
            stat_per_label[label]["recall"] = (stat_per_label[label]["tp"] /
                                               lbl_tp_fn)

            lbl_re_pr = stat_per_label[label]["recall"] + \
                stat_per_label[label]["prec"]
            lbl_re_pr = lbl_re_pr if lbl_re_pr > 0.0 else 1.0

            stat_per_label[label]["f1"] = (
                2 * (stat_per_label[label]["recall"] *
                     stat_per_label[label]["prec"])) / lbl_re_pr

        tp_fn = total_fn + total_tp
        tp_fn = tp_fn if tp_fn > 0.0 else 1.0

        tp_fp = total_fp + total_tp
        tp_fp = tp_fp if tp_fp > 0.0 else 1.0

        micro_recall = total_tp / tp_fn
        micro_precision = total_tp / tp_fp

        re_pr = micro_recall + micro_precision
        re_pr = re_pr if re_pr > 0.0 else 1.0
        micro_f1 = (2 * (micro_recall * micro_precision)) / re_pr

        acc = total_tp / batch_size

        return (acc, micro_recall, micro_precision, micro_f1,
                pred_labels, true_labels, stat_per_label)

    def evaluate_results(self, data_loader, pad_id):
        logger.info("Evaluating test samples...")
        rc_cnf = self.component.relcat_config
        if (rc_cnf.train.class_weights is not None and
                rc_cnf.train.enable_class_weights):
            criterion = nn.CrossEntropyLoss(weight=torch.FloatTensor(
                rc_cnf.train.class_weights).to(self.device))
        else:
            criterion = nn.CrossEntropyLoss()

        total_loss, total_acc, total_f1, total_recall, total_precision = (
            0.0, 0.0, 0.0, 0.0, 0.0)
        all_batch_stats_per_label = []

        self.component.model.eval()

        for i, data in enumerate(data_loader):
            with torch.no_grad():
                token_ids, e1_e2_start, labels, _, _ = data
                attention_mask = (token_ids != pad_id).float().to(self.device)
                token_type_ids = torch.zeros(
                    (*token_ids.shape[:2],)).long().to(self.device)

                labels = labels.to(self.device)

                model_output, pred_classification_logits = (
                    self.component.model(token_ids,
                                         token_type_ids=token_type_ids,
                                         attention_mask=attention_mask,
                                         Q=None,
                                         e1_e2_start=e1_e2_start))

                batch_loss = criterion(pred_classification_logits.view(
                    -1, rc_cnf.train.nclasses).to(self.device),
                    labels.squeeze(1))
                total_loss += batch_loss.item()

                (batch_accuracy, batch_recall, batch_precision, batch_f1,
                 pred_labels, true_labels, batch_stats_per_label) = (
                    self.evaluate_(pred_classification_logits,
                                   labels, ignore_idx=-1))

                all_batch_stats_per_label.append(batch_stats_per_label)

                total_acc += batch_accuracy
                total_recall += batch_recall
                total_precision += batch_precision
                total_f1 += batch_f1

        final_stats_per_label = {}

        for batch_label_stats in all_batch_stats_per_label:
            for label_id, stat_dict in batch_label_stats.items():

                if label_id not in final_stats_per_label.keys():
                    final_stats_per_label[label_id] = stat_dict
                else:
                    for stat, score in stat_dict.items():
                        final_stats_per_label[label_id][stat] += score

        for label_id, stat_dict in final_stats_per_label.items():
            for stat_name, value in stat_dict.items():
                final_stats_per_label[label_id][stat_name] = value / (i + 1)

        total_loss = total_loss / (i + 1)
        total_acc = total_acc / (i + 1)
        total_precision = total_precision / (i + 1)
        total_f1 = total_f1 / (i + 1)
        total_recall = total_recall / (i + 1)

        results = {
            "loss": total_loss,
            "accuracy": total_acc,
            "precision": total_precision,
            "recall": total_recall,
            "f1": total_f1
        }

        logger.info("=" * 20 + " Evaluation Results " + "=" * 20)
        logger.info(" no. of batches:" + str(i + 1))
        for key in sorted(results.keys()):
            logger.info(" %s = %0.3f" % (key, results[key]))
        logger.info("-" * 23 + " class stats " + "-" * 23)
        for label_id, stat_dict in final_stats_per_label.items():
            logger.info(
                "label: %s | f1: %0.3f | prec : %0.3f | acc: %0.3f | "
                "recall: %0.3f ",
                rc_cnf.general.idx2labels[label_id],
                stat_dict["f1"],
                stat_dict["prec"],
                stat_dict["acc"],
                stat_dict["recall"]
            )
        logger.info("-" * 59)
        logger.info("=" * 59)

        return results

    def pipe(self, stream: Iterable[MutableDocument], *args, **kwargs
             ) -> Iterator[MutableDocument]:
        rc_cnf = self.component.relcat_config

        predict_rel_dataset = RelData(
            cdb=self.cdb, config=rc_cnf,
            tokenizer=self.component.tokenizer)

        self.component.model = self.component.model.to(self.device)

        for doc_id, doc in enumerate(stream, 0):
            predict_rel_dataset.dataset, _ = self._create_test_train_datasets(
                data=predict_rel_dataset.create_base_relations_from_doc(
                    doc, doc_id=str(doc_id)),
                split_sets=False)

            predict_dataloader = DataLoader(
                dataset=predict_rel_dataset, shuffle=False,
                batch_size=rc_cnf.train.batch_size,
                num_workers=0, collate_fn=self.component.padding_seq,
                pin_memory=rc_cnf.general.pin_memory)

            total_rel_found = len(
                predict_rel_dataset.dataset["output_relations"])
            rel_idx = -1

            logger.info("total relations for doc: " + str(total_rel_found))
            logger.info("processing...")

            pbar = tqdm(total=total_rel_found)

            for i, data in enumerate(predict_dataloader):
                with torch.no_grad():
                    token_ids, e1_e2_start, labels, _, _ = data

                    attention_mask = (
                        token_ids != self.component.pad_id
                        ).float().to(self.device)
                    token_type_ids = torch.zeros(
                        *token_ids.shape[:2]).long().to(self.device)

                    (model_output,
                     pred_classification_logits) = self.component.model(
                        token_ids, token_type_ids=token_type_ids,
                        attention_mask=attention_mask,
                        e1_e2_start=e1_e2_start)

                    for i, pred_rel_logits in enumerate(
                            pred_classification_logits):
                        rel_idx += 1

                        confidence = torch.softmax(
                            pred_rel_logits, dim=0).max(0)
                        predicted_label_id = int(confidence[1].item())

                        relations: list = doc.get_addon_data(  # type: ignore
                            "relations")
                        relations.append(
                            {
                                "relation": rc_cnf.general.idx2labels[
                                    predicted_label_id],
                                "label_id": predicted_label_id,
                                "ent1_text": predict_rel_dataset.dataset[
                                    "output_relations"][rel_idx][
                                    2],
                                "ent2_text": predict_rel_dataset.dataset[
                                    "output_relations"][rel_idx][
                                    3],
                                "confidence": float("{:.3f}".format(
                                    confidence[0])),
                                "start_ent_pos": "",
                                "end_ent_pos": "",
                                "start_entity_id":
                                    predict_rel_dataset.dataset[
                                        "output_relations"][rel_idx][8],
                                "end_entity_id":
                                    predict_rel_dataset.dataset[
                                        "output_relations"][rel_idx][9]
                            })
                    pbar.update(len(token_ids))
            pbar.close()

            yield doc

    def predict_text_with_anns(self, text: str, annotations: list[dict]
                               ) -> MutableDocument:
        """ Creates spacy doc from text and annotation input.
        Predicts using self.__call__

        Args:
            text (str): text
            annotations (dict): dict containing the entities from NER
                (of your choosing), the format must be the following format:
                    [
                        {
                            "cui": "202099003", -this is optional
                            "value": "discoid lateral meniscus",
                            "start": 294,
                            "end": 318
                        },
                        {
                            "cui": "202099003",
                            "value": "Discoid lateral meniscus",
                            "start": 1905,
                            "end": 1929,
                        }
                    ]

        Returns:
            Doc: spacy doc with the relations.
        """
        # NOTE: This runs not an empty language, but the specified one
        base_tokenizer = create_tokenizer(
            self.cdb.config.general.nlp.provider, self.cdb.config)
        doc = base_tokenizer(text)

        for ann in annotations:
            tkn_idx = []
            for ind, word in enumerate(doc):
                end_char = word.base.char_index + len(word.base.text)
                if end_char <= ann['end'] and end_char > ann['start']:
                    tkn_idx.append(ind)
            entity = base_tokenizer.create_entity(
                doc, min(tkn_idx), max(tkn_idx) + 1, label=ann["value"])
            entity.cui = ann["cui"]
            doc.ner_ents.append(entity)

        doc = self(doc)

        return doc
