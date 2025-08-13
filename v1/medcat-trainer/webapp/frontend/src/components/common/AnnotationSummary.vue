<template>
  <div class="summary">
    <table class="table table-condensed table-hover">
      <thead>
        <tr>
          <th>Annotated Text</th>
          <th>Concept ID</th>
          <th>Concept Name</th>
          <th v-if="showInfoCol('icd10')">ICD-10</th>
          <th v-if="showInfoCol('opcs4')">OPCS-4</th>
          <th v-for="task in tasks" :key="task.id">{{task.name}}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="concept in annos" :key="concept.id" class="summary-body" @click="selectConcept(concept)">
          <td>
            <span>{{leftContext(concept)}}</span>
            <span :class="highlightClass(concept)">{{concept.value}}</span>
            <span>{{rightContext(concept)}}</span>
          </td>
          <td>{{concept.cui}}</td>
          <td>{{concept.pretty_name}}</td>
          <td v-if="showInfoCol('icd10')" class="cui-info">
            <div v-for="code of concept.icd10" :key="code.code">{{`${code.code} | ${code.desc}`}}</div>
          </td>
          <td v-if="showInfoCol('opcs4')" class="cui-info">
          </td>
          <td v-for="task in metaAnnos[concept.id]" :key="task.id">
            <span>{{taskMaps[task.id][task.value]}}</span>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script>
import SummaryMixin from '@/mixins/SummaryMixin'

export default {
  name: 'AnnotationSummary',
  mixins: [SummaryMixin],
  props: {
    annos: Array
  },
  created () {
    this.enrichSummary(this.annos)
  }
}
</script>

<style scoped lang="scss">

.summary {
  height: 550px;
  overflow-y: auto;

  table td {
    cursor: pointer;
  }
}

.cui-info {
  white-space: pre-wrap;
}

.highlight-task-new {
  @extend .highlight-task-0;
  &::after {
    content: "*";
  }
}
</style>
