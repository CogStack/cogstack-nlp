<template>
  <div>
    <div class="task-name">{{task.name}}</div>
    <div class="task-description">{{task.description}}</div>
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
.task-name {
  font-size: 16px;
  padding: 10px 15px 5px 15px;
  display: inline-block;
  width: 125px;
}

.task-description {
  font-size: 12px;
  padding: 10px 15px 5px 15px;
  vertical-align: middle;
  display: inline-block;
  width: calc(100% - 125px);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
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
  box-shadow: 0 5px 5px -5px rgba(0,0,0,0.2);

  .task-value {
    flex: 1 1 auto;
  }
}
</style>
