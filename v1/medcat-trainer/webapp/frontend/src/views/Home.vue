<template>
  <div class="full-height">
    <login v-if="!loginSuccessful" @login:success="loggedIn()"></login>
    <transition name="alert"><div class="alert alert-danger" v-if="routeAlert" role="alert">{{routeAlert}}</div></transition>
    <div class="view-bar" v-if="isAdmin">
      <button class="btn btn-outline-primary" @click="projectGroupView = !projectGroupView">
        <span v-if="projectGroupView">Single Projects</span>
        <span v-if="!projectGroupView">Project Groups</span>
      </button>
    </div>
    <div v-if="projectGroupView" class="full-height project-group-table">
      <v-data-table id="projectGroupTable" :items="projectGroups.items"
                    :headers="projectGroups.headers"
                    :hover="true"
                    v-if="!loadingProjects"
                    color="primary"
                    @click:row="selectProjectGroup"
                    hide-default-footer
                    :items-per-page="-1">
        <template v-slot:item.last_modified="{ item }">
          {{new Date(item.last_modified).toLocaleString()}}
        </template>
      </v-data-table>
      <modal v-if="selectedProjectGroup" :closable="true" @modal:close="selectedProjectGroup = null" class="summary-modal">
        <template #header>
          <h3>Project Group: {{selectedProjectGroup.name}}</h3>
          <br>
          <p>{{selectedProjectGroup.description}}</p>
        </template>
        <template #body>
          <project-list :project-items="selectedProjectGroup.items" :is-admin="isAdmin"
                        :cdb-search-index-status="cdbSearchIndexStatus"></project-list>
        </template>
      </modal>
    </div>
    <project-list v-if="!projectGroupView" :project-items="projects.items" :is-admin="isAdmin"
                  :cdb-search-index-status="cdbSearchIndexStatus"></project-list>
  </div>

</template>
<script>
import _ from 'lodash'

import Modal from '@/components/common/Modal.vue'
import Login from '@/components/common/Login.vue'
import EventBus from '@/event-bus'
import ProjectList from "@/components/common/ProjectList.vue"


export default {
  name: 'Home',
  components: {
    ProjectList,
    Login,
    Modal
  },
  data () {
    return {
      projectGroupView: false,
      projectGroups: {
        items: [],
        headers: [
          { value: 'name', title: 'Name' },
          { value: 'description', title: 'Description' },
          { value: 'last_modified', title: 'Last Modified' }
        ]
      },
      projects: {
        items: []
      },
      routeAlert: false,
      loginSuccessful: false,
      loadingProjects: false,
      isAdmin: false,
      selectedProjectGroup: null,
      cdbSearchIndexStatus: {}
    }
  },
  created () {
    this.loggedIn()
  },
  watch: {
    '$route': 'loggedIn'
  },
  mounted () {
    EventBus.$on('login:success', this.loggedIn)
  },
  beforeDestroy () {
    EventBus.$off('login:success')
  },
  methods: {
    loggedIn () {
      this.$http.get('/api/behind-rp/').then(resp => {
        if (!resp.data && this.$route.path !== '/') {
          this.routeAlert = `Invalid URL: ${this.$route.path}, redirected to the MedCAT Home page.`
          const that = this
          setTimeout(() => {
            that.routeAlert = false
          }, 5000)
        }
      })
      // assume if there's an api-token we've logged in before and will try get projects
      // fallback to logging in otherwise
      if (this.$cookies.get('api-token')) {
        this.loginSuccessful = true
        this.isAdmin = this.$cookies.get('admin') === 'true'
        this.fetchProjects()
      }
    },
    fetchProjectGroups () {
      const projectGroupIds = new Set(this.projects.items.filter(p => p.group !== null).map(p => p.group))
      this.$http.get(`/api/project-groups/?id__in=${Array.from(projectGroupIds).join(',')}`).then(resp => {
        this.projectGroups.items = resp.data.results
      })
    },
    fetchProjects () {
      this.loadingProjects = true
      if (this.loginSuccessful) {
        this.$http.get('/api/project-annotate-entities/').then(resp => {
          this.projects.items = resp.data.results
          if (resp.data.next) {
            this.fetchPage(resp.data.next)
          } else {
            this.postLoadedProjects()
          }
        }).catch(() => {
          this.$cookies.remove('username')
          this.$cookies.remove('api-token')
          this.$cookies.remove('admin')
          this.$cookies.remove('user-id')
          this.loadingProjects = false
          this.loginSuccessful = false
        })
      }
    },
    fetchPage (pageUrl) {
      this.$http.get('/' + pageUrl.split('/').slice(-3).join('/')).then(resp => {
        this.projects.items = this.projects.items.concat(resp.data.results)
        if (resp.data.next) {
          this.fetchPage(resp.data.next)
        } else {
          this.postLoadedProjects()
        }
      })
    },
    postLoadedProjects () {
      this.fetchSearchIndexStatus()
      this.fetchProjectProgress()
      this.fetchProjectGroups()
      this.loadingProjects = false
    },

    fetchSearchIndexStatus () {
      const cdbIds = _.uniq(this.projects.items.map(p => p.cdb_search_filter[0])).filter(id => id)
      this.$http.get(`/api/concept-db-search-index-created/?cdbs=${cdbIds.join(',')}`).then(resp => {
        this.cdbSearchIndexStatus = resp.data.results
      }).catch(err => {
        console.log(err)
      })
    },
    fetchProjectProgress () {
      const projectIds = this.projects.items.map(p => p.id)
      if (projectIds.length > 0) {
        this.$http.get(`/api/project-progress/?projects=${projectIds}`).then(resp => {
          this.projects.items = this.projects.items.map(item => {
            item['progress'] = resp.data[item.id].validated_count
            item['progress_max'] = resp.data[item.id].dataset_count
            return item
          })
        })
      }
    },
    selectProjectGroup(_, { item }) {
      if (item) {
        this.selectedProjectGroup = item
        this.selectedProjectGroup.items = this.projects.items.filter(p => p.group === this.selectedProjectGroup.id)
      }
    }
  }
}
</script>

<style lang="scss">
h3 {
  margin: 10%
}

.view-bar {
  height: 30px;
  padding: 5px 0;
  width: 95%;
  margin: auto;
}

.project-group-table {
  height: calc(100% - 30px);
  padding: 10px 0;
  width: 95%;
  margin: auto;
}


.home-title {
  font-size: 23px;
  padding: 30px 0;
}



</style>
