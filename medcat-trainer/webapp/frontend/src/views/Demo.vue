<template>
  <div class="container-fluid demo">
    <div class="demo-text">
      <form @submit.prevent>
        <div class="form-group">
          <label>Project Model:</label>
          <select class="form-control" v-model="selectedProject">
            <option :value="proj" v-for="proj of projects" :key="proj.id">{{proj.name}}
            </option>
          </select>
        </div>
        <div class="form-group">
          <label>Text to Annotate:</label>
          <textarea v-model="exampleText" class="form-control" name="text" rows="10"></textarea>
        </div>
        <div class="form-group">
          <label>CUI Filter</label>
          <textarea v-model="cuiFilters" class="form-control" name="cui"
                    rows="3" placeholder="Comma separated list: S-91175000, S-84757009"></textarea>
        </div>
        <button @click="annotate()" class="btn btn-primary">Annotate</button>
      </form>
    </div>
    <div class="view-port">
      <div class="clinical-text">
        <clinical-text :loading="loadingMsg" :text="annotatedText" :ents="ents"
                       :taskName="task" :taskValues="taskValues" @select:concept="selectEntity"></clinical-text>
      </div>
      <div class="sidebar">
        <concept-summary :selectedEnt="currentEnt" :project="selectedProject"
                         :searchFilterDBIndex="searchFilterDBIndex"></concept-summary>
      </div>
    </div>
  </div>
</template>

<script>
import ClinicalText from '@/components/common/ClinicalText.vue'
import ConceptSummary from '@/components/common/ConceptSummary.vue'

const TASK_NAME = 'Concept Anno'
const VALUES = ['Val']

export default {
  name: 'Demo',
  components: {
    ClinicalText,
    ConceptSummary
  },
  data () {
    return {
      exampleText: '',
      projects: [],
      selectedProject: {},
      cuiFilters: '',
      ents: [],
      currentEnt: {},
      annotatedText: '',
      loadingMsg: null,
      task: TASK_NAME,
      taskValues: VALUES,
      searchFilterDBIndex: null
    }
  },
  created () {
    let projectList = []
    let that = this
    const baseUrl = '/api/project-annotate-entities/'
    let getProjects = function (url) {
      that.$http.get(url).then(resp => {
        if (resp.data.count === (projectList.length + resp.data.results.length)) {
          that.projects = projectList.concat(resp.data.results)
        } else {
          const nextUrl = `${baseUrl}?${resp.data.next.split('?').slice(-1)}`
          projectList = projectList.concat(resp.data.results)
          getProjects(nextUrl)
        }
      })
    }
    getProjects(baseUrl)
  },
  methods: {
    annotate () {
      const payload = {
        project_id: this.selectedProject.id,
        message: this.exampleText,
        cuis: this.cuiFilters,
      }
      this.loadingMsg = 'Annotating Text...'
      this.$http.post('/api/annotate-text/', payload).then(resp => {
        this.loadingMsg = null
        this.ents = resp.data['entities'].map(e => {
          e.assignedValues = {}
          e.assignedValues[this.task] = this.taskValues[0]
          return e
        })
        this.currentEnt = this.ents.length > 0 ? this.ents[0] : null
        this.annotatedText = resp.data['message']
      })
    },
    selectEntity (entIndex) {
      this.currentEnt = this.ents[entIndex]
    },
    fetchCDBSearchIndex () {
      if (this.selectedProject.cdb_search_filter.length > 0) {
        this.$http.get(`/api/concept-dbs/${this.selectedProject.cdb_search_filter[0]}/`).then(resp => {
          if (resp.data) {
            this.searchFilterDBIndex = `${resp.data.name}_id_${this.selectedProject.cdb_search_filter}`
          }
        })
      }
    }
  },
  watch: {
    'selectedProject': {
      handler () {
        this.fetchCDBSearchIndex()
      }
    }
  }
}
</script>

<style scoped lang="scss">
.demo {
  height: calc(100% - 71px);
  display: flex;
}

.demo-text {
  flex-direction: column;
  flex: 0 0 400px;
  height: 100%;
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
  flex-direction: column;
  flex: 0 0 350px;
}

form {
  margin: 5%;
}
</style>
