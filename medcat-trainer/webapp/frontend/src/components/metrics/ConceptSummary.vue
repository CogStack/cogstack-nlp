<template>
  <div class="concept-summary-panel">
    <div class="exclusion-toolbar">
      <label class="threshold-control" for="low-f1-threshold">
        <span>Low F1 below</span>
        <input id="low-f1-threshold"
               class="form-control threshold-input"
               type="number"
               min="0"
               max="1"
               step="0.05"
               v-model.number="f1Threshold">
      </label>
      <button type="button"
              class="btn btn-outline-danger"
              :disabled="lowPerformingCount === 0"
              @click="excludeLowPerformers">
        {{ excludeLowPerformersLabel }}
      </button>
      <span class="included-count">
        {{ includedItems.length }} of {{ sourceItems.length }} concepts in these scores
      </span>
    </div>

    <div v-if="hasExclusions" class="excluded-tray">
      <div class="excluded-tray-header">
        <span>
          {{ excludedItems.length }}
          {{ excludedItems.length === 1 ? 'concept' : 'concepts' }}
          excluded from these scores
        </span>
        <button type="button" class="btn btn-outline-primary btn-sm" @click="restoreAll">
          Restore all
        </button>
      </div>
      <div class="excluded-chips">
        <span v-for="item in excludedItems" :key="conceptKey(item)" class="excluded-chip">
          <span class="chip-name">{{ item.concept_name || item.cui }}</span>
          <span class="chip-f1">F1 {{ formatRatio(item.cui_f1) }}</span>
          <button type="button"
                  class="chip-restore"
                  :aria-label="`Restore ${item.concept_name || item.cui}`"
                  @click="restoreConcept(item)">
            <font-awesome-icon icon="undo"></font-awesome-icon>
          </button>
        </span>
      </div>
    </div>

    <v-row class="summary-row">
      <v-card v-for="metric in summaryMetrics" :key="metric.key" class="summary-card">
        <v-card-title>{{ metric.label }}</v-card-title>
        <v-card-text>
          <div class="metric-value">{{ formatPercent(metric.current) }}</div>
          <div v-if="hasExclusions" class="metric-delta" :class="deltaClass(metric.delta)">
            <span v-if="metric.delta !== null">{{ formatDelta(metric.delta) }}</span>
            <span class="metric-baseline">full set {{ formatPercent(metric.baseline) }}</span>
          </div>
        </v-card-text>
      </v-card>
    </v-row>

    <v-data-table class="concept-summary-table"
                  :items="includedItems"
                  :headers="headers"
                  density="compact"
                  v-model:sort-by="sortBy"
                  :row-props="rowProps"
                  hide-default-footer
                  :items-per-page="-1">
      <template #header.concept>
        <div>Concept</div>
        <v-tooltip></v-tooltip>
      </template>
      <template #header.concept_count>
        Concept Count
        <v-tooltip activator="parent">Number of occurrences across the projects</v-tooltip>
      </template>
      <template #header.variations>
        # Vars
        <v-tooltip activator="parent">The count of unique variations for a concept</v-tooltip>
      </template>
      <template #header.variation_values>
        Variations
        <v-tooltip activator="parent">The unique set of variations for a concept</v-tooltip>
      </template>
      <template #header.count_variations_ratio>
        Variations Ratio
        <v-tooltip activator="parent">The ratio of number of annotations and the number of variations of a concept</v-tooltip>
      </template>
      <template #header>
        CUI
        <v-tooltip activator="parent">The Concept Unique Identifier</v-tooltip>
      </template>
      <template #header.cui_f1>
        F1
        <v-tooltip activator="parent">The harmonic mean of the recall and precision scores</v-tooltip>
      </template>
      <template #header.cui_prec>
        Prec.
        <v-tooltip activator="parent">The precision scores of a concept</v-tooltip>
      </template>
      <template #header.cui_rec>
        Rec
        <v-tooltip activator="parent">The recall scores of a concept</v-tooltip>
      </template>
      <template #header.tps>
        TPs
        <v-tooltip activator="parent">True positives - concept examples that are annotated and predicted by the model</v-tooltip>
      </template>
      <template #header.fns>
        FNs
        <v-tooltip activator="parent">False negatives - concept examples that annotated but not predicted by the model</v-tooltip>
      </template>
      <template #header.fps>
        FPs
        <v-tooltip activator="parent">False positives - concept examples that are predicted but not annotated</v-tooltip>
      </template>
      <template #header.exclude>
        Exclude
        <v-tooltip activator="parent">Remove this concept from the scores above</v-tooltip>
      </template>
      <template #item.concept_name="{ item }">
        <span class="concept-name" :title="item.concept_name">{{ item.concept_name }}</span>
      </template>
      <template #item.variation_values="{ item }">
        <v-tooltip location="top" max-width="420" :disabled="variationList(item).length === 0">
          <template #activator="{ props }">
            <span v-bind="props" class="variation-values">{{ variationPreview(item) }}</span>
          </template>
          <span>{{ variationTooltip(item) }}</span>
        </v-tooltip>
      </template>
      <template #item.cui_f1="{ item }">
        <div class="perf-progress">
          <v-progress-linear
              v-model="item.cui_f1"
              color="#32AB60"
              background-color="#46B480"
              height="16"
              :max="1.0">
            <span :class="{'good-perf': item.cui_f1 > 0.4}">{{item.cui_f1.toFixed(2)}}</span>
          </v-progress-linear>
        </div>
      </template>
      <template #item.cui_rec="{ item }">
        <div class="perf-progress">
          <v-progress-linear
              v-model="item.cui_rec"
              color="#32AB60"
              background-color="#46B480"
              height="16"
              :max="1.0">
            <span :class="{'good-perf': item.cui_rec > 0.4}">{{item.cui_rec.toFixed(2)}}</span>
          </v-progress-linear>
        </div>
      </template>
      <template #item.cui_prec="{ item }">
        <div class="perf-progress">
          <v-progress-linear
              v-model="item.cui_prec"
              color="#32AB60"
              background-color="#46B480"
              height="16"
              :max="1.0">
            <span :class="{'good-perf': item.cui_prec > 0.4}">{{item.cui_prec.toFixed(2)}}</span>
          </v-progress-linear>
        </div>
      </template>
      <template #item.tps="{ item }">
        <button type="button" class="btn res-btn tp-count" :disabled="countValue(item, 'tps') === 0"
                @click.stop="openExamples('tp_examples', item)">
          {{ countValue(item, 'tps') }}
        </button>
      </template>
      <template #item.fns="{ item }">
        <button type="button" class="btn res-btn fn-count" :disabled="countValue(item, 'fns') === 0"
                @click.stop="openExamples('fn_examples', item)">
          {{ countValue(item, 'fns') }}
        </button>
      </template>
      <template #item.fps="{ item }">
        <button type="button" class="btn res-btn fp-count" :disabled="countValue(item, 'fps') === 0"
                @click.stop="openExamples('fp_examples', item)">
          {{ countValue(item, 'fps') }}
        </button>
      </template>
      <template #item.exclude="{ item }">
        <button type="button"
                class="btn btn-outline-danger res-btn"
                :aria-label="`Exclude ${item.concept_name || item.cui}`"
                @click="excludeConcept(item)">
          <font-awesome-icon icon="times"></font-awesome-icon>
        </button>
      </template>
    </v-data-table>

    <teleport to="body">
    <modal v-if="showModal" :closable="true" @modal:close="clearModalData" class="examples-modal">
      <template #header>
        <h3>{{ modalData.title }}</h3>
      </template>
      <template #body>
        <div>
          <div v-if="modalData.type === 'fp'">
            <p>False positive model predictions can be the result of:</p>
            <ul>
              <li>Alternative model predictions that are overlapping with other concepts</li>
              <li>Genuine missed annotations by an annotator.</li>
            </ul>
            <p>Clicking on these annotations will not highlight this annotation as it doesn't exist in the
              dataset </p>
          </div>
          <div v-if="modalData.type === 'fn'">
            <p>False negative model predictions can be the result of:</p>
            <ul>
              <li>A model mistake that marked an annotation 'correct' where it should be incorrect</li>
              <li>An annotator mistake that marked an annotation 'correct' where it should be incorrect</li>
            </ul>
          </div>
          <div v-if="modalData.type === 'tp'">
            <p>True positive model predictions are annotations that were correctly predicted by the model.</p>
          </div>
          <table class="table table-hover">
            <thead>
            <tr>
              <th>Doc Name</th>
              <th>CUI</th>
              <th>Value</th>
              <th>Accuracy</th>
              <th>Text</th>
            </tr>
            </thead>
            <tbody>
            <anno-result v-for="(res, key) of modalData.results" :key="key" :result="res"
                         :type="modalData.type" :doc-text="textFromAnno(res)"></anno-result>
            </tbody>
          </table>
        </div>
      </template>
    </modal>
    </teleport>
  </div>
