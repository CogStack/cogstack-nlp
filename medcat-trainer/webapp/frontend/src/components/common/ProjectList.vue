<template>
  <div class="full-height project-table">
    <div class="table-container">
      <v-overlay :model-value="loadingProjects"
                 :disabled="true"
                 :persistent="true"
                 color="primary"
                 class="align-center justify-center"
                 activator="parent">
        <v-progress-circular indeterminate color="primary"></v-progress-circular>
        <span class="overlay-message">Loading Projects...</span>
      </v-overlay>
      <v-data-table id="projectTable"
                    :key="tableKey"
                    :headers="visibleHeaders"
                    :items="filteredProjectItems"
                    :hover="true"
                    :mobile="false"
                    :items-per-page="-1"
                    hide-default-footer
                    :row-props="availableProjectForMetrics"
                    v-if="!loadingProjects"
                    @click:row="select">
        <template #header.name>
          <div class="column-header">
            <button
              type="button"
              class="column-header-sort"
              :class="{ active: sortBy === 'name' }"
              title="Sort by title"
              @click="toggleSort('name')">
              Title
              <font-awesome-icon
                class="sort-icon"
                :icon="sortBy === 'name' ? (sortOrder === 'asc' ? 'sort-up' : 'sort-down') : 'sort'"
              />
            </button>
            <input
              v-model="searchQuery"
              type="search"
              class="form-control form-control-sm header-filter-input"
              placeholder="Filter…"
              aria-label="Filter by title"
              @click.stop
            />
          </div>
        </template>

        <template #header.require_entity_validation>
          <div class="column-header">
            <span class="column-header-label">Mode</span>
            <select
              v-model="modeFilter"
              class="form-control form-control-sm header-filter-input"
              aria-label="Filter by annotate or validate"
              @click.stop>
              <option
                v-for="opt in modeFilterOptions"
                :key="opt.value"
                :value="opt.value">
                {{ opt.label }}
              </option>
            </select>
          </div>
        </template>

        <template #header.status>
          <div class="column-header">
            <span class="column-header-label">
              Status
              <v-tooltip activator="parent">
                <div>
                  <font-awesome-icon class="status-cell" icon="pen"></font-awesome-icon> - project is actively annotating
                </div>
                <div>
                  <font-awesome-icon class="status-cell danger" icon="times"></font-awesome-icon> - project marked as discontinued (failed)
                </div>
                <div>
                  <font-awesome-icon class="status-cell complete-project success" icon="check"></font-awesome-icon> - project is complete
                </div>
              </v-tooltip>
            </span>
            <select
              v-model="statusFilter"
              class="form-control form-control-sm header-filter-input"
              aria-label="Filter by project status"
              @click.stop>
              <option
                v-for="opt in statusFilterOptions"
                :key="opt.value"
                :value="opt.value">
                {{ opt.label }}
              </option>
            </select>
          </div>
        </template>

        <template #header.create_time>
          <button
            type="button"
            class="column-header-sort"
            :class="{ active: sortBy === 'create_time' }"
            title="Sort by create date"
            @click="toggleSort('create_time')">
            Created
            <font-awesome-icon
              class="sort-icon"
              :icon="sortBy === 'create_time' ? (sortOrder === 'asc' ? 'sort-up' : 'sort-down') : 'sort'"
            />
          </button>
        </template>

        <template #header.last_modified>
          <button
            type="button"
            class="column-header-sort"
            :class="{ active: sortBy === 'last_modified' }"
            title="Sort by last modified"
            @click="toggleSort('last_modified')">
            Modified
            <font-awesome-icon
              class="sort-icon"
              :icon="sortBy === 'last_modified' ? (sortOrder === 'asc' ? 'sort-up' : 'sort-down') : 'sort'"
            />
          </button>
        </template>

        <template #header.locked>
          <span class="header-label-wrap">
            <span>Project</span>
            <span>Locked</span>
          </span>
          <v-tooltip activator="parent">
            Whether the project is locked from further annotation
          </v-tooltip>
        </template>

        <template #header.metrics>
          Metrics
          <v-tooltip activator="parent">
            Access the metrics view for a single or group of projects
          </v-tooltip>
        </template>
        <template #header.cuis>
          Concepts
          <v-tooltip activator="parent">
            <div>The list of Concept Unique Identifiers (CUIs) to be annotated in a project.</div>
            <div>'All' indicates there is no filter</div>
          </v-tooltip>
        </template>
        <template #header.anno_class>
          <span class="header-label-wrap">
            <span>Annotation</span>
            <span>Classification</span>
          </span>
          <v-tooltip activator="parent">
            Annotation set classification.
            <div>
              <font-awesome-icon class="status-cell" icon="minus"></font-awesome-icon> indicates 'local' annotations are collected specific to this project's use case / clinical area.
            </div>
            <div>
              <font-awesome-icon class="status-cell success" icon="globe"></font-awesome-icon> indicates global annotations are collected suitable for use within a global model.
            </div>
          </v-tooltip>
        </template>
        <template #header.progress>
          Progress
          <v-tooltip activator="parent">
            Number of validated documents / total number of documents configured in the project
          </v-tooltip>
        </template>

        <template #item.locked="{ item }">
          <font-awesome-icon v-if="item.project_locked" class="status-locked" icon="lock"></font-awesome-icon>
          <font-awesome-icon v-if="!item.project_locked" class="status-unlocked" icon="lock-open"></font-awesome-icon>
        </template>
        <template #item.create_time="{ item }">
          {{new Date(item.create_time).toLocaleDateString()}}
        </template>
        <template #item.last_modified="{ item }">
          <span class="date-cell">{{ formatShortDate(item.last_modified) }}</span>
        </template>
        <template #item.cuis="{ item }">
          <div class="term-list">{{item.cuis.slice(0, 40) || 'All'}}</div>
        </template>
        <template #item.require_entity_validation="{ item }">
          {{item.require_entity_validation ? 'Annotate' : 'Validate'}}
        </template>
        <template #item.status="{ item }">
          <font-awesome-icon v-if="item.project_status === 'A'" class="status-cell" icon="pen"></font-awesome-icon>
          <font-awesome-icon v-if="item.project_status === 'D'" class="status-cell danger" icon="times"></font-awesome-icon>
          <font-awesome-icon v-if="item.project_status === 'C'" class="status-cell complete-project success" icon="check"></font-awesome-icon>
        </template>
        <template #item.anno_class="{ item }">
          <font-awesome-icon v-if="item.annotation_classification" class="status-cell success" icon="globe"></font-awesome-icon>
          <font-awesome-icon v-if="!item.annotation_classification" class="status-cell" icon="minus"></font-awesome-icon>
        </template>
        <template #item.cdb_search_filter="{ item }">
          <span v-if="cdbSearchIndexStatus[item.cdb_search_filter]">
            <font-awesome-icon icon="check" class="success"></font-awesome-icon>
            <v-tooltip activator="parent" >Concept DB search available</v-tooltip>
          </span>
          <span v-if="!cdbSearchIndexStatus[item.cdb_search_filter]">
            <font-awesome-icon  icon="times" class="danger"></font-awesome-icon>
            <v-tooltip activator="parent">
              <div>Project concept search not available.</div>
              <div>Check the project setup 'CDB search filter' option is set and correctly imported</div>
            </v-tooltip>
          </span>
        </template>
        <template #item.model_loaded="{ item }">
          <div v-if="modelLoaded[item.id]" @click.stop>
            <button class="btn btn-outline-success model-up">
              <font-awesome-icon icon="times" class="clear-model-cache" @click="clearLoadedModel(item.id)"></font-awesome-icon>
              <font-awesome-icon icon="fa-cloud-arrow-up"></font-awesome-icon>
            </button>
          </div>
          <div v-if="!modelLoaded[item.id]" @click.stop>
            <button class="btn btn-outline-secondary" @click="loadProjectCDB(item.id)">
              <font-awesome-icon v-if="loadingModel !== item.id" icon="fa-cloud-arrow-up"></font-awesome-icon>
              <font-awesome-icon v-if="loadingModel === item.id" icon="spinner" spin></font-awesome-icon>
            </button>
          </div>
        </template>
        <template #item.run_model="{ item }">
          <div @click.stop>
            <button :disabled="runningBgTasks.has(item.id) || completeBgTasks.has(item.id)"
                    @click="runModel(item.id)"
                    class="run-model btn btn-outline-primary">
              <font-awesome-icon class=" model-bg-run-comp" icon="check"
                                 v-if="completeBgTasks.has(item.id)"></font-awesome-icon>
              <font-awesome-icon v-if="runningBgTasks.has(item.id)" icon="spinner" spin></font-awesome-icon>
              <font-awesome-icon v-if="!runningBgTasks.has(item.id)" icon="robot"></font-awesome-icon>
            </button>
          </div>
        </template>
        <template #item.metrics="{ item }">
          <div  @click.stop>
            <button class="btn"
                    :class="{'btn-primary': selectedProjects.indexOf(item) !== -1, 'btn-outline-primary': selectedProjects.indexOf(item) === -1}"
                    @click="selectProject(item)">
              <font-awesome-icon icon="fa-chart-pie"></font-awesome-icon>
            </button>
            <v-tooltip activator="parent">
              Once selected, only projects <br>
              configured to use the same MedCAT <br>
              model will be available
            </v-tooltip>
          </div>
        </template>
        <template #item.save_model="{ item }">
          <div @click.stop>
            <button class="btn btn-outline-primary" :disabled="saving" @click="saveModel(item.id)"><font-awesome-icon icon="save"></font-awesome-icon></button>
          </div>

        </template>
        <template #item.progress="{ item }">
          <v-progress-linear
            v-model="item.progress"
            color="#32ab60"
            height="22px"
            :max="item.progress_max">
             <span>{{item.progress}}</span> / <span>{{item.progress_max}}</span>
          </v-progress-linear>
        </template>

        <template #no-data>
          <div class="project-list-no-data">
            <p>No projects match the current filters.</p>
            <button type="button" class="btn btn-outline-primary btn-sm" @click="clearFilters">
              Clear filters
            </button>
          </div>
        </template>
      </v-data-table>
    </div>
    <div>
      <transition name="alert"><div class="alert alert-primary" v-if="saving" role="alert">Saving models</div></transition>
      <transition name="alert"><div class="alert alert-primary" v-if="modelSaved" role="alert">Model Successfully saved</div></transition>
      <transition name="alert"><div class="alert alert-danger" v-if="modelSavedError" role="alert">Error saving model</div></transition>
      <transition name="alert"><div class="alert alert-danger" v-if="runModelBgError" role="alert">Error running model in background</div></transition>
      <transition name="alert"><div class="alert alert-primary" v-if="loadingModel" role="alert">Loading model</div></transition>
      <transition name="alert"><div class="alert alert-danger" v-if="modelCacheLoadError" role="alert">Error loading MedCAT model for project</div></transition>
      <transition name="alert"><div class="alert alert-danger" v-if="projectLockedWarning" role="alert">Unable load a locked project. Contact your CogStack administrator to unlock</div></transition>
      <transition name="alert"><div class="alert alert-info " v-if="metricsJobId">
        Submitted Metrics job {{metricsJobId.metrics_job_id}}. Check the
        <router-link to="metrics-reports/">/metrics-reports/</router-link>
        page for your results</div>
      </transition>
      <transition name="alert"><div class="alert alert-info submit-report-job-alert" v-if="selectedProjects.length > 0">
        Submit metrics report run for selected projects
        <button class="btn btn-outline-primary load-metrics" @click="submitMetricsReportReq">
          <font-awesome-icon icon="chevron-right"></font-awesome-icon>
        </button>
      </div></transition>
    </div>

    <modal v-if="clearModelModal" :closable="true" @modal:close="clearModelModal = false">
      <template #header>
        <h3>Confirm Clear Cached Model State</h3>
      </template>
      <template #body>
        <p>Confirm clearing cached MedCAT Model Project {{clearModelModal}} (and any other Projects that use the same model). </p>
        <p>
          This will remove any interim training done (if any).
          To recover the cached model, re-open the project(s), and re-submit all documents.
          If you're unsure you should not clear the model state.
        </p>
      </template>
      <template #footer>
        <button class="btn btn-primary" @click="confirmClearLoadedModel(clearModelModal)">Confirm</button>
        <button class="btn btn-default" @click="clearModelModal = false">Cancel</button>
      </template>
    </modal>

    <modal v-if="cancelRunningBgTaskModal" :closable="true" @modal:close="cancelRunningBgTaskModal = null">
      <template #header>
        <h3>Background Model Predictions</h3>
      </template>
      <template #body>
        <v-progress-linear :max="cancelRunningBgTaskModal.dsCount"
                           v-model="cancelRunningBgTaskModal.prepCount"
                           height="20px" class="animate" striped color="primary">
          <span><strong>{{ cancelRunningBgTaskModal.prepCount }} / {{ cancelRunningBgTaskModal.dsCount }}</strong></span>
        </v-progress-linear>
        <div class="cancel-dialog-body" v-if="cancelRunningBgTaskModal.prepCount < cancelRunningBgTaskModal.dsCount">
          Confirm to stop running model predictions in the background and enter project.
        </div>
        <div class="cancel-dialog-body" v-if="cancelRunningBgTaskModal.prepCount === cancelRunningBgTaskModal.dsCount">
          Model predictions ready.
        </div>
      </template>
      <template #footer>
        <button class="btn btn-primary" @click="confirmCancelBgTaskStop()">
          <span v-if="cancelRunningBgTaskModal.prepCount < cancelRunningBgTaskModal.dsCount">
            Confirm
          </span>
          <span v-if="cancelRunningBgTaskModal.prepCount === cancelRunningBgTaskModal.dsCount">
            View Project
          </span>
        </button>
      </template>
    </modal>
  </div>
