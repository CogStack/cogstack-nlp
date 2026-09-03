<template>
  <div class="meta-annotation-task">
    <div class="task-header">
      <div class="task-name">{{task.name}}</div>
      <div class="task-description">{{task.description}}</div>
    </div>
    <div class="task-values-container">
      <button class="btn btn-outline-primary task-value"
              :class="optionStyle(option)"
              v-for="option of task.options" :key="option.id"
              @click="selectTaskValue(option)">{{option.name}}
        <span class="predicted-conf" v-if="task.predicted_value === option.id">score:{{task.acc.toFixed(3)}}</span>
      </button>
    </div>
  </div>
</template>

<script>
export default {
  name: 'MetaAnnotationTask',
  props: {
    task: Object
  },
  emits: [
    'select:metaAnno'
  ],
  methods: {
    selectTaskValue (option) {
      this.$emit('select:metaAnno', this.task, option)
      this.$forceUpdate()
    },
    optionStyle (option) {
      if (this.task.value === option.id &&
        (this.task.validated || !this.task.predicted_value)) {
        return 'selected'
      } else if (this.task.predicted_value === option.id) {
        return 'predicted'
      }
      return ''
    }
  }
}
</script>

<style scoped lang="scss">
.meta-annotation-task {
  min-width: 0;
  container-type: inline-size;
}

.task-header {
  display: flex;
  align-items: baseline;
  min-width: 0;
}

.task-name {
  font-size: 16px;
  padding: 10px 15px 5px 15px;
  flex: 0 1 125px;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-description {
  font-size: 12px;
  padding: 10px 15px 5px 15px;
  flex: 1 1 auto;
  min-width: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

@container (max-width: 380px) {
  .task-name {
    font-size: 13px;
    padding: 6px 8px 2px 8px;
    flex-basis: 88px;
  }

  .task-description {
    font-size: 11px;
    padding: 6px 8px 2px 8px;
  }

  .task-values-container {
    padding: 0 8px 8px 8px;
    gap: 3px;

    .task-value {
      font-size: 12px;
      padding: 0.15rem 0.4rem;
      line-height: 1.2;
    }
  }

  .predicted-conf {
    font-size: 8pt;
  }
}

.selected {
  color: #fff;
  background-color: $primary-alt !important;
  border-color: $primary-alt !important;
}

.predicted {
  background: lightgrey;
  border-color: $primary-alt;
}

.predicted-conf {
  font-size: 9pt;
  display: block;
}

.task-values-container {
  padding: 0 15px 10px 15px;
  display: flex;
  flex-direction: row;
  flex-wrap: wrap;
  gap: 4px;
  min-width: 0;
  box-shadow: 0 5px 5px -5px rgba(0,0,0,0.2);

  .task-value {
    flex: 1 1 auto;
    min-width: 0;
    white-space: normal;
  }
}
</style>
