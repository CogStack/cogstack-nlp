from typing import Optional, Callable, TextIO, TypedDict

from tqdm import tqdm

from medcat.cat import CAT
from medcat.utils.filters import project_filters
from medcat.data.mctexport import (
    MedCATTrainerExport, MedCATTrainerExportProject,
    MedCATTrainerExportDocument)
from medcat.config.config import LinkingFilters
from medcat.cdb.concepts import CUIInfo, get_new_cui_info
from medcat.tokenizing.tokens import MutableEntity, UNTOKENIZABLE_ENTITY_ID
from medcat.components.types import CoreComponentType
from medcat.utils.training_utils import dataset_aware_component
from collections import defaultdict
from pydantic import BaseModel, Field
from enum import Enum

class MetricMode(str, Enum):
    """Supported evaluation modes for statistics collection."""

    FULL = "full"
    NER = "ner"
    LINKING = "linking"


class RawStats(BaseModel):
    """Raw accumulated state for a single evaluation mode."""

    tp: int = 0
    fp: int = 0
    fn: int = 0
    # Number of labels where it is not possible to generate an entity
    # Because the tokenizer doesn't find a single token
    # i.e. entity at chars 100-103, token is 100-104.
    no_tokens: int = 0

    # per document IoU metrics, summed over all documents and 
    # averaged later via char_docs, which counts the number of 
    # documents that have entities that have been processed.
    iou_sum: float = 0.0
    giou_sum: float = 0.0
    cohen_k_sum: float = 0.0
    char_docs: int = 0

    # metrics for individual CUIs
    cui_tp: dict[str, int] = Field(default_factory=dict)
    cui_fp: dict[str, int] = Field(default_factory=dict)
    cui_fn: dict[str, int] = Field(default_factory=dict)
    # gold counts is the number of labels for that CUI
    cui_gold_counts: dict[str, int] = Field(default_factory=dict)
    cui_no_tokens: dict[str, int] = Field(default_factory=dict)
    
    examples: dict[str, dict[str, list]] = {
        'tp': {}, 'fp': {}, 'fn': {}}

    # character metrics for individual CUIs
    cui_iou: defaultdict[str, list[float]] = Field(
        default_factory=lambda: defaultdict[str, list[float]](list)
    )
    cui_giou: defaultdict[str, list[float]] = Field(
        default_factory=lambda: defaultdict[str, list[float]](list)
    )
    cui_cohen_k: defaultdict[str, list[float]] = Field(
        default_factory=lambda: defaultdict[str, list[float]](list)
    )


class OverallMetrics(BaseModel):
    """Project / Mode level metrics, calculated from RawStats."""
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    
    # Number of labels where it is not possible to generate an entity
    no_tokens: int = 0
    # Number of labels in entire project where it is not 
    # possible to generate an entity
    no_tokens_ratio: float = 0.0

    tp: int = 0
    fp: int = 0
    fn: int = 0

    char_iou: float = 0.0
    char_giou: float = 0.0
    char_cohen_k: float = 0.0


class CUIMetrics(BaseModel):
    """Metrics on a per cui basis."""
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0

    tp: int = 0
    fp: int = 0
    fn: int = 0

    char_iou: float = 0.0
    char_giou: float = 0.0
    char_cohen_k: float = 0.0

    char_iou_n: float = 0.0
    char_giou_n: float = 0.0
    char_cohen_k_n: float = 0.0


class Metrics(BaseModel):
    """Calculated metrics for a single evaluation mode."""

    overall: OverallMetrics
    per_cui: dict[str, CUIMetrics] = Field(default_factory=dict)


class GoldAnnotation(TypedDict):
    """Validated gold annotation payload after CUI filtering."""

    start: int
    end: int
    cuis: list[str]
    cui: str
    text: str
    raw: object


class PredictedAnnotation(TypedDict):
    """Predicted entity payload used for scoring and metrics."""

    start: int
    end: int
    cui: str
    text: str
    confidence: float
    raw: MutableEntity
    no_tokens: int


class ModeStats(BaseModel):
    """Accumulated state and calculated metrics for one evaluation mode."""

    stats: RawStats = Field(default_factory=RawStats)
    metrics: Metrics | None = None
    
class ProjectStats(BaseModel):
    """Accumulated state and calculated metrics for one project 
    or all projects."""
    full_pipeline: ModeStats = Field(
        default_factory=ModeStats
    )
    ner: ModeStats | None = None
    linking: ModeStats | None = None

    _MODE_FIELDS = {
        MetricMode.FULL: "full_pipeline",
        MetricMode.NER: "ner",
        MetricMode.LINKING: "linking",
    }

    def get_mode(self, mode: MetricMode) -> ModeStats | None:
        """Get statistics for the requested evaluation mode."""
        try:
            normalized_mode = MetricMode(mode)
            field_name = self._MODE_FIELDS[normalized_mode]
        except (KeyError, ValueError) as e:
            raise ValueError(f"Unknown metric mode: {mode}") from e

        return getattr(self, field_name)
    
    @classmethod
    def create(
        cls,
        ner: bool = False,
        linking: bool = False,
    ) -> "ProjectStats":
        return cls(
            ner=ModeStats() if ner else None,
            linking=ModeStats() if linking else None,
        )
    
