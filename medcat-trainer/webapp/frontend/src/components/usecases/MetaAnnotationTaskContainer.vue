<template>
  <div class="meta-task-container" v-if="tasks && tasks.length > 0">
    <div class="title">Meta Annotation Tasks</div>
    <div class="meta-task-list">
      <meta-annotation-task v-for="task of tasks" :key="task.id"
                            @select:metaAnno="selectedTaskAnno" :task="task"></meta-annotation-task>
    </div>
  </div>
</template>

<script>
import MetaAnnotationTask from '@/components/usecases/MetaAnnotationTask.vue'
import MetaAnnotationService from '@/mixins/MetaAnnotationService.js'

export default {
  name: 'MetaAnnotationTaskContainer',
  components: {
    MetaAnnotationTask
  },
  mixins: [MetaAnnotationService],
  props: {
    modelPackSet: Boolean,
    taskIDs: Array,
    selectedEnt: {
      type: Object,
      default () {
        return {}
      }
    }
  },
  data () {
    return {
      tasks: Array
    }
  },
  methods: {
    selectedTaskAnno (task, option) {
      if (task.value === option.id) {
        if (task.validated && !task.predicted_value) {
          // remove annotation
          this.$http.delete(`/api/meta-annotations/${task.annotation_id}/`).then(() => {
            task.value = null
            task.annotation_id = null
          })
        } else {
          // update prediction to validated is true.
          task.validated = !task.validated
          this.updateMetaAnno(task, option)
        }
      } else if (task.value && task.value !== option.id) {
        // update to new value
        task.validated = true
        this.updateMetaAnno(task, option)
      } else {
        // create new
        this.newMetaAnnotation(this.selectedEnt, task, option.id).then(resp => {
          task.annotation_id = resp.data.id
          task.value = resp.data.meta_task_value
        })
      }
    },
    updateMetaAnno (task, option) {
      let payload = {
        validated: task.validated,
        predicted_meta_task_value: task.predicted_meta_task_value,
        annotated_entity: this.selectedEnt.id,
        meta_task: task.id,
        meta_task_value: option.id
      }
      this.$http.put(`/api/meta-annotations/${task.annotation_id}/`, payload).then(() => {
        task.value = option.id
      })
    }
  },
  created () {
    const that = this
    this.fetchMetaTasks(this.taskIDs, () => {
      if (that.selectedEnt) {
        that.fetchMetaAnnotations(that.selectedEnt, !this.modelPackSet)
      }
    })
  },
  watch: {
    'taskIDs': 'fetchMetaTasks',
    'selectedEnt': function(selectedEnt) {
      this.fetchMetaAnnotations(selectedEnt, !this.modelPackSet)
    }
  }
}
</script>

<style scoped lang="scss">
.meta-task-list {
  overflow-y: auto;
  min-height: 250px;
}
</style>
