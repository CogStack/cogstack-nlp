import _ from 'lodash'
import MetaAnnotationService from '@/mixins/MetaAnnotationService.js'
import ConceptDetailService from '@/mixins/ConceptDetailService.js'

export default {
  name: 'SummaryService',
  props: {
    currentDoc: Object,
    taskIDs: Array,
    searchFilterDBIndex: String
  },
  mixins: [ConceptDetailService, MetaAnnotationService],
  data() {
    return {
      metaAnnos: {},
      taskMaps: {}
    }
  },
  methods: {
    enrichSummary(annos) {
      const that = this
      // Batch fetch concept details for annotations missing pretty_name
      const annosNeedingDetails = annos.filter(anno => !anno.pretty_name && anno.entity)
      if (annosNeedingDetails.length > 0) {
        const annotationsPayload = annosNeedingDetails.map(anno => ({
          id: anno.id,
          entity: anno.entity
        }))
        this.$http.post('/api/batch-concept-details/', {
          annotations: annotationsPayload,
          cdb_search_index: this.searchFilterDBIndex
        }).then(resp => {
          // Update annotations with concept details
          const results = resp.data.results
          annosNeedingDetails.forEach(anno => {
            const details = results[anno.id]
            if (details) {
              anno.cui = details.cui
              anno.desc = details.desc
              anno.type_ids = details.type_ids
              anno.pretty_name = details.pretty_name
              anno.synonyms = details.synonyms
              anno.icd10 = details.icd10 || []
              anno.opcs4 = details.opcs4 || []
            }
          })
        }).catch(err => {
          console.error('Error fetching batch concept details:', err)
        })
      }
      if (this.taskIDs.length > 0) {
        this.fetchMetaTasks(this.taskIDs, () => {
          that.taskMaps = {}
          that.tasks.forEach(task => {
            that.taskMaps[task.id] = {}
            task.options.forEach(op => {
              that.taskMaps[task.id][op.id] = op.name
            })
          })
          that.enrichMetaAnnos(annos)
        })
      }
    },
    showInfoCol(info) {
      return _.some(this.annos, a => (a[info] || []).length > 0)
    },
    enrichMetaAnnos(annos) {
      const that = this
      this.metaAnnos = {}
      const annotatedEntityIds = annos.map(anno => anno.id).filter(id => id != null)

      if (annotatedEntityIds.length === 0) {
        return
      }

      // Batch fetch meta annotations
      this.$http.post('/api/batch-meta-annotations/', {
        annotated_entity_ids: annotatedEntityIds
      }).then(resp => {
        const results = resp.data.results
        const useDefault = false

        // Process each annotation's meta annotations
        annos.forEach(ent => {
          // Handle both string and number keys from API response
          const entityId = ent.id
          const metaAnnoList = results[entityId] || results[String(entityId)] || results[Number(entityId)] || []
          const taskValues = []

          // Ensure tasks are loaded
          if (!this.tasks || this.tasks.length === 0) {
            console.warn('Tasks not loaded yet, skipping meta annotation processing for entity', entityId)
            that.$set(that.metaAnnos, entityId, [])
            return
          }

          // Map meta annotations to tasks (create copies to avoid mutating original tasks)
          // Only include tasks that have values, matching the original fetchMetaAnnotations behavior
          for (let task of this.tasks) {
            const savedTask = metaAnnoList.filter(ma => ma.meta_task === task.id)
            if (savedTask.length > 0) {
              const r = savedTask[0]
              const taskCopy = _.cloneDeep(task)
              taskCopy.value = r.meta_task_value
              taskCopy.annotation_id = r.id
              taskCopy.predicted_value = r.predicted_meta_task_value || null
              taskCopy.validated = r.validated
              taskCopy.acc = r.acc
              taskValues.push(taskCopy)
            } else if (useDefault && task.default) {
              // Handle default values if needed (would require creating new meta annotations)
              // For now, just add the task with default value
              const taskCopy = _.cloneDeep(task)
              taskCopy.value = task.default
              taskValues.push(taskCopy)
            }
            // Note: We don't include tasks without values, matching original behavior
          }
          ent.metaAnnos = taskValues
        })
      }).catch(err => {
        console.error('Error fetching batch meta annotations:', err)
        if (err.response) {
          console.error('Response data:', err.response.data)
          console.error('Response status:', err.response.status)
        }
      })
    },
    selectConcept(concept) {
      this.$emit('select:AnnoSummaryConcept', this.annos.indexOf(concept))
    },
    leftContext(concept) {
      return this.currentDoc.text.slice(_.max([0, concept.start_ind - 20]), concept.start_ind)
    },
    rightContext(concept) {
      const docText = this.currentDoc.text
      return this.currentDoc.text.slice(concept.end_ind, _.min([docText.length, concept.end_ind + 20]))
    },
    highlightClass(concept) {
      const def = !concept.correct && !concept.deleted && !concept.killed &&
        !concept.alternative && !concept.manually_created
      return {
        'highlight-task-default': def,
        'highlight-task-new': concept.manually_created,
        'highlight-task-0': concept.correct,
        'highlight-task-1': concept.deleted,
        'highlight-task-2': concept.killed,
        'highlight-task-3': concept.alternative
      }
    }
  }
}
