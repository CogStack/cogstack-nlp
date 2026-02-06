<template>
  <div v-if="hasMetaAnnotations" class="meta-annotations-section">
    <div class="meta-annotations-title">Meta Annotations</div>
    <div v-for="(metaAnn, index) in metaAnnotations" :key="index" class="meta-annotation-task">
      <div class="task-name">
        <span class="task-label">{{ metaAnn.task }}:</span>
        <span class="task-value">{{ metaAnn.value }}</span>
        <span v-if="metaAnn.confidence !== null && metaAnn.confidence !== undefined" class="predicted-conf">
          score: {{ metaAnn.confidence.toFixed(3) }}
        </span>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'MetaAnnotationsSummary',
  props: {
    metaAnnotations: {
      type: Array,
      default: () => []
    }
  },
  computed: {
    hasMetaAnnotations () {
      return Array.isArray(this.metaAnnotations) && this.metaAnnotations.length > 0
    }
  }
}
</script>

<style scoped lang="scss">
.meta-annotations-section {
  margin-top: 20px;
  padding-top: 20px;
  border-top: 2px solid rgba(0, 0, 0, 0.1);
  display: flex;
  flex-direction: column;
}

.meta-annotations-title {
  display: block;
  font-weight: 600;
  margin: 0 0 6px 0;
  padding: 5px 15px;
  font-size: 14pt;
  line-height: 1.5;
  color: black;
  box-shadow: 0 5px 5px -5px rgba(0, 0, 0, 0.2);
  text-align: left;
  width: 100%;
}

.meta-annotation-task {
  margin-bottom: 10px;
  width: 100%;
}

.task-name {
  font-size: 16px;
  padding: 10px 15px 5px 15px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
}

.task-label {
  text-align: left;
  flex-shrink: 0;
}

.task-value {
  color: #0072CE; // NHS Bright Blue (primary)
  font-weight: 500;
  text-align: left;
  flex: 1;
  display: flex;
  justify-content: left;
}

.predicted-conf {
  font-size: 9pt;
  display: inline-block;
  text-align: right;
  flex-shrink: 0;
}
</style>