</template>

<script>
import AnnoResult from '@/components/anns/AnnoResult.vue'
import Modal from '@/components/common/Modal.vue'
import { documentTextForExample } from '@/components/metrics/exampleFields'

const VARIATION_PREVIEW_COUNT = 2
const VARIATION_TERM_LIMIT = 28

const SUMMARY_METRICS = [
  { key: 'macro-f1', label: 'Macro F1', kind: 'macro', metric: 'cui_f1' },
  { key: 'macro-prec', label: 'Macro Precision', kind: 'macro', metric: 'cui_prec' },
  { key: 'macro-rec', label: 'Macro Recall', kind: 'macro', metric: 'cui_rec' },
  { key: 'micro-f1', label: 'Micro F1', kind: 'micro', metric: 'cui_f1' },
  { key: 'micro-prec', label: 'Micro Precision', kind: 'micro', metric: 'cui_prec' },
  { key: 'micro-rec', label: 'Micro Recall', kind: 'micro', metric: 'cui_rec' }
]

export default {
  name: 'ConceptSummary',
  components: {
    AnnoResult,
    Modal
  },
  props: {
    items: {
      type: Array,
      required: true
    },
    docs2text: {
      type: Object,
      required: true
    }
  },
  data() {
    return {
      showModal: false,
      modalData: {
        results: null,
        title: null,
        type: null
      },
      f1Threshold: 0.7,
      excludedKeys: [],
      sortBy: [{ key: 'cui_f1', order: 'asc' }],
      headers: [
          { key: 'concept_name', value: 'concept_name', title: 'Concept Name'},
          { key: 'concept_count', value: 'concept_count' },
          { key: 'variations', value: 'variations' },
          { key: 'variation_values', value: 'variation_values', title: ''},
          { key: 'count_variations_ratio', value: 'count_variations_ratio', title: 'Variation Ratio' },
          { key: 'cui', value: 'cui', title: 'CUI' },
          { key: 'cui_f1', value: 'cui_f1', title: 'F1' },
          { key: 'cui_prec', value: 'cui_prec', title: 'Prec.' },
          { key: 'cui_rec', value: 'cui_rec', title: 'Rec.' },
          { key: 'tps', value: 'tps', title: 'TPs' },
          { key: 'fns', value: 'fns', title: 'FNs' },
          { key: 'fps', value: 'fps', title: 'FPs' },
          { key: 'exclude', value: 'exclude', title: 'Exclude', sortable: false }
        ]
    }
  },
  computed: {
    sourceItems() {
      return this.items || []
    },
    includedItems() {
      return this.sourceItems.filter(item => !this.excludedKeys.includes(this.conceptKey(item)))
    },
    excludedItems() {
      return this.sourceItems.filter(item => this.excludedKeys.includes(this.conceptKey(item)))
    },
    hasExclusions() {
      return this.excludedItems.length > 0
    },
    lowPerformingItems() {
      return this.includedItems.filter(item => this.isLowPerforming(item))
    },
    lowPerformingCount() {
      return this.lowPerformingItems.length
    },
    excludeLowPerformersLabel() {
      if (this.lowPerformingCount === 0) {
        return 'No concepts below this F1'
      }
      if (this.lowPerformingCount === 1) {
        return 'Exclude 1 low performer'
      }
      return `Exclude ${this.lowPerformingCount} low performers`
    },
    summaryMetrics() {
      return SUMMARY_METRICS.map(definition => {
        const current = this.scoreFor(this.includedItems, definition.kind, definition.metric)
        const baseline = this.scoreFor(this.sourceItems, definition.kind, definition.metric)
        const delta = current === null || baseline === null ? null : current - baseline
        return { ...definition, current, baseline, delta }
      })
    }
  },
  watch: {
    items() {
      this.excludedKeys = []
    },
    f1Threshold(value) {
      if (!Number.isFinite(value)) {
        this.f1Threshold = 0.7
        return
      }
      const clamped = Math.min(1, Math.max(0, Math.round(value * 100) / 100))
      if (clamped !== value) {
        this.f1Threshold = clamped
      }
    }
  },
  methods: {
    conceptKey(item) {
      return `${item.cui || ''}::${item.concept_name || ''}`
    },
    variationList(item) {
      const values = item.value
      if (Array.isArray(values)) {
        return values.map(value => String(value)).filter(value => value.length > 0)
      }
      if (values === null || values === undefined || values === '') {
        return []
      }
      return [String(values)]
    },
    shortVariation(value) {
      if (value.length <= VARIATION_TERM_LIMIT) {
        return value
      }
      return `${value.slice(0, VARIATION_TERM_LIMIT - 1)}…`
    },
    variationPreview(item) {
      const values = this.variationList(item)
      if (!values.length) {
        return ''
      }
      const shown = values.slice(0, VARIATION_PREVIEW_COUNT).map(value => this.shortVariation(value))
      const hidden = values.length - shown.length
      if (hidden > 0) {
        return `${shown.join(', ')} +${hidden}`
      }
      return shown.join(', ')
    },
    variationTooltip(item) {
      return this.variationList(item).join(', ')
    },
    isLowPerforming(item) {
      const f1 = Number(item.cui_f1)
      return Number.isFinite(f1) && f1 < this.f1Threshold
    },
    excludeConcept(item) {
      const key = this.conceptKey(item)
      if (!this.excludedKeys.includes(key)) {
        this.excludedKeys = [...this.excludedKeys, key]
      }
    },
    excludeLowPerformers() {
      const keys = this.lowPerformingItems.map(item => this.conceptKey(item))
      this.excludedKeys = [...this.excludedKeys, ...keys]
    },
    restoreConcept(item) {
      const key = this.conceptKey(item)
      this.excludedKeys = this.excludedKeys.filter(excluded => excluded !== key)
    },
    restoreAll() {
      this.excludedKeys = []
    },
    rowProps({ item }) {
      if (this.isLowPerforming(item)) {
        return { class: 'low-perf-row' }
      }
      return {}
    },
    scoreFor(items, kind, metric) {
      if (this.sourceItems.length === 0) {
        return 0
      }
      if (!items.length) {
        return null
      }
      if (kind === 'macro') {
        return this.macroAverage(items, metric)
      }
      return this.microAverage(items)[metric]
    },
    macroAverage(items, metric) {
      const values = items
        .map(item => Number(item[metric]))
        .filter(value => Number.isFinite(value))
      if (!values.length) {
        return null
      }
      return values.reduce((acc, value) => acc + value, 0) / values.length
    },
    microAverage(items) {
      let totalTPs = 0
      let totalFPs = 0
      let totalFNs = 0

      items.forEach(item => {
        totalTPs += Number(item.tps) || 0
        totalFPs += Number(item.fps) || 0
        totalFNs += Number(item.fns) || 0
      })

      const precision = this.ratio(totalTPs, totalTPs + totalFPs)
      const recall = this.ratio(totalTPs, totalTPs + totalFNs)
      let f1 = null
      if (precision !== null && recall !== null && (precision + recall) > 0) {
        f1 = (2 * precision * recall) / (precision + recall)
      } else if (precision === 0 && recall === 0) {
        f1 = 0
      }

      return {
        cui_prec: precision,
        cui_rec: recall,
        cui_f1: f1
      }
    },
    ratio(numerator, denominator) {
      if (!denominator) {
        return null
      }
      const value = numerator / denominator
      return Number.isFinite(value) ? value : null
    },
    formatPercent(value) {
      if (value === null || !Number.isFinite(value)) {
        return '—'
      }
      return `${(value * 100).toFixed(1)}%`
    },
    formatDelta(delta) {
      const points = delta * 100
      const sign = points > 0 ? '+' : ''
      return `${sign}${points.toFixed(1)} pts`
    },
    formatRatio(value) {
      const numeric = Number(value)
      if (!Number.isFinite(numeric)) {
        return '—'
      }
      return numeric.toFixed(2)
    },
    deltaClass(delta) {
      if (delta === null || !Number.isFinite(delta) || Math.abs(delta) < 0.0005) {
        return 'flat'
      }
      return delta > 0 ? 'up' : 'down'
    },
    countValue (item, field) {
      const row = this.exampleRow(item)
      const value = Number(row && row[field])
      return Number.isFinite(value) ? value : 0
    },
    exampleRow (item) {
      // v-data-table may pass its internal wrapper ({ type, raw }) rather than the source row.
      if (item && item.type === 'item' && item.raw) return item.raw
      return item
    },
    exampleList (row, exampleType) {
      const direct = row && row[exampleType]
      if (Array.isArray(direct)) return direct
      if (direct && typeof direct === 'object') return [direct]

      const items = Array.isArray(this.items) ? this.items : []
      // Identity lookup fails when the table hands back a copy of the row.
      const idx = row ? items.indexOf(row) : -1
      if (idx !== -1 && Array.isArray(items[idx][exampleType])) return items[idx][exampleType]

      const match = items.find(candidate =>
        candidate && row && candidate.cui === row.cui &&
        (row.concept_name == null || candidate.concept_name === row.concept_name)
      )
      const matched = match && match[exampleType]
      if (Array.isArray(matched)) return matched
      if (matched && typeof matched === 'object') return [matched]
      return []
    },
    openExamples(exampleType, item) {
      const row = this.exampleRow(item) || {}
      const label = row.concept_name || 'Concept'
      const cui = row.cui || ''
      if (exampleType === 'tp_examples') {
        this.modalData.title = `${label} (${cui}) - True Positive Model Predictions`
        this.modalData.type = 'tp'
      } else if (exampleType === 'fp_examples') {
        this.modalData.title = `${label} (${cui}) - False Positive Model Predictions`
        this.modalData.type = 'fp'
      } else {
        this.modalData.title = `${label} (${cui}) - False Negative Model Predictions`
        this.modalData.type = 'fn'
      }
      this.modalData.results = this.exampleList(row, exampleType)
      // Open after this click finishes so the new dialog mask cannot receive it and close immediately.
      this.$nextTick(() => {
        this.showModal = true
      })
    },
    clearModalData() {
      this.modalData = {
        results: null,
        title: null,
        type: null
      }
      this.showModal = false
    },
    textFromAnno(anno) {
      return documentTextForExample(this.docs2text, anno)
    }
  }
}
</script>