</template>

<script>
import Modal from "@/components/common/Modal.vue"
import {
  ALL_FILTER,
  STATUS_FILTER_OPTIONS,
  MODE_FILTER_OPTIONS,
  filterAndSortProjects
} from '@/utils/projectListFilters'

export default {
  name: "ProjectList",
  components: { Modal},
  props: {
    projectItems: Array,
    isAdmin: Boolean,
    cdbSearchIndexStatus: Object,
  },
  data () {
    return {
      searchQuery: '',
      debouncedSearchQuery: '',
      searchDebounceTimer: null,
      statusFilter: ALL_FILTER,
      modeFilter: ALL_FILTER,
      sortBy: 'last_modified',
      sortOrder: 'desc',
      statusFilterOptions: STATUS_FILTER_OPTIONS,
      modeFilterOptions: MODE_FILTER_OPTIONS,
      tableKey: 0,
      modelLoaded: {},
      projects: {
        headers: [
          {
            value: 'locked',
            title: 'Project Locked',
            width: '4rem',
            headerProps: { class: 'icon-cell header-wrap-cell' },
            cellProps: { class: 'icon-cell' }
          },
          { value: 'id', title: 'ID', width: '3.25rem' },
          { value: 'name', title: 'Title', width: '14%' },
          {
            value: 'description',
            title: 'Description',
            headerProps: { class: 'col-hide-narrow' },
            cellProps: { class: 'col-hide-narrow' }
          },
          {
            value: 'create_time',
            title: 'Created',
            width: '5.5rem',
            headerProps: { class: 'col-hide-medium' },
            cellProps: { class: 'col-hide-medium' }
          },
          { value: 'last_modified', title: 'Modified', width: '6.5rem' },
          {
            value: 'cuis',
            title: 'CUIs',
            headerProps: { class: 'col-hide-narrow' },
            cellProps: { class: 'col-hide-narrow' }
          },
          { value: 'require_entity_validation', title: 'Mode', width: '6rem' },
          {
            value: 'status',
            title: 'Status',
            width: '3.25rem',
            headerProps: { class: 'icon-cell' },
            cellProps: { class: 'icon-cell' }
          },
          { value: 'progress', title: 'Progress', width: '7.5rem', cellProps: { class: 'progress-cell' } },
          {
            value: 'anno_class',
            title: 'Annotation Classification',
            width: '5rem',
            headerProps: { class: 'icon-cell header-wrap-cell' },
            cellProps: { class: 'icon-cell' }
          },
          {
            value: 'cdb_search_filter',
            title: 'CDB Import',
            width: '3.5rem',
            headerProps: { class: 'icon-cell header-wrap-cell' },
            cellProps: { class: 'icon-cell' }
          },
          {
            value: 'run_model',
            title: 'Run',
            width: '4rem',
            headerProps: { class: 'icon-cell' },
            cellProps: { class: 'icon-cell' }
          },
          {
            value: 'model_loaded',
            title: 'Model',
            width: '4rem',
            headerProps: { class: 'icon-cell' },
            cellProps: { class: 'icon-cell' }
          },
          {
            value: 'metrics',
            title: 'Metrics',
            width: '4rem',
            headerProps: { class: 'icon-cell' },
            cellProps: { class: 'icon-cell' }
          },
          {
            value: 'save_model',
            title: 'Save',
            width: '3.75rem',
            headerProps: { class: 'icon-cell' },
            cellProps: { class: 'icon-cell' }
          }
        ],
        adminOnlyFields: [
          'anno_class',
          'cdb_search_filter',
          'run_model',
          'model_loaded',
          'save_model'
        ]
      },
      projectLockedWarning: false,
      modelSaved: false,
      modelSavedError: false,
      runModelBgError: false,
      loadingModel: false,
      modelCacheLoadError: false,
      metricsJobId: null,
      saving: false,
      clearModelModal: false,
      selectedProjects: [],
      loadingProjects: false,
      runningBgTasks: new Set(),
      completeBgTasks: new Set(),
      cancelRunningBgTaskModal: null
    }
  },
  computed: {
    visibleHeaders() {
      const headers = this.isAdmin
        ? this.projects.headers
        : this.projects.headers.filter(f => this.projects.adminOnlyFields.indexOf(f.value) === -1)
      return headers.map(h => ({ align: 'start', ...h }))
    },
    filteredProjectItems() {
      return filterAndSortProjects(this.projectItems, {
        searchQuery: this.debouncedSearchQuery,
        statusFilter: this.statusFilter,
        modeFilter: this.modeFilter,
        sortBy: this.sortBy,
        sortOrder: this.sortOrder
      })
    },
  },
  watch: {
    searchQuery(val) {
      clearTimeout(this.searchDebounceTimer)
      this.searchDebounceTimer = setTimeout(() => {
        this.debouncedSearchQuery = val
      }, 200)
    }
  },
  beforeUnmount() {
    clearTimeout(this.searchDebounceTimer)
  },
  created () {
    this.pollDocPrepStatus()
    this.fetchModelsLoaded()
  },
  methods: {
    toggleSort(key) {
      if (this.sortBy === key) {
        this.sortOrder = this.sortOrder === 'asc' ? 'desc' : 'asc'
      } else {
        this.sortBy = key
        this.sortOrder = key === 'name' ? 'asc' : 'desc'
      }
    },
    clearFilters() {
      this.searchQuery = ''
      this.debouncedSearchQuery = ''
      this.statusFilter = ALL_FILTER
      this.modeFilter = ALL_FILTER
    },
    formatShortDate(value) {
      if (!value) return '—'
      return new Date(value).toLocaleDateString()
    },
    clearLoadedModel (projectId) {
      this.clearModelModal = projectId
    },
    confirmClearLoadedModel (projectId) {
      this.clearModelModal = false
      this.$http.delete(`/api/cache-project-model/${projectId}/`).then(_ => {
        this.fetchModelsLoaded()
      })
    },
    loadProjectCDB (projectId) {
      this.loadingModel = projectId
      this.$http.get(`/api/cache-project-model/${projectId}/`).then(_ => {
        this.loadingModel = false
        this.fetchModelsLoaded()
      }).catch(_ => {
        this.modelCacheLoadError = true
        this.loadingModel = false
        const that = this
        setTimeout(() => {
          that.modelCacheLoadError = false
        }, 5000)
      })
    },
    fetchModelsLoaded () {
      this.$http.get('/api/model-loaded/').then(resp => {
        this.modelLoaded = resp?.data?.model_states
      })
    },
    selectProject (project) {
      if (this.selectedProjects.indexOf(project) !== -1) {
        this.selectedProjects.splice(this.selectedProjects.indexOf(project), 1)
      } else {
        this.selectedProjects.push(project)
      }
      this.tableKey++
    },
    availableProjectForMetrics (data) {
      if (this.selectedProjects.length === 0) {
        return {class: ''}
      } else {
        let disabled = !(this.selectedProjects[0].concept_db === data.item.concept_db &&
                        this.selectedProjects[0].vocab === data.item.vocab) ||
                        this.selectedProjects[0].model_pack !== data.item.model_pack
        return {class: disabled ? ' disabled-row' : ''}
      }
    },
    submitMetricsReportReq () {
      const payload = {
        projectIds: this.selectedProjects.map(p => p.id).join(',')
      }
      this.selectedProjects = []
      this.$http.post('/api/metrics-job/', payload).then(resp => {
        this.metricsJobId = resp.data
        setTimeout(() => {
          this.metricsJobId = null
        }, 15000)
      })
    },
    select (_, { item }) {
      let project = item
      if (project) {
        if (project.project_locked) {
          this.projectLockedWarning = true
          const that = this
          setTimeout(() => {
            that.projectLockedWarning = false
          }, 5000)
        } else if (this.runningBgTasks.has(project.id)) {
          this.bgTaskStatus(project)
        } else {
          this.$router.push({
            name: 'train-annotations',
            params: {
              projectId: project.id
            }
          })
        }
      }
    },
    runModel (projectId) {
      let payload = {
        project_id: projectId
      }
      this.runningBgTasks = new Set([...this.runningBgTasks, projectId])
      this.$http.post('/api/prepare-documents-bg/', payload).then(_ => {
      }).catch(_ => {
        this.runModelBgError = true
        const that = this
        setTimeout(function () {
          that.runModelBgError = false
        }, 5000)
      })
    },
    saveModel (projectId) {
      let payload = {
        project_id: projectId
      }
      this.saving = true
      this.$http.post('/api/save-models/', payload).then(() => {
        this.saving = false
        this.modelSaved = true
        const that = this
        setTimeout(() => {
          that.modelSaved = false
        }, 5000)
      }).catch(() => {
        this.saving = false
        this.modelSavedError = true
        const that = this
        setTimeout(function () {
          that.modelSavedError = false
        }, 5000)
      })
    },
    bgTaskStatus (project) {
      this.$http.get(`/api/prep-docs-bg-tasks/${project.id}/`).then(resp => {
        this.cancelRunningBgTaskModal = {
          proj: project,
          dsCount: resp.data.dataset_len,
          prepCount: resp.data.prepd_docs_len
        }
        setTimeout(() => {
          if (this.cancelRunningBgTaskModal) {
            this.bgTaskStatus(project)
          }
        }, 5000)
      })
    },
    confirmCancelBgTaskStop () {
      let project = this.cancelRunningBgTaskModal.proj
      this.$http.delete(`/api/prep-docs-bg-tasks/${project.id}/`).then(_ => {
        this.runningBgTasks.delete(project.id)
      }).catch(exc => {
        console.warn(exc)
      }).finally(_ => {
        this.select({}, {item: project})
        this.cancelRunningBgTaskModal = null
      })
    },
    pollDocPrepStatus () {
      this.$http.get('/api/prep-docs-bg-tasks/').then(resp => {
        this.completeBgTasks = new Set(resp.data.comp_tasks.map(d => d.project))
        const newRunningTasks = new Set([
          ...this.runningBgTasks,
          ...resp.data.running_tasks.map(d => d.project)
        ])
        for (const completedTask of this.completeBgTasks) {
          newRunningTasks.delete(completedTask)
        }
        this.runningBgTasks = newRunningTasks
      })
      setTimeout(this.pollDocPrepStatus, 8000)
    }
  }
}
</script>

