<template>
  <div class="container-fluid demo">
    <div class="demo-text">
      <form @submit.prevent>
        <div class="form-group">
          <label class="demo-label">Model Pack:</label>
          <select class="form-control" v-model="selectedModelPack">
            <option :value="mp" v-for="mp of modelPacks" :key="mp.id">{{mp.name}}
            </option>
          </select>
        </div>
        <div class="demo-toast demo-toast--inline" v-if="toast.visible" :class="`demo-toast--${toast.variant}`">
          {{ toast.message }}
        </div>
        <div class="form-group">
          <label class="demo-label">CUI Filter:</label>
          <div class="cui-filter-controls">
            <label class="cui-filter-checkbox">
              <input type="checkbox" v-model="includeSubConcepts">
              Incl. Sub-concepts
            </label>
            <button
              type="button"
              class="btn btn-link btn-sm cui-filter-paste-toggle"
              @click="showCuiFilterTextarea = !showCuiFilterTextarea"
            >
              {{ showCuiFilterTextarea ? 'Hide box' : 'Paste CUIs (optional)' }}
            </button>
          </div>

          <div class="cui-filter-picker">
            <div v-if="!selectedModelPack?.concept_db" class="text-muted small">
              Selected ModelPack does not have a Concept DB.
            </div>
            <concept-picker
              v-else
              :restrict_concept_lookup="false"
              :cui_filter="''"
              :cdb_search_filter="[]"
              :concept_db="selectedModelPack.concept_db"
              :selection="''"
              @pickedResult:concept="addCuiToFilter"
            />
          </div>

          <div v-if="selectedCuiFilterConcepts.length > 0" class="cui-pill-row">
            <span class="cui-pill" v-for="item in selectedCuiFilterConcepts" :key="item.cui" :title="item.name || item.cui">
              <span class="cui-pill-text">{{ item.cui }} - {{ item.name }}</span>
              <button type="button" class="cui-pill-remove" @click="removeCuiFromFilter(item.cui)">×</button>
            </span>
          </div>
          <textarea
            v-if="showCuiFilterTextarea"
            v-model="cuiFilters"
            class="form-control"
            name="cui"
            rows="2"
            placeholder="Optional: paste comma separated list e.g. 91175000, 84757009"
            @blur="syncPillsFromCuiText"
          ></textarea>
        </div>
      </form>
    </div>
    <div class="view-port">
      <div class="clinical-text">
        <annotate-text-entry
          :modelpackId="selectedModelPack?.id"
          :cuis="cuiFilters"
          :includeSubConcepts="includeSubConcepts"
          :taskName="task"
          :taskValues="taskValues"
          @select:concept="selectEntity"
        ></annotate-text-entry>
      </div>
      <div class="sidebar">
        <div class="concept-summary-container">
          <concept-summary :selectedEnt="currentEnt" :project="selectedProject"
                           :searchFilterDBIndex="searchFilterDBIndex"></concept-summary>
        </div>
        <meta-annotations-summary :metaAnnotations="currentEnt?.meta_annotations"></meta-annotations-summary>
      </div>
    </div>
  </div>
</template>

<script>
import ConceptSummary from '@/components/common/ConceptSummary.vue'
import ConceptPicker from '@/components/common/ConceptPicker.vue'
import AnnotateTextEntry from '@/components/common/AnnotateTextEntry.vue'
import MetaAnnotationsSummary from '@/components/common/MetaAnnotationsSummary.vue'

const TASK_NAME = 'Concept Anno'
const VALUES = ['Val']