<style>
.good-perf {
  color: #E5EBEA;
}

.perf-progress {
  width: 54px;
}

.res-btn {
  height: 20px;
  padding: 0 8px !important;
  border: 0 !important;
  background-color: transparent;
  font-size: 12px;
  line-height: 20px;
}

button.res-btn.tp-count {
  opacity: 0.3;
  /* color: var(--success); */
}

button.res-btn.fn-count {
  opacity: 0.3;
  /* color: var(--warning); */
}

button.res-btn.fp-count {
  opacity: 0.3;
  /* color: var(--danger); */
}

button.res-btn.tp-count:not(:disabled) {
  opacity: 1;
  color: var(--success);
}

button.res-btn.fn-count:not(:disabled) {
  opacity: 1;
  color: var(--warning);
}

button.res-btn.fp-count:not(:disabled) {
  opacity: 1;
  color: var(--danger);
}

button.res-btn.tp-count:not(:disabled):hover {
  color: var(--bs-white);
  background-color: var(--success);
}

button.res-btn.fn-count:not(:disabled):hover {
  color: var(--bs-white);
  background-color: var(--warning);
}

button.res-btn.fp-count:not(:disabled):hover {
  color: var(--bs-white);
  background-color: var(--danger);
}

.v-card {
  max-height: 80vh;
  overflow-y: auto;
}