<style scoped lang="scss">
@import '@/styles/project-list-filters';

.project-list-no-data {
  padding: 24px;
  text-align: center;

  p {
    margin-bottom: 12px;
  }
}

#projectTable {
  :deep(.v-table__wrapper) {
    overflow-x: hidden;
  }

  :deep(table) {
    table-layout: fixed;
    width: 100%;
  }

  :deep(thead th),
  :deep(tbody td) {
    text-align: left !important;
  }

  :deep(thead th) {
    vertical-align: bottom;
    padding: 4px 6px;
    font-size: 0.8rem;
    overflow: hidden;
  }

  :deep(tbody td) {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: 0.85rem;
    padding: 4px 6px !important;
    vertical-align: middle;
  }

  :deep(td.progress-cell) {
    white-space: normal;
    overflow: visible;
  }

  :deep(th.icon-cell),
  :deep(td.icon-cell) {
    overflow: visible;
    text-overflow: clip;
    text-align: left !important;
    vertical-align: middle;
    white-space: nowrap;
  }

  :deep(th.header-wrap-cell) {
    overflow: visible;
    white-space: normal;
    vertical-align: bottom;
  }

  :deep(td.icon-cell .btn) {
    padding: 2px 8px;
    line-height: 1.2;
  }

  :deep(.col-hide-narrow) {
    @media (max-width: 1400px) {
      display: none !important;
    }
  }

  :deep(.col-hide-medium) {
    @media (max-width: 1100px) {
      display: none !important;
    }
  }
}

