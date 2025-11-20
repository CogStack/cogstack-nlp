from typing import Callable

from tqdm import tqdm

from common_pref import IS_V2

if IS_V2:
    from medcat.data.mctexport import MedCATTrainerExportDocument
    from medcat.data.mctexport import MedCATTrainerExportProject
    from medcat.utils.filters import project_filters
    from medcat.tokenizing.tokens import MutableEntity
    from medcat.cdb.concepts import CUIInfo
else:
    from medcat.stats.mctexport import MedCATTrainerExportDocument
    from medcat.stats.mctexport import MedCATTrainerExportProject
    from v1_helper import CUIInfo, project_filters, MutableEntity
from medcat.config import LinkingFilters


class StatsCalculator:
    """Calculates precision/recall statistics for entity linking."""

    def __init__(self, filters: LinkingFilters, cui2info: dict[str, CUIInfo]):
        self.filters = filters
        self.cui2info = cui2info
        self._reset()

    def _reset(self):
        self.tp = self.fp = self.fn = 0
        self.cui_tp: dict[str, int] = {}
        self.cui_fp: dict[str, int] = {}
        self.cui_fn: dict[str, int] = {}
        self.examples: dict[str, dict[str, list]] = {
            'tp': {}, 'fp': {}, 'fn': {}}

    def process_document(
        self,
        doc: MedCATTrainerExportDocument,
        predictions: list[MutableEntity]
    ) -> None:
        """
        Process a single document's annotations and predictions.

        Args:
            doc: Gold-standard annotated document
            predictions: Model's predicted entities
        """
        gold_anns = self._extract_gold_annotations(doc)
        pred_anns = self._extract_predictions(predictions)

        # Track which predictions have been matched
        matched_preds: set[int] = set()

        # Phase 1: Match gold annotations to predictions (find TPs and FNs)
        for gold in gold_anns:
            match_idx = self._find_matching_prediction(
                gold, pred_anns, matched_preds)

            if match_idx is not None:
                # True Positive
                matched_preds.add(match_idx)
                pred = pred_anns[match_idx]
                self._record_tp(gold, pred)
            else:
                # False Negative
                self._record_fn(gold)

        # Phase 2: Remaining predictions are False Positives
        for idx, pred in enumerate(pred_anns):
            if idx not in matched_preds:
                if self.filters.check_filters(pred["cui"]):
                    self._record_fp(pred)

    def process_project(self, project: MedCATTrainerExportProject,
                        entity_getter: Callable[[str], list[MutableEntity]],
                        use_project_filters: bool = True,
                        extra_cui_filter: set[str] | None = None,
                        show_progress: bool = True,
                        ) -> None:
        with project_filters(self.filters,
                             project,
                             extra_cui_filter,
                             use_project_filters):
            for doc in tqdm(project["documents"], disable=not show_progress,
                            desc="Documents"):
                self.process_document(doc, entity_getter(doc["text"]))

    def _extract_gold_annotations(
        self,
        doc: MedCATTrainerExportDocument
    ) -> list[dict]:
        """Extract validated gold annotations, supporting multi-CUI options."""
        gold_anns = []

        for ann in doc['annotations']:
            if not ann.get('validated', True):
                continue
            if ann.get('killed', False) or ann.get('deleted', False):
                continue

            # Support both single CUI and multiple acceptable CUIs
            cuis = ann.get('acceptable_cuis', ann['cui'])
            if not isinstance(cuis, list):
                cuis = [cuis]

            # Filter to valid CUIs
            valid_cuis = [
                cui for cui in cuis
                if self.filters.check_filters(cui)]

            if valid_cuis:
                gold_anns.append({
                    'start': ann['start'],
                    'end': ann['end'],
                    'cuis': valid_cuis,  # List of acceptable CUIs
                    'primary_cui': valid_cuis[0],  # For counting
                    'text': ann['value'],
                    'raw': ann
                })

        return gold_anns

    def _extract_predictions(
        self,
        predictions: list[MutableEntity]
    ) -> list[dict]:
        """Extract relevant info from predicted entities."""
        return [{
            'start': ent.base.start_char_index,
            'end': ent.base.end_char_index,
            'cui': ent.cui,
            'text': ent.base.text,
            'confidence': float(ent.context_similarity),
            'raw': ent
        } for ent in predictions if self.filters.check_filters(ent.cui)]

    def _find_matching_prediction(
        self,
        gold: dict,
        predictions: list[dict],
        matched_preds: set[int]
    ) -> int | None:
        """
        Find a prediction that matches this gold annotation.

        Matching criteria:
        - Same start position (can be relaxed for fuzzy matching)
        - Predicted CUI is in gold's acceptable CUIs
        - Not already matched
        """
        for idx, pred in enumerate(predictions):
            if idx in matched_preds:
                continue

            # Exact span match
            if pred['start'] == gold['start']:
                # Check if predicted CUI is acceptable
                if pred['cui'] in gold['cuis']:
                    return idx

        return None

    def _record_tp(self, gold: dict, pred: dict) -> None:
        """Record a true positive."""
        cui = pred['cui']
        self.tp += 1
        self.cui_tp[cui] = self.cui_tp.get(cui, 0) + 1

        if cui not in self.examples['tp']:
            self.examples['tp'][cui] = []
        self.examples['tp'][cui].append({
            'gold_text': gold['text'],
            'pred_text': pred['text'],
            'cui': cui,
            'start': pred['start'],
            'confidence': pred['confidence']
        })

    def _record_fn(self, gold: dict) -> None:
        """Record a false negative."""
        cui = gold['primary_cui']
        self.fn += 1
        self.cui_fn[cui] = self.cui_fn.get(cui, 0) + 1

        if cui not in self.examples['fn']:
            self.examples['fn'][cui] = []
        self.examples['fn'][cui].append({
            'text': gold['text'],
            'acceptable_cuis': gold['cuis'],
            'start': gold['start']
        })

    def _record_fp(self, pred: dict) -> None:
        """Record a false positive."""
        cui = pred['cui']
        self.fp += 1
        self.cui_fp[cui] = self.cui_fp.get(cui, 0) + 1

        if cui not in self.examples['fp']:
            self.examples['fp'][cui] = []
        self.examples['fp'][cui].append({
            'text': pred['text'],
            'cui': cui,
            'start': pred['start'],
            'confidence': pred['confidence']
        })

    def compute_metrics(self) -> dict:
        """Compute overall and per-CUI metrics."""
        metrics = {
            'overall': self._compute_prf(self.tp, self.fp, self.fn),
            'per_cui': {}
        }

        all_cuis = (
            set(self.cui_tp.keys()) | set(self.cui_fp.keys()) |
            set(self.cui_fn.keys()))

        for cui in all_cuis:
            tp = self.cui_tp.get(cui, 0)
            fp = self.cui_fp.get(cui, 0)
            fn = self.cui_fn.get(cui, 0)

            metrics['per_cui'][cui] = {
                'name': self._get_cui_name(cui),
                **self._compute_prf(tp, fp, fn),
                'tp': tp, 'fp': fp, 'fn': fn
            }

        return metrics

    @staticmethod
    def _compute_prf(tp: int, fp: int, fn: int) -> dict:
        """Compute precision, recall, F1."""
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0

        return {'precision': prec, 'recall': rec, 'f1': f1}

    def _get_cui_name(self, cui: str) -> str:
        """Get preferred name for CUI."""
        info = self.cui2info.get(cui)
        if info:
            return info.get('preferred_name') or list(info['names'])[0]
        return cui