.examples-modal .modal-container {
  width: 90%;
}
</style>

<style scoped lang="scss">
.exclusion-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  padding: 8px 4px 0;
}

.threshold-control {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  color: $text;
}

.threshold-input {
  width: 88px;
  height: 32px;
  padding: 2px 8px;
}

.included-count {
  margin-left: auto;
  color: $color-5;
  font-size: 0.9rem;
}

.excluded-tray {
  margin: 10px 4px 0;
  padding: 8px 10px;
  border: 1px solid rgba($danger, 0.35);
  border-radius: 4px;
  background: rgba($danger, 0.06);
}

.excluded-tray-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.excluded-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}

.excluded-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 2px 6px 2px 8px;
  border-radius: 12px;
  background: #fff;
  border: 1px solid $borders;
  font-size: 0.85rem;
}

.chip-f1 {
  color: $danger;
  font-variant-numeric: tabular-nums;
}

.chip-restore {
  border: 0;
  background: transparent;
  color: $text;
  padding: 0 2px;
  line-height: 1;

  &:hover {
    color: $primary;
  }
}

.metric-value {
  font-variant-numeric: tabular-nums;
}

.metric-delta {
  margin-top: 4px;
  font-size: 0.8rem;
  font-weight: 600;
  line-height: 1.2;

  &.up {
    color: $success;
  }

  &.down {
    color: $danger;
  }

  &.flat {
    color: $color-5;
  }
}

.metric-baseline {
  display: block;
  font-weight: 500;
  color: $color-5;
}

.concept-name,
.variation-values {
  display: inline-block;
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  vertical-align: middle;
  line-height: 1.2;
}

.variation-values {
  max-width: 200px;
}

.concept-summary-table.v-table,
.concept-summary-table :deep(.v-table) {
  --v-table-row-height: 32px;
}

.concept-summary-table {

  :deep(.v-table__wrapper > table > thead > tr > th) {
    padding: 4px 8px !important;
    white-space: nowrap;
    font-size: 0.8rem;
  }

  :deep(.v-table__wrapper > table > tbody > tr > td) {
    padding: 1px 8px !important;
    vertical-align: middle;
  }

  :deep(.perf-progress) {
    width: 54px;
  }

  :deep(.v-progress-linear) {
    font-size: 11px;
  }

  :deep(.res-btn) {
    height: 20px;
    padding: 0 8px !important;
    font-size: 12px;
    line-height: 20px;
  }
}

:deep(.v-table > .v-table__wrapper > table > tbody > tr.low-perf-row) {
  background-color: rgba($danger, 0.08);
}
</style>