.date-cell {
  font-size: 0.8rem;
}

.status-cell {
  text-align: left;
}

.status-unlocked {
  text-align: left;
  color: $color-1;
  padding: 0;
  opacity: .5;
}

.status-locked {
  @extend .status-unlocked;
  opacity: 1;
  color: $danger;
}

.project-table {
  height: calc(100% - 30px);
  padding: 10px 0;
  width: 96%;
  max-width: 96%;
  margin: 0 auto;
}

.table-container {
  height: calc(100% - 125px);
  overflow-y: auto;
  overflow-x: hidden;
  max-width: 100%;
  margin: 0 auto;
}

.complete-project, .success {
  color: $success;
  font-size: 1.1rem;
}

.danger {
  color: $danger;
  font-size: 1.1rem;
}

#projectTable :deep(td.icon-cell .status-cell) {
  font-size: 1.1rem;
  display: inline-block;
}

.model-up {
  position: relative;
  &:hover {
    cursor: initial !important;
  }
}

.clear-model-cache {
  font-size: 15px;
  color: $task-color-2;
  cursor: pointer;
  position: absolute;
  right: -5px;
  top: -5px;
}

.selected-project {
  font-size: 15px;
  color: green;
  position: relative;
  right: -40px;
  top: -10px;
}

.load-metrics {
  padding: 0 5px;

}


.submit-report-job-alert {
  text-align: right;
}

.term-list {
  display: block;
  max-width: 100%;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.run-model {
  position: relative;
}

.model-bg-run-comp {
  color: $success;
  font-size: 15px;
  position: absolute;
  right: -5px;
  top: -5px;
}

.cancel-dialog-body {
  padding-top: 10px;
}

.v-table > .v-table__wrapper > table > tbody > tr > td,
.v-table > .v-table__wrapper > table > tbody > tr > th,
.v-table > .v-table__wrapper > table > thead > tr > td,
.v-table > .v-table__wrapper > table > thead > tr > th,
.v-table > .v-table__wrapper > table > tfoot > tr > td,
.v-table > .v-table__wrapper > table > tfoot > tr > th {
  padding: 0 4px !important;
}

.v-progress-linear.animate .v-progress-linear__determinate
{
  animation: move 5s linear infinite;
}
@keyframes move {
  0% {
    background-position: 0 0;
  }
  100% {
    background-position: 100px 100px;
  }
}

:deep(.v-table > .v-table__wrapper > table > tbody > tr.disabled-row) {
  pointer-events: none;
  opacity: 0.5;
  background-color: #f0f0f0;
}
</style>