class StatsCollection(BaseModel):
    """Accumulated state and calculated metrics for all projects."""
    all_projects: ProjectStats = Field(
        default_factory=ProjectStats
    )
    projects: dict[int, ProjectStats] = Field(
        default_factory=dict
    )

    def get_project_stats(self, project_index: int) -> ProjectStats:
        """Return statistics for a single project."""
        return self.projects[project_index]

    def get_aggregate_stats(self) -> ProjectStats:
        """Return the aggregate statistics across all projects."""
        return self.all_projects

    @classmethod
    def create(
        cls,
        num_projects: int,
        ner: bool = False,
        linking: bool = False,
    ) -> "StatsCollection":
        return cls(
            all_projects=ProjectStats.create(
                ner=ner,
                linking=linking,
            ),
            projects={
                i: ProjectStats.create(
                    ner=ner,
                    linking=linking,
                )
                for i in range(num_projects)
            },
        )
    
class StatsCalculator:
    """Calculates statistics for entity linking."""

    BUCKET_FULL = MetricMode.FULL
    BUCKET_NER = MetricMode.NER
    BUCKET_LINKING = MetricMode.LINKING

    def __init__(self,
                 filters: LinkingFilters,
                 cui2info: dict[str, CUIInfo],
                 num_projects: int,
                 ner_performance: bool = False,
                 linking_performance: bool = False,
                 ) -> None:
        self.filters = filters
        self.cui2info = cui2info
        self.reset(num_projects, 
                   ner_performance,
                   linking_performance)

    def reset(self, 
              num_projects: int, 
              ner_performance: bool = False, 
              linking_performance: bool = False) -> None:
        self.ner_performance = ner_performance
        self.linking_performance = linking_performance
        self.num_projects = num_projects
        self.stats = StatsCollection().create(
            num_projects=self.num_projects,
            ner=self.ner_performance,
            linking=self.linking_performance
        )

    def _extract_gold_annotations(
        self,
        doc: MedCATTrainerExportDocument
    ) -> list[GoldAnnotation]:
        """Extract validated gold annotations, supporting multi-CUI options."""
        gold_anns: list[GoldAnnotation] = []

        for ann in doc['annotations']:
            if not ann.get('validated', True):
                continue
            if ann.get('killed', False) or ann.get('deleted', False):
                continue

            # Support both single CUI and multiple acceptable CUIs.
            acceptable_cuis = ann.get('acceptable_cuis', ann['cui'])
            if isinstance(acceptable_cuis, list):
                cuis = acceptable_cuis
            else:
                cuis = [acceptable_cuis]

            # Filter to valid CUIs.
            valid_cuis: list[str] = [
                cui
                for cui in cuis
                if isinstance(cui, str)
                and self.filters.check_filters(cui)
            ]
            if valid_cuis:
                gold_anns.append({
                    'start': ann['start'],
                    'end': ann['end'],
                    'cuis': valid_cuis,  # List of acceptable CUIs
                    'cui': valid_cuis[0],  # For counting
                    'text': ann['value'],
                    'raw': ann
                })
        return gold_anns
    
    def _extract_predictions(
        self,
        predictions: list[MutableEntity],
        apply_filters: bool = True,
    ) -> list[PredictedAnnotation]:
        """Extract relevant info from predicted entities."""
        extracted: list[PredictedAnnotation] = []

        for ent in predictions:
            if apply_filters and not self.filters.check_filters(ent.cui):
                continue

            extracted.append({
                'start': ent.base.start_char_index,
                'end': ent.base.end_char_index,
                'cui': ent.cui,
                'text': ent.base.text,
                'confidence': float(ent.context_similarity),
                'raw': ent,
                'no_tokens': 1 if ent.id == UNTOKENIZABLE_ENTITY_ID else 0,
            })

        return extracted

    def _count_gold_annotations(
        self,
        gold_anns: list[GoldAnnotation],
        project_index: int,
        mode: MetricMode
    ) -> None:
        """Count gold annotations for a project and all-projects aggregate."""
        project_stats = self.stats.get_project_stats(project_index)
        aggregate_stats = self.stats.get_aggregate_stats()
        for project_stats in (project_stats, aggregate_stats):
            mode_stats = project_stats.get_mode(mode)
            if mode_stats is None:
                continue
            state = mode_stats.stats
            if mode == self.BUCKET_NER:
                key = "__NER__"
                state.cui_gold_counts[key] = (
                    state.cui_gold_counts.get(key, 0)
                    + len(gold_anns)
                )
                continue
            for gold in gold_anns:
                cui = gold["cui"]
                state.cui_gold_counts[cui] = (
                    state.cui_gold_counts.get(cui, 0)
                    + 1
                )
        
    def _record_tp(self, 
                   state: RawStats, 
                   gold: GoldAnnotation, 
                   pred: PredictedAnnotation) -> None:
        """Record a true positive."""
        cui = pred['cui']
        state.tp += 1
        state.cui_tp[cui] = state.cui_tp.get(cui, 0) + 1
        
        if cui not in state.examples['tp']:
            state.examples['tp'][cui] = []
        state.examples['tp'][cui].append({
            'gold_text': gold['text'],
            'pred_text': pred['text'],
            'cui': cui,
            'start': pred['start'],
            'confidence': pred['confidence']
        })

    def _record_fn(self, state: RawStats, gold: GoldAnnotation) -> None:
        """Record a false negative."""
        cui = gold['cui']
        state.fn += 1
        state.cui_fn[cui] = state.cui_fn.get(cui, 0) + 1
        
        if cui not in state.examples['fn']:
            state.examples['fn'][cui] = []
        state.examples['fn'][cui].append({
            'text': gold['text'],
            'acceptable_cuis': gold['cuis'],
            'start': gold['start']
        })
        
    def _record_fp(self, state: RawStats, pred: PredictedAnnotation) -> None:
        """Record a false positive."""
        cui = pred['cui']
        state.fp += 1
        state.cui_fp[cui] = state.cui_fp.get(cui, 0) + 1
        
        if cui not in state.examples['fp']:
            state.examples['fp'][cui] = []
        state.examples['fp'][cui].append({
            'text': pred['text'],
            'cui': cui,
            'start': pred['start'],
            'confidence': pred['confidence']
        })
            
    def _record_no_tokens(self, state: RawStats, pred: PredictedAnnotation) -> None:
        """Record a prediction with no tokens (ID -1000)."""
        # When there's an entity with no way for the tokenizer to parse it
        # (commonly, this means that it's a subtoken span i.e. mRBC -> RBC isn't viable)
        # There's no tokens, throwing an error at get_tokens.
        # Treat it as a gold-like false negative so the recorded payload matches
        # the expected annotation schema used by the rest of the scorer.
        gold: GoldAnnotation = {
            'start': pred['start'],
            'end': pred['end'],
            'cuis': [pred['cui']],
            'cui': pred['cui'],
            'text': pred['text'],
            'raw': pred['raw'],
        }
        cui = gold['cui']
        state.no_tokens += 1
        state.cui_no_tokens[cui] = state.cui_no_tokens.get(cui, 0) + 1
        self._record_fn(state, gold)
        
    def _find_matching_prediction(
        self,
        gold: GoldAnnotation,
        predictions: list[PredictedAnnotation],
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
        
    def _score_annotations(self, 
                           gold_anns: list[GoldAnnotation], 
                           pred_anns: list[PredictedAnnotation],
                           project_index: int, 
                           mode: MetricMode, 
                           filter_fp_by_cui: bool = True) -> None:
        # Track which predictions have been matched
        matched_preds: set[int] = set()
        aggregate_stats = self.stats.get_aggregate_stats()
        project_stats = self.stats.get_project_stats(project_index)
        all_projects_state = aggregate_stats.get_mode(mode)
        project_state = project_stats.get_mode(mode)
        
        if all_projects_state is None or project_state is None:
            return

        # this is a bit counter intuitive.
        # essentially if you're looking at the linking performance,
        # then there maybe entities with no tokens (due to spacy i.e
        # [m'RNA'] not being representated) So you have to check the
        # ner'd spans for linking performance.
        if mode == self.BUCKET_LINKING:
            for pred in pred_anns:
                if pred['no_tokens'] == 1:
                    self._record_no_tokens(all_projects_state.stats, pred)
                    self._record_no_tokens(project_state.stats, pred)

        # NOTE: All predictions where ID are -1000 are false positives.
        # this should only really happen on the linker testing, as it's a perfect
        # NER step which is trying to create tokenless entities.
        # Phase 1: Match gold annotations to predictions (find TPs and FNs)
        for gold in gold_anns:
            if not gold['cuis']:
                # No valid CUIs for this gold annotation, skip it
                continue
            match_idx = self._find_matching_prediction(
                gold, pred_anns, matched_preds)

            if match_idx is not None:
                # True Positive
                matched_preds.add(match_idx)
                pred = pred_anns[match_idx]
                self._record_tp(all_projects_state.stats, gold, pred)
                self._record_tp(project_state.stats, gold, pred)
            else:
                # False Negative
                self._record_fn(all_projects_state.stats, gold)
                self._record_fn(project_state.stats, gold)

        # Phase 2: Remaining predictions are False Positives
        for idx, pred in enumerate(pred_anns):
            if idx in matched_preds: 
                continue
            if filter_fp_by_cui and not self.filters.check_filters(pred['cui']): 
                continue
            self._record_fp(all_projects_state.stats, pred)
            self._record_fp(project_state.stats, pred)

    def _to_ner_views(self, 
                      gold_anns: list[GoldAnnotation], 
                      pred_anns: list[PredictedAnnotation]
                      ) -> tuple[list[GoldAnnotation], list[PredictedAnnotation]]:
        ner_cui = '__NER__'
        eval_pred_anns: list[PredictedAnnotation] = [
            {**pred, "cui": ner_cui}
            for pred in pred_anns
        ]

        eval_gold_anns: list[GoldAnnotation] = [
            {**gold, "cuis": [ner_cui], "cui": ner_cui}
            for gold in gold_anns
        ]
        return eval_gold_anns, eval_pred_anns
    
    def _build_character_sets(
        self,
        anns: list[PredictedAnnotation] | list[GoldAnnotation],
    ) -> dict[str, set[int]]:
        chars_by_cui = defaultdict(set)

        for ann in anns:
            start = int(ann['start'])
            end = int(ann['end'])
            cui = ann['cui']
            char_idxs = set(range(start, end))
            chars_by_cui[cui].update(char_idxs)


        return dict(chars_by_cui)
    
    def _character_cohen_kappa(
        self,
        gold_chars: set[int],
        pred_chars: set[int],
        document_length: int,
    ) -> float:
        """
        The voices in my chatbot told me this is faster than the 
        sklearn implementation, and it is also more memory efficient.
        
        Testing shows same metrics, and halving computation speed.
        """

        tp = len(gold_chars & pred_chars)
        fp = len(pred_chars - gold_chars)
        fn = len(gold_chars - pred_chars)
        tn = document_length - tp - fp - fn

        total = document_length

        if total == 0:
            return 1.0

        # Observed agreement
        po = (tp + tn) / total

        # Expected agreement
        gold_positive = tp + fn
        gold_negative = fp + tn

        pred_positive = tp + fp
        pred_negative = fn + tn

        pe = (
            (gold_positive * pred_positive)
            +
            (gold_negative * pred_negative)
        ) / (total * total)

        denominator = 1 - pe

        if denominator == 0:
            # Perfect agreement or no variation
            return 1.0

        return (po - pe) / denominator
    
    def _calculate_document_character_scores(
        self,
        gold_anns: list[GoldAnnotation],
        pred_anns: list[PredictedAnnotation],
        doc_length: int,
    ) -> tuple[dict[str, float], dict[str, float], dict[str, float]]:
        """Compute per-CUI character score components for one document."""
        gold_chars_by_cui = self._build_character_sets(gold_anns)
        pred_chars_by_cui = self._build_character_sets(pred_anns)

        # For standard IoU and Cohen's Kappa:
        # include CUIs appearing in either gold or prediction.
        all_cuis = set(gold_chars_by_cui) | set(pred_chars_by_cui)

        # For GIoU: Gold Label Intersection over Union,
        # we only evaluate CUIs that are present in labels.
        # only include CUIs present in gold.
        gold_cuis = set(gold_chars_by_cui)

        per_cui_ious: dict[str, float] = {}
        per_cui_gious: dict[str, float] = {}
        per_cui_kappas: dict[str, float] = {}

        for cui in all_cuis:
            gold_chars = gold_chars_by_cui.get(cui, set())
            pred_chars = pred_chars_by_cui.get(cui, set())

            intersection = gold_chars & pred_chars
            union = gold_chars | pred_chars

            # Character IoU
            iou = len(intersection) / len(union) if union else 1.0
            per_cui_ious[cui] = iou

            # Gold IoU / GIoU
            # Only evaluated for CUIs present in gold.
            # Prediction-only CUIs are ignored.
            if cui in gold_cuis:
                giou = len(intersection) / len(gold_chars)
                per_cui_gious[cui] = giou

            per_cui_kappas[cui] = self._character_cohen_kappa(
                gold_chars,
                pred_chars,
                doc_length,
            )

        return per_cui_ious, per_cui_gious, per_cui_kappas

    def _update_project_stats(
        self,
        project_state: ModeStats,
        all_project_state: ModeStats,
        per_cui_ious: dict[str, float],
        per_cui_gious: dict[str, float],
        per_cui_kappas: dict[str, float],
    ) -> None:
        """Apply a document's character metric values to the project state."""
        for cui, iou in per_cui_ious.items():
            project_state.stats.cui_iou[cui].append(iou)
            all_project_state.stats.cui_iou[cui].append(iou)

        for cui, giou in per_cui_gious.items():
            project_state.stats.cui_giou[cui].append(giou)
            all_project_state.stats.cui_giou[cui].append(giou)

        for cui, kappa in per_cui_kappas.items():
            project_state.stats.cui_cohen_k[cui].append(kappa)
            all_project_state.stats.cui_cohen_k[cui].append(kappa)

        # Average the per-CUI IoUs rather than merging character sets.
        # This preserves CUI identity.
        doc_iou = (
            sum(per_cui_ious.values()) / len(per_cui_ious)
            if per_cui_ious else 0.0
        )

        # Only gold CUIs contribute to GIoU, so we average over those.
        doc_giou = (
            sum(per_cui_gious.values()) / len(per_cui_gious)
            if per_cui_gious else 0.0
        )

        # cohen's kappa is averaged over all CUIs, including those only in predictions.
        doc_cohen_k = (
            sum(per_cui_kappas.values()) / len(per_cui_kappas)
            if per_cui_kappas else 1.0
        )

        project_state.stats.iou_sum += doc_iou
        all_project_state.stats.iou_sum += doc_iou

        project_state.stats.giou_sum += doc_giou
        all_project_state.stats.giou_sum += doc_giou

        project_state.stats.cohen_k_sum += doc_cohen_k
        all_project_state.stats.cohen_k_sum += doc_cohen_k

        project_state.stats.char_docs += 1
        all_project_state.stats.char_docs += 1

    def _score_character_annotations(self, 
                                     gold_anns: list[GoldAnnotation], 
                                     pred_anns: list[PredictedAnnotation],
                                     project_index: int, 
                                     mode: MetricMode, 
                                     doc_length: int) -> None:
        """
        Calculate:
        - Character Intersection over Union (IoU) for gold and predicted annotations.
        - Gold label Character Intersection over Union (IoU) for gold and 
        predicted annotations.
        - Cohen's Kappa for gold and predicted annotations.
        
        Cheat sheet of what we're generating:
        # iou = sum of document-level macro IoUs
        #     -> divide by number of documents
        # giou = sum of document-level macro GIoUs
        #     -> divide by number of documents
        # cohen_k = sum of document-level macro Kappas
        #         -> divide by number of documents
        # cui_iou[CUI] = sum of per-document IoU for that CUI
        #              -> divide by number of documents containing that CUI
        # cui_giou[CUI] = sum of per-document GIoU for that CUI
        #               -> divide by number of documents containing that CUI in gold
        # cui_cohen_k[CUI] = sum of per-document CUI-specific Kappa
        #                 -> divide by number of documents where the CUI is evaluated
        """
        aggregate_stats = self.stats.get_aggregate_stats()
        project_stats = self.stats.get_project_stats(project_index)
        all_project_state = aggregate_stats.get_mode(mode)
        project_state = project_stats.get_mode(mode)

        if project_state is None or all_project_state is None:
            return

        per_cui_ious, per_cui_gious, per_cui_kappas = (
            self._calculate_document_character_scores(
                gold_anns,
                pred_anns,
                doc_length,
            )
        )

        self._update_project_stats(
            project_state,
            all_project_state,
            per_cui_ious,
            per_cui_gious,
            per_cui_kappas,
        )

    def process_document(
        self,
        doc: MedCATTrainerExportDocument,
        project_index: int,
        predictions: list[MutableEntity],
        mode: MetricMode,
        calculate_ner_performance: bool = False,
    ) -> None:
        """
        Process a single document's annotations and predictions.

        Args:
            doc: Gold-standard annotated document
            predictions: Model's predicted entities
        """
        full_pipe_gold_anns = self._extract_gold_annotations(doc)
        full_pipe_pred_anns = self._extract_predictions(predictions)
        
        self._count_gold_annotations(full_pipe_gold_anns, project_index, mode)
        self._score_annotations(
            full_pipe_gold_anns, 
            full_pipe_pred_anns,
            project_index, 
            mode=mode,
            filter_fp_by_cui=True
        )
        self._score_character_annotations(
            full_pipe_gold_anns,
            full_pipe_pred_anns,
            project_index, 
            mode=mode, doc_length=len(doc['text'])
        )

        # This gets called in the full pipeline call, if ner performance is called.
        if calculate_ner_performance:
            ner_gold_anns, ner_pred_anns = self._to_ner_views(
                full_pipe_gold_anns, full_pipe_pred_anns)
            self._count_gold_annotations(ner_gold_anns, project_index,
                                        mode=self.BUCKET_NER)
            self._score_annotations(ner_gold_anns, ner_pred_anns,
                                    project_index, mode=self.BUCKET_NER,
                                    filter_fp_by_cui=False)
            self._score_character_annotations(
                ner_gold_anns, 
                ner_pred_anns,
                project_index, 
                mode=self.BUCKET_NER, 
                doc_length=len(doc['text'])
            )
        
    def process_project(self, project: MedCATTrainerExportProject,
                        project_index: int,
                        entity_getter: Callable[[str], list[MutableEntity]],
                        mode: MetricMode,
                        calculate_ner_performance: bool = False,
                        use_project_filters: bool = False,
                        extra_cui_filter: set[str] | None = None
                        ) -> None:
        """Process all documents in a project.
        
        Args:
            project: The project data containing documents and annotations.
            project_index: Index of the project in the export.
            entity_getter: Function to get predicted entities from text.
            mode: Evaluation mode (full, ner, linking).
            calculate_ner_performance: Whether to calculate NER performance.
            use_project_filters: Whether to apply project-specific filters.
            extra_cui_filter: Additional CUI filter to apply.
        """
        with project_filters(self.filters,
                             project,
                             extra_cui_filter,
                             use_project_filters):
            for doc in tqdm(project['documents'],
                            desc='Documents'):
                predictions = entity_getter(doc['text'])
                self.process_document(
                    doc,
                    project_index,
                    predictions,
                    mode=mode,
                    calculate_ner_performance=calculate_ner_performance,
                )

    def _get_linked_ents(self, cat: CAT, text: str) -> list[MutableEntity]:
        """Required for mypy cleanliness"""
        doc = cat(text)
        if doc is None:
            return []
        return doc.linked_ents

    def process_export(self, cat: CAT, export: MedCATTrainerExport,
                       mode: MetricMode,
                       calculate_ner_performance: bool = False,
                       use_project_filters: bool = False,
                       extra_cui_filter: set[str] | None = None,
                       filter_before_disamb: bool = False) -> None:
        """Process all projects in the export.
        
        Args:
            cat: The MedCAT CAT instance for entity linking.
            export: The MedCAT trainer export data.
            mode: Evaluation mode (full, ner, linking).
            calculate_ner_performance: Whether to calculate NER performance.
            use_project_filters: Whether to apply project-specific filters.
            extra_cui_filter: Additional CUI filter to apply.
            filter_before_disamb: Whether to filter entities before disambiguation.
        """
        if filter_before_disamb:
            cat.config.components.linking.filter_before_disamb = True
        for i, proj in tqdm(enumerate(export['projects']), desc='Projects'):
            self.process_project(
                proj, 
                i,
                lambda text: self._get_linked_ents(cat, text),
                mode=mode,
                calculate_ner_performance=calculate_ner_performance,
                use_project_filters=use_project_filters,
                extra_cui_filter=extra_cui_filter
            )
            
    @staticmethod
    def _compute_prf(tp: int, fp: int, fn: int, no_tokens: int) -> dict:
        """Compute precision, recall, F1."""
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
        no_tokens_ratio = no_tokens / (tp + fn) if (tp + fn) > 0 else 0.0
        return {
            'precision': prec, 
            'recall': rec, 
            'f1': f1, 
            'no_tokens': no_tokens, 
            'no_tokens_ratio': f'{no_tokens_ratio:.4f}'
        }

    def _get_cui_name(self, cui: str) -> str:
        """Get preferred name for CUI."""
        info = self.cui2info.get(cui)
        if info:
            return info.get('preferred_name') or list(info['names'])[0]
        return cui
    
    def _safe_mean(self, values):
        return sum(values) / len(values) if values else 0.0

    def _prepare_metrics(self, 
                         raw_stats: RawStats) -> tuple[OverallMetrics, dict[str, dict]]:
        """Prepare overall and per-CUI metrics from raw accumulated state."""
        # project metrics
        prf_values = self._compute_prf(
            raw_stats.tp,
            raw_stats.fp,
            raw_stats.fn,
            raw_stats.no_tokens,
        )

        if raw_stats.char_docs > 0:
            char_iou = raw_stats.iou_sum / raw_stats.char_docs
            char_giou = raw_stats.giou_sum / raw_stats.char_docs
            char_cohen_k = raw_stats.cohen_k_sum / raw_stats.char_docs
        else:
            char_iou = 0.0
            char_giou = 0.0
            char_cohen_k = 0.0

        overall = OverallMetrics(
            precision=prf_values['precision'],
            recall=prf_values['recall'],
            f1=prf_values['f1'],
            no_tokens=raw_stats.no_tokens,
            no_tokens_ratio=float(prf_values['no_tokens_ratio']),
            tp=raw_stats.tp,
            fp=raw_stats.fp,
            fn=raw_stats.fn,
            char_iou=char_iou,
            char_giou=char_giou,
            char_cohen_k=char_cohen_k,
        )

        # cui metrics
        all_cuis = (
            set(raw_stats.cui_tp)
            | set(raw_stats.cui_fp)
            | set(raw_stats.cui_fn)
            | set(raw_stats.cui_iou)
            | set(raw_stats.cui_giou)
            | set(raw_stats.cui_cohen_k)
        )

        per_cui: dict[str, dict] = {}

        for cui in all_cuis:
            tp = raw_stats.cui_tp.get(cui, 0)
            fp = raw_stats.cui_fp.get(cui, 0)
            fn = raw_stats.cui_fn.get(cui, 0)
            no_tokens = raw_stats.cui_no_tokens.get(cui, 0)

            cui_iou_scores = raw_stats.cui_iou.get(cui, [])
            cui_giou_scores = raw_stats.cui_giou.get(cui, [])
            cui_k_scores = raw_stats.cui_cohen_k.get(cui, [])

            per_cui[cui] = {
                "name": self._get_cui_name(cui),
                **self._compute_prf(
                    tp,
                    fp,
                    fn,
                    no_tokens,
                ),
                "tp": tp,
                "fp": fp,
                "fn": fn,
                "char_iou": self._safe_mean(cui_iou_scores),
                "char_giou": self._safe_mean(cui_giou_scores),
                "char_cohen_k": self._safe_mean(cui_k_scores),
                "char_iou_n": len(cui_iou_scores),
                "char_giou_n": len(cui_giou_scores),
                "char_cohen_k_n": len(cui_k_scores),
            }

        return overall, per_cui

    def compute_metrics(
        self,
        stats: ProjectStats,
        mode: MetricMode
    ) -> None:
        """Compute overall and per-CUI metrics for a given mode."""

        mode_stats = stats.get_mode(mode)
        if mode_stats is None:
            return
        overall, per_cui = self._prepare_metrics(mode_stats.stats)
        
        # Store computed metrics in the ModeStats object
        mode_stats.metrics = Metrics(
            overall=overall,
            per_cui={
                cui: CUIMetrics(**metrics)
                for cui, metrics in per_cui.items()
            },
        )
            
    def compute_all_metrics(self,
                            ner_performance: bool = True,
                            linking_performance: bool = True) -> None:
        """Compute metrics for all projects and the aggregate."""
        stats = self.stats.get_aggregate_stats()
        self.compute_metrics(stats, StatsCalculator.BUCKET_FULL)
        if ner_performance:
            self.compute_metrics(stats, StatsCalculator.BUCKET_NER)
        if linking_performance:
            self.compute_metrics(stats, StatsCalculator.BUCKET_LINKING)
        
        if self.num_projects > 1:
            for i in range(self.num_projects):
                stats = self.stats.get_project_stats(i)
                self.compute_metrics(stats, 
                                     StatsCalculator.BUCKET_FULL)
                if ner_performance:
                    self.compute_metrics(stats, 
                                         StatsCalculator.BUCKET_NER)
                if linking_performance:
                    self.compute_metrics(stats, 
                                         StatsCalculator.BUCKET_LINKING)
            
    # these 3 functions are just copied from previous, 
    # they get nice names for concepts
    def _empty(self, cui: str) -> CUIInfo:
        return get_new_cui_info(
            cui=cui, preferred_name=cui, names=set((cui, )))

    def _get_or_empty(self, cui: str) -> CUIInfo:
        return self.cui2info.get(cui, self._empty(cui))

    def _get_pref_name(self, cui: str) -> str:
        info = self._get_or_empty(cui)
        return info['preferred_name'] or list(info['names'])[0]
    
    def print_stats(self,
                    epoch: int,
                    mode_stats: ModeStats,
                    n_samples: int = 10,
                    stream: TextIO | None = None) -> None:
        """Finalise the report / metrics.

        This prints out the overall metrics and calculates per CUI metrics.

        Args:
            epoch (int): The number of the current epoch.
            mode_stats (ModeStats): The statistics for the current mode.
            n_samples (int): Number of entries to print for each section.
            stream (TextIO | None): Optional output stream to direct the report
                to instead of stdout.
        """
        if mode_stats.metrics is None:
            raise ValueError(
                "Metrics have not been computed yet. "
                "Call compute_metrics() first."
            )
        print("Epoch: {}, Prec: {}, Rec: {}, F1: {}\n".format(
                epoch,
                mode_stats.metrics.overall.precision,
                mode_stats.metrics.overall.recall,
                mode_stats.metrics.overall.f1
            ), file=stream
        )

        # Sort fns & prec
        fps = {k: v for k, v in sorted(mode_stats.metrics.per_cui.items(),
                key=lambda item: item[1].fp, reverse=True)}
        fns = {k: v for k, v in sorted(mode_stats.metrics.per_cui.items(),
                key=lambda item: item[1].fn, reverse=True)}
        tps = {k: v for k, v in sorted(mode_stats.metrics.per_cui.items(),
                key=lambda item: item[1].tp, reverse=True)}

        # Get top 5
        pr_fps = [(self._get_pref_name(cui),
                    cui, fps[cui]) for cui in list(fps.keys())[0:n_samples]]
        pr_fns = [(self._get_pref_name(cui),
                    cui, fns[cui]) for cui in list(fns.keys())[0:n_samples]]
        pr_tps = [(self._get_pref_name(cui),
                    cui, tps[cui]) for cui in list(tps.keys())[0:n_samples]]

        print("\n\nFalse Positives\n", file=stream)
        for one in pr_fps:
            print("{:70} - {:20} - {:10}".format(
                str(one[0])[0:69],
                str(one[1])[0:19],
                one[2].fp),
                file=stream
            )
        print("\n\nFalse Negatives\n", file=stream)
        for one in pr_fns:
            print("{:70} - {:20} - {:10}".format(
                str(one[0])[0:69],
                str(one[1])[0:19],
                one[2].fn),
                file=stream
            )
        print("\n\nTrue Positives\n", file=stream)
        for one in pr_tps:
            print("{:70} - {:20} - {:10}".format(
                str(one[0])[0:69],
                str(one[1])[0:19],
                one[2].tp),
                file=stream
            )
        print("*" * 110 + "\n", file=stream)

    def legacy_stats(self, mode_stats: "ModeStats") -> tuple[
        dict[str, int], dict[str, int], dict[str, int],
        dict[str, float], dict[str, float], dict[str, float],
        dict[str, int], dict
    ]:
        per_cui = mode_stats.metrics.per_cui if mode_stats.metrics is not None else {}
        to_return = (
            mode_stats.stats.cui_fp,
            mode_stats.stats.cui_fn,
            mode_stats.stats.cui_tp,
            {cui: metrics.precision for cui, metrics in per_cui.items()},
            {cui: metrics.recall for cui, metrics in per_cui.items()},
            {cui: metrics.f1 for cui, metrics in per_cui.items()},
            mode_stats.stats.cui_gold_counts,
            mode_stats.stats.examples,
        )
        return to_return

def get_stats_calculator(cat: CAT, 
                         data: MedCATTrainerExport,
                         epoch: int = 0,
                         use_project_filters: bool = False,
                         use_overlaps: bool = False,
                         ner_performance: bool = False,
                         linking_performance: bool = False,
                         extra_cui_filter: Optional[set[str]] = None,
                         do_print: bool = True,) -> StatsCalculator:
    calculator = StatsCalculator(
            filters=cat.config.components.linking.filters,
            cui2info=cat.cdb.cui2info,
            num_projects=len(data['projects']),
            ner_performance=ner_performance,
            linking_performance=linking_performance
    )
    # Always compute full pipeline metrics.
    # If ner is of interest then also compute NER metrics from the same pass.
    calculator.process_export(
        cat,
        data,
        mode=StatsCalculator.BUCKET_FULL,
        calculate_ner_performance=ner_performance,
        use_project_filters=use_project_filters,
        extra_cui_filter=extra_cui_filter,
    )
    # Optionally compute linking-only metrics with perfect upstream NER.
    if linking_performance:
        with dataset_aware_component(cat, CoreComponentType.ner, data):
            calculator.process_export(
                cat,
                data,
                mode=StatsCalculator.BUCKET_LINKING,
                use_project_filters=use_project_filters,
                extra_cui_filter=extra_cui_filter,
            )

    calculator.compute_all_metrics(ner_performance, linking_performance)
    
    if do_print:
        to_print = calculator.stats.all_projects.get_mode(StatsCalculator.BUCKET_FULL)
        if to_print is None:
            raise ValueError("No statistics available for the full pipeline mode.")
        calculator.print_stats(epoch, to_print)
    return calculator

def get_stats(cat: CAT, 
              data: MedCATTrainerExport,
              epoch: int = 0,
              use_project_filters: bool = False,
              use_overlaps: bool = False,
              ner_performance: bool = False,
              linking_performance: bool = False,
              extra_cui_filter: Optional[set[str]] = None,
              do_print: bool = True,) -> tuple[
        dict[str, int], dict[str, int], dict[str, int],
        dict[str, float], dict[str, float], dict[str, float],
        dict[str, int], dict
    ]:
    calculator = get_stats_calculator(
        cat=cat,
        data=data,
        epoch=epoch,
        use_project_filters=use_project_filters,
        use_overlaps=use_overlaps,
        ner_performance=ner_performance,
        linking_performance=linking_performance,
        extra_cui_filter=extra_cui_filter
    )
    full_stats = calculator.stats.all_projects.full_pipeline
    return calculator.legacy_stats(full_stats)