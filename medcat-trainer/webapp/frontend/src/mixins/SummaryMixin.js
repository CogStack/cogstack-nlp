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
  data () {
    return {
      metaAnnos: {
        type: Object,
        default () {
          return {}
        }
      },
      taskMaps: Object
    }
  },
  methods: {
    enrichSummary (annos, onAllAnnotationsCallback) {
      const that = this
      annos.forEach(anno => {
        if (!anno.pretty_name) {
          this.fetchDetail(anno, this.searchFilterDBIndex)
        }
      })
      if (this.taskIDs.length > 0) {
        this.fetchMetaTasks(this.taskIDs, () => {
          that.taskMaps = {}
          that.tasks.forEach(task => {
            that.taskMaps[task.id] = {}
            task.options.forEach(op => {
              that.taskMaps[task.id][op.id] = op.name
            })
          })
          that.enrichMetaAnnos(annos, onAllAnnotationsCallback)
        })
      }
    },
    showInfoCol (info) {
      return _.some(this.annos, a => (a[info] || []).length > 0)
    },
    enrichMetaAnnos (annos, finishedEnrichmentCallback) {
      const that = this
      this.metaAnnos = {}
      const useDefault = false
      for (let ent of annos) {
        this.fetchMetaAnnotations(ent, tasks => {
          that.$set(that.metaAnnos, ent.id, tasks)
          if (Object.entries(this.metaAnnos).length === annos.length) {
            if (finishedEnrichmentCallback) {
              finishedEnrichmentCallback()
            }
          }
        }, useDefault)
      }
    },
    selectConcept (concept) {
      this.$emit('select:AnnoSummaryConcept', this.annos.indexOf(concept))
    },
    leftContext (concept) {
      return this.currentDoc.text.slice(_.max([0, concept.start_ind - 20]), concept.start_ind)
    },
    rightContext (concept) {
      const docText = this.currentDoc.text
      return this.currentDoc.text.slice(concept.end_ind, _.min([docText.length, concept.end_ind + 20]))
    },
    highlightClass (concept) {
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
