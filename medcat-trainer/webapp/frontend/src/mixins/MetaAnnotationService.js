
import _ from 'lodash'

export default {
  name: 'MetaAnnotationService',
  data () {
    return {
      tasks: []
    }
  },
  methods: {
    fetchMetaTasks (taskIDs, callback) {
      this.$http.get(`/api/meta-tasks/`).then(resp => {
        let tasks = resp.data.results.filter(r => {
          return taskIDs.includes(r.id)
        })
        let values = _.flatten(tasks.map(t => t.values))
        this.$http.get(`/api/meta-task-values/`).then(resp => {
          let taskValueObjs = resp.data.results.filter(r => values.includes(r.id))
          let taskValObjMap = {}
          for (const valId of values) {
            taskValObjMap[valId] = taskValueObjs.filter(o => o.id === valId)[0]
          }
          tasks = tasks.map(t => {
            t.options = t.values.map(val => taskValObjMap[val])
            t.value = null
            delete t['values']
            return t
          })
          this.tasks = tasks
          if (typeof (callback) === 'function') {
            callback()
          }
        })
      })
    },
    newMetaAnnotation (selectedEnt, task, optionId) {
      const payload = {
        validated: true, // 'default' meta annotations are always valid.
        annotated_entity: selectedEnt.id,
        meta_task: task.id,
        meta_task_value: optionId
      }
      return this.$http.post(`/api/meta-annotations/`, payload)
    },
    fetchMetaAnnotations (selectedEnt, useDefault, callback) {
      if (this.tasks.length > 0 && selectedEnt !== null) {
        for (let t of this.tasks) {
          t.value = null
        }
        this.$http.get(`/api/meta-annotations/?annotated_entity=${selectedEnt.id}`).then(resp => {
          // map current state tasks to these entities - to delete as needed.
          let taskValues = []
          let newAnnoPromises = []
          for (let task of this.tasks) {
            let savedTask = resp.data.results.filter(t => t.meta_task === task.id)
            if (savedTask.length > 0) {
              let r = savedTask[0]
              task.value = r.meta_task_value
              task.annotation_id = r.id
              task.predicted_value = r.predicted_meta_task_value
              task.validated = r.validated
              task.acc = r.acc
              taskValues.push(task)
            } else if (useDefault && task.default) {
              // no annotation exists, should be validated and set as default value
              newAnnoPromises.push(this.newMetaAnnotation(selectedEnt, task, task.default))
              taskValues.push(task)
            }
          }
          let callCallback = function () {
            if (typeof (callback) === 'function') {
              callback(_.cloneDeep(taskValues))
            }
          }

          if (newAnnoPromises.length) {
            Promise.all(newAnnoPromises).then(values => {
              for (let resp of values) {
                let task = taskValues.filter(t => t.id === resp.data.meta_task)[0]
                task.annotation_id = resp.data.id
                task.value = resp.data.meta_task_value
              }
              callCallback()
            })
          } else {
            callCallback()
          }
        })
      }
    }
  }
}