export default {
  name: 'Demo',
  components: {
    ConceptSummary,
    ConceptPicker,
    AnnotateTextEntry,
    MetaAnnotationsSummary
  },
  data () {
    return {
      modelPacks: [],
      selectedModelPack: null,
      cachingModelPack: false,
      showCuiFilterTextarea: false,
      selectedCuiFilterConcepts: [],
      toast: {
        visible: false,
        message: '',
        variant: 'info',
        hideTimer: null
      },
      projects: [],
      selectedProject: null,
      projectsByModelPackId: {},
      cuiFilters: '',
      includeSubConcepts: false,
      currentEnt: null,
      task: TASK_NAME,
      taskValues: VALUES,
      searchFilterDBIndex: null
    }
  },
  computed: {
    currentEntMetaAnnotations () {
      return this.currentEnt?.meta_annotations || []
    }
  },
  created () {
    Promise.all([
      this.fetchAllPages('/api/project-annotate-entities/'),
      this.fetchAllPages('/api/modelpacks/')
    ]).then(([projects, modelPacks]) => {
      this.projects = projects
      this.modelPacks = modelPacks
      this.projectsByModelPackId = projects.reduce((acc, p) => {
        if (p.model_pack && !acc[p.model_pack]) {
          acc[p.model_pack] = p
        }
        return acc
      }, {})

      const firstUsableMp = this.modelPacks.find(mp => this.projectsByModelPackId[mp.id])
      this.selectedModelPack = firstUsableMp || (this.modelPacks.length > 0 ? this.modelPacks[0] : null)
    })
  },
  methods: {
    fetchAllPages (baseUrl) {
      const results = []
      const fetch = (url) => {
        return this.$http.get(url).then(resp => {
          results.push(...resp.data.results)
          if (resp.data.next) {
            const nextQuery = resp.data.next.split('?').slice(-1)[0]
            const nextUrl = `${baseUrl}?${nextQuery}`
            return fetch(nextUrl)
          }
          return results
        })
      }
      return fetch(baseUrl)
    },
    parseCuis (text) {
      if (!text) return []
      return text
        .split(/[,;\n\r\t]+/g)
        .map(s => s.trim())
        .filter(Boolean)
    },
    syncCuiTextFromPills () {
      const cuis = this.selectedCuiFilterConcepts.map(c => c.cui).filter(Boolean)
      this.cuiFilters = cuis.join(',')
    },
    syncPillsFromCuiText () {
      const cuis = this.parseCuis(this.cuiFilters)
      const existingByCui = Object.assign({}, ...this.selectedCuiFilterConcepts.map(item => ({ [item.cui]: item })))
      this.selectedCuiFilterConcepts = cuis.map(cui => existingByCui[cui] || { cui })
    },
    addCuiToFilter (picked) {
      if (!picked?.cui) return
      if (!this.selectedCuiFilterConcepts.find(x => x.cui === picked.cui)) {
        this.selectedCuiFilterConcepts.push({ cui: picked.cui, name: picked.name })
        this.syncCuiTextFromPills()
      }
    },
    removeCuiFromFilter (cui) {
      this.selectedCuiFilterConcepts = this.selectedCuiFilterConcepts.filter(x => x.cui !== cui)
      this.syncCuiTextFromPills()
    },
    showToast (message, variant = 'info', autoHideMs = 2500) {
      if (this.toast.hideTimer) {
        clearTimeout(this.toast.hideTimer)
        this.toast.hideTimer = null
      }
      this.toast.message = message
      this.toast.variant = variant
      this.toast.visible = true
      if (autoHideMs && autoHideMs > 0) {
        this.toast.hideTimer = setTimeout(() => {
          this.toast.visible = false
          this.toast.hideTimer = null
        }, autoHideMs)
      }
    },
    cacheSelectedModelPack () {
      if (!this.selectedModelPack?.id) return Promise.resolve()
      this.cachingModelPack = true
      this.showToast('Caching model…', 'info', 0)
      return this.$http.get(`/api/cache-modelpack/${this.selectedModelPack.id}/`).then(() => {
        this.cachingModelPack = false
        this.showToast('Model cached', 'success', 1500)
      }).catch(() => {
        this.cachingModelPack = false
        this.showToast('Failed to cache model', 'error', 3000)
      })
    },
    selectEntity (ent) {
      this.currentEnt = ent
    },
    fetchCDBSearchIndex () {
      if (this.selectedProject?.cdb_search_filter?.length > 0) {
        this.$http.get(`/api/concept-dbs/${this.selectedProject.cdb_search_filter[0]}/`).then(resp => {
          if (resp.data) {
            this.searchFilterDBIndex = `${resp.data.name}_id_${this.selectedProject.cdb_search_filter}`
          }
        })
      } else {
        this.searchFilterDBIndex = null
      }
    }
  },
  watch: {
    selectedModelPack: {
      handler () {
        this.selectedProject = this.selectedModelPack ? (this.projectsByModelPackId[this.selectedModelPack.id] || null) : null
        this.fetchCDBSearchIndex()
        this.cacheSelectedModelPack()
      }
    },
  }
}
</script>

<style scoped lang="scss">
.demo {
  height: 100%;
  display: flex;
}

.demo-text {
  display: flex;
  flex-direction: column;
  flex: 0 0 460px;
  height: 100%;
  overflow: auto;
}

.view-port {
  flex: 1 1 auto;
  display: flex;
}

.clinical-text {
  height:100%;
  flex-direction: column;
  flex: 1 1 auto;
}

.sidebar {
  height:100%;
  display: flex;
  flex-direction: column;
  flex: 0 0 350px;
}

.concept-summary-container {
  max-height: 50%;
  overflow-y: auto;
  flex-shrink: 0;
}

form {
  margin: 4%;
  display: flex;
  flex-direction: column;
  height: 100%;
}

.demo-toast {
  padding: 10px 12px;
  border-radius: 6px;
  color: #fff;
  word-wrap: break-word;
}

.demo-toast--inline {
  margin: -6px 0 12px 0;
  box-shadow: 0 6px 18px rgba(0, 0, 0, 0.12);
}

.demo-toast--info {
  background: #0d6efd;
}

.demo-toast--success {
  background: #198754;
}

.demo-toast--error {
  background: #dc3545;
}

.cui-filter-controls {
  margin: -4px 0 8px 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.cui-filter-checkbox {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 0;
  font-size: 14px;
  cursor: pointer;
}

.cui-filter-paste-toggle {
  padding: 0;
}

.demo-label {
  display: block;
  font-weight: 600;
  margin: 0 0 6px 0;
  padding: 0;
  font-size: inherit;
  line-height: 1.5;
  color: inherit;
  width: 100%;
}

.form-group {
  margin-bottom: 15px;
}

.cui-filter-picker {
  margin: 6px 0 10px 0;
}

.cui-pill-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin: 6px 0 10px 0;
}

.cui-pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border: 1px solid rgba(0, 0, 0, 0.15);
  background: rgba(13, 110, 253, 0.08);
  color: #0b5ed7;
  border-radius: 999px;
  padding: 4px 10px;
  font-size: 12px;
  line-height: 1;
}

.cui-pill-text {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
}

.cui-pill-remove {
  border: none;
  background: transparent;
  color: inherit;
  padding: 0;
  cursor: pointer;
  font-size: 16px;
  line-height: 1;
}
</style>
