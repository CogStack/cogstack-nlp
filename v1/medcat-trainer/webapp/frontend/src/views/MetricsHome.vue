<template>
  <div class="full-height metrics-reports-table">
    <v-data-table :items="reports.items"
                  :headers="reports.headers"
                  :hover="true"
                  @click:row="loadMetrics"
                  hide-default-footer
                  :items-per-page="-1">
      <template #item.projects="{ item }" >
        <div @click.stop>
          <v-runtime-template :template="projectsFormatter(item.projects)"></v-runtime-template>
        </div>
      </template>

      <template #item.status="{ item }">
        <span v-if="item.status === 'pending'">Pending
          <font-awesome-icon icon="fa-regular fa-clock" class="status-icon"></font-awesome-icon>
        </span>
        <span v-if="item.status === 'running'">Running
          <font-awesome-icon icon="spinner" spin class="status-icon"></font-awesome-icon>
        </span>
        <span v-if="item.status === 'complete'">Complete
          <font-awesome-icon icon="check" class="status-icon success"></font-awesome-icon>
        </span>
      </template>
      <template #item.cleanup="{ item }">
        <div @click.stop>
          <button class="btn btn-outline-danger" @click="confDeleteReportModal = item"
                  :disabled="item.status === 'pending' || item.status === 'running'">
              <font-awesome-icon icon="times"></font-awesome-icon>
          </button>
        </div>
      </template>
    </v-data-table>

    <v-overlay :model-overlay="loadingReports">
      <v-progress-circular indeterminate color="'primary'"></v-progress-circular>
      <span class="overlay-message">Loading Metrics Reports...</span>
    </v-overlay>

    <modal v-if="confDeleteReportModal" :closable="true" @modal:close="confDeleteReportModal = null">
      <template #header>
        <h3>Confirm Delete Metrics Report</h3>
      </template>
      <template #body>
        <div v-if="confDeleteReportModal.status === 'running'">
          Metrics report still running, this will cancel the running metrics report running job
        </div>
        <div v-if="confDeleteReportModal.status === 'complete'">
          Confirm complete metrics report deletion. To regenerate the report reselect the projects on the
          home screen and select metrics.
        </div>
      </template>
      <template #footer>
        <button class="btn btn-danger" @click="confRemoval">Confirm</button>
      </template>
    </modal>

  </div>
</template>

<script>
import VRuntimeTemplate from 'vue3-runtime-template'
import Modal from '@/components/common/Modal.vue'

export default {
  name: "MetricsHome",
  components: {Modal, VRuntimeTemplate,},
  props: {
  },
  data () {
    return {
      loadingReports: false,
      confDeleteReportModal: null,
      projects: {},
      reports: {
        items: [],
        headers: [
          { value: 'report_id', title: 'ID' },
          { value: 'report_name', title: 'Report Name' },
          { value: 'created_user', title: 'Created User' },
          { value: 'create_time', title: 'Create Time' },
          { value: 'projects', title: 'Projects' },
          { value: 'status', title: 'Status' },
          { value: 'cleanup', title: 'Remove' }
        ]
      }
    }
  },
  created () {
    this.loadingReports = true
    this.pollReportStatus()
  },
  methods: {
    pollReportStatus () {
      this.$http.get('/api/metrics-job/').then(resp => {
        this.loadingReports = false
        this.reports.items = resp.data.reports.map(i => {
          const item = {...i}
          item.report_name = item.report_name || item.report_name_generated
          return item
        })
        this.fetchProjects()
        setTimeout(this.pollReportStatus, 5000)
      })
    },
    fetchProjects () {
      this.reports.items.forEach(item => {
        item.projects.forEach(projId => {
          if (!Object.keys(this.projects).includes(projId)) {
            this.$http.get(`/api/project-annotate-entities/${projId}/`).then(resp => {
              this.projects[projId] = resp.data
            })
          }
        })
      })
    },
    loadMetrics (_, { item }) {
      this.$router.push({
        name: 'metrics',
        params: {
          reportId: item.report_id
        }
      })
    },
    confRemoval () {
      const item = this.confDeleteReportModal
      this.$http.delete(`/api/metrics-job/${this.confDeleteReportModal.report_id}/`).then(_ => {
        this.confDeleteReportModal = null
        this.reports.items.splice(item)
      }).finally(() => {
        this.confDeleteReportModal = null
      })
    },
    projectsFormatter (value) {
      let outEl = ''
      value.forEach(i => {
        if (this.projects[i]) {
          outEl += `
          <div>
            <router-link :to="{ name: 'train-annotations', params: { projectId: '${i}' }}">${this.projects[i].name}</router-link>
          </div>`
        } else {
          outEl += `
            <div>
              ${i} <font-awesome-icon icon="spinner" spin></font-awesome-icon>
            </div>`
        }
      })
      return `<div>${outEl}</div>`
    }
  }
}
</script>

<style scoped lang="scss">
.metrics-reports-table {
  padding: 10px 0;
  width: 95%;
  margin: auto;
  height: calc(100% - 100px);
  overflow-y: auto;
}

.status-icon {
  padding-left: 3px;
}

.project-links {
  color: #005EB8;

  &:hover {
    color: #fff;
    border-bottom: 1px solid #fff;
  }
}

</style>
