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
                    :headers="isAdmin ? projects.headers : projects.headers.filter(f => projects.adminOnlyFields.indexOf(f.value) === -1)"
                    :items="projectItems"
                    :hover="true"
                    :items-per-page="-1"
                    :row-props="availableProjectForMetrics"
                    v-if="!loadingProjects"
                    @click:row="select"
                    hide-default-footer>
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
        <template #header.status>
          Project Status
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
        </template>
        <template #header.anno_class>
          Annotation Dataset
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
          {{new Date(item.last_modified).toLocaleString()}}
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
            height="30px"
            :max="item.progress_max">
             <span>{{item.progress}}</span> / <span>{{item.progress_max}}</span>
          </v-progress-linear>
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
      tableKey: 0,
      modelLoaded: {},
      projects: {
        headers: [
          { value: 'locked', title: ''},
          { value: 'id', title: 'ID' },
          { value: 'name', title: 'Title' },
          { value: 'description', title: 'Description' },
          { value: 'create_time', title: 'Create Time',},
          { value: 'last_modified', title: 'Last Modified' },
          { value: 'cuis', title: 'Concepts' },
          { value: 'require_entity_validation', title: 'Annotate / Validate' },
          { value: 'status', title: 'Status' },
          { value: 'progress', title: 'Progress' },
          { value: 'anno_class', title: 'Annotation Classification' },
          { value: 'cdb_search_filter', title: 'Concepts Imported' },
          { value: 'run_model', title: 'Run Model' },
          { value: 'model_loaded', title: 'Model Loaded' },
          { value: 'metrics', title: 'Metrics' },
          { value: 'save_model', title: 'Save Model' }
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
  created () {
    this.pollDocPrepStatus()
    this.fetchModelsLoaded()
  },
  methods: {
    clearLoadedModel (projectId) {
      this.clearModelModal = projectId
    },
    confirmClearLoadedModel (projectId) {
      this.clearModelModal = false
      this.$http.delete(`/api/cache-model/${projectId}/`).then(_ => {
        this.fetchModelsLoaded()
      })
    },
    loadProjectCDB (projectId) {
      this.loadingModel = projectId
      this.$http.get(`/api/cache-model/${projectId}/`).then(_ => {
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

.status-cell {
  text-align: center;
}

.status-unlocked {
  text-align: center;
  color: $color-1;
  padding: 0 5px;
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
  width: 95%;
  margin: auto;
}

.table-container {
  height: calc(100% - 125px);
  overflow-y: auto;
}

.complete-project, .success {
  color: $success;
  font-size: 20px;
}

.danger {
  color: $danger;
  font-size: 20px;
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
  max-width: 20vw;
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
