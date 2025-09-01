<template>
  <div>
    <v-row class="summary-row">
      <v-card class="summary-card">
        <v-card-title>Macro F1</v-card-title>
        <v-card-text>{{ calculateMacroAverage('cui_f1') }}%</v-card-text>
      </v-card>

      <v-card class="summary-card">
        <v-card-title>Macro Precision</v-card-title>
        <v-card-text>{{ calculateMacroAverage('cui_prec') }}%</v-card-text>
      </v-card>

      <v-card class="summary-card">
        <v-card-title>Macro Recall</v-card-title>
        <v-card-text>{{ calculateMacroAverage('cui_rec') }}%</v-card-text>
      </v-card>

      <v-card class="summary-card">
        <v-card-title>Micro F1</v-card-title>
        <v-card-text>{{ calculateMicroAverage('cui_f1') }}%</v-card-text>
      </v-card>

      <v-card class="summary-card">
        <v-card-title>Micro Precision</v-card-title>
        <v-card-text>{{ calculateMicroAverage('cui_prec') }}%</v-card-text>
      </v-card>

      <v-card class="summary-card">
        <v-card-title>Micro Recall</v-card-title>
        <v-card-text>{{ calculateMicroAverage('cui_rec') }}%</v-card-text>
      </v-card>
    </v-row>

    <v-data-table :items="items"
                  :headers="headers"
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
      <template #item.variation_values="{ item }">
        <div>{{ item.value.join(', ') }}</div>
      </template>
      <template #item.cui_f1="{ item }">
        <div class="perf-progress">
          <v-progress-linear
              v-model="item.cui_f1"
              color="#32AB60"
              background-color="#46B480"
              height="30px"
              :max="1.0">
            <span :class="{'good-perf': item.cui_f1 > 0.4}">{{item.cui_f1.toFixed(1)}}</span>
          </v-progress-linear>
        </div>
      </template>
      <template #item.cui_rec="{ item }">
        <div class="perf-progress">
          <v-progress-linear
              v-model="item.cui_rec"
              color="#32AB60"
              background-color="#46B480"
              height="30px"
              :max="1.0">
            <span :class="{'good-perf': item.cui_rec > 0.4}">{{item.cui_rec.toFixed(1)}}</span>
          </v-progress-linear>
        </div>
      </template>
      <template #item.cui_prec="{ item }">
        <div class="perf-progress">
          <v-progress-linear
              v-model="item.cui_prec"
              color="#32AB60"
              background-color="#46B480"
              height="30px"
              :max="1.0">
            <span :class="{'good-perf': item.cui_prec > 0.4}">{{item.cui_prec.toFixed(1)}}</span>
          </v-progress-linear>
        </div>
      </template>
      <template #item.tps="{ item }">
        <button class="btn btn-outline-success res-btn" :disabled="item.tps === 0"
                @click="openExamples('tp_examples', item)">
          {{ item.tps }}
        </button>
      </template>
      <template #item.fns="{ item }">
        <button class="btn btn-outline-warning res-btn" :disabled="item.fns === 0"
                @click="openExamples('fn_examples', item)">
          {{ item.fns }}
        </button>
      </template>
      <template #item.fps="{ item }">
        <button class="btn btn-outline-danger res-btn" :disabled="item.fps === 0"
                @click="openExamples('fp_examples', item)">
          {{ item.fps }}
        </button>
      </template>
    </v-data-table>

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
  </div>
</template>

<script>
import AnnoResult from '@/components/anns/AnnoResult.vue'
import Modal from '@/components/common/Modal.vue'

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
      headers: [
          {value: 'concept_name', title: 'Concept Name'},
          { value: 'concept_count' },
          { value: 'variations' },
          { value: 'variation_values', title: ''},
          { value: 'count_variations_ratio', title: 'Variation Ratio' },
          { value: 'cui', title: 'CUI' },
          { value: 'cui_f1', title: 'F1' },
          { value: 'cui_prec', title: 'Prec.' },
          { value: 'cui_rec', title: 'Rec.' },
          { value: 'tps', title: 'TPs' },
          { value: 'fns', title: 'FNs' },
          { value: 'fps', title: 'FPs' }
        ]
    }
  },
  methods: {
    calculateMacroAverage(metric) {
      if (!this.items || this.items.length === 0) {
        return '0.0'
      }
      const sum = this.items.reduce((acc, item) => acc + item[metric], 0)
      return ((sum / this.items.length) * 100).toFixed(1)
    },
    calculateMicroAverage(metric) {
      if (!this.items || this.items.length === 0) {
        return '0.0'
      }
      let totalTPs = 0
      let totalFPs = 0
      let totalFNs = 0

      this.items.forEach(item => {
        totalTPs += item.tps
        totalFPs += item.fps
        totalFNs += item.fns
      })

      let precision = totalTPs / (totalTPs + totalFPs)
      let recall = totalTPs / (totalTPs + totalFNs)
      let f1 = 2 * (precision * recall) / (precision + recall)

      switch(metric) {
        case 'cui_prec':
          return (precision * 100).toFixed(1)
        case 'cui_rec':
          return (recall * 100).toFixed(1)
        case 'cui_f1':
          return (f1 * 100).toFixed(1)
        default:
          return '0.0'
      }
    },
    openExamples(exampleType, item) {
      if (exampleType === 'tp_examples') {
        this.modalData.title = `${item.concept_name} (${item.cui}) - True Positive Model Predictions`
        this.modalData.type = 'tp'
      } else if (exampleType === 'fp_examples') {
        this.modalData.title = `${item.concept_name} (${item.cui}) - False Positive Model Predictions`
        this.modalData.type = 'fp'
      } else {
        this.modalData.title = `${item.concept_name} (${item.cui}) - False Negative Model Predictions`
        this.modalData.type = 'fn'
      }
      const idx = this.items.indexOf(item)
      this.modalData.results = this.items[idx][exampleType]
      this.showModal = true
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
      const docId = anno['document id']
      return this.docs2text[docId]
    }
  }
}
</script>

<style>
.good-perf {
  color: #E5EBEA;
}

.perf-progress {
  width: 50px;
}

.res-btn {
  height: 25px;
  padding: 3px 10px !important;
  border: 0 !important;
}

.res-btn:hover {
  color: white !important;
}

.v-card {
  max-height: 80vh;
  overflow-y: auto;
}

.examples-modal .modal-container {
  width: 90%;
}
</style>