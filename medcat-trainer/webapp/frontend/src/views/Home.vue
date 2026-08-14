<template>
  <div class="full-height home-page">
    <login v-if="!loginSuccessful" @login:success="loggedIn()"></login>
    <transition name="alert"><div class="alert alert-danger" v-if="routeAlert" role="alert">{{routeAlert}}</div></transition>
    <div v-if="isAdmin && loginSuccessful" class="home-tabs">
      <button
        type="button"
        class="tab-button"
        :class="{ active: !projectGroupView }"
        @click="projectGroupView = false">
        <font-awesome-icon icon="folder"></font-awesome-icon>
        Projects
      </button>
      <button
        type="button"
        class="tab-button"
        :class="{ active: projectGroupView }"
        @click="projectGroupView = true">
        <font-awesome-icon icon="layer-group"></font-awesome-icon>
        Project Groups
      </button>
    </div>
    <div class="home-content">
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
          </template>
          <template #body>
            <project-list :project-items="selectedProjectGroup.items" :is-admin="isAdmin"
                          :cdb-search-index-status="cdbSearchIndexStatus"></project-list>
          </template>
        </modal>
      </div>
      <project-list v-if="!projectGroupView" :project-items="projects.items" :is-admin="isAdmin"
                    :cdb-search-index-status="cdbSearchIndexStatus"></project-list>
      <plugin-slot name="home:after-projects" />
    </div>
  </div>

</template>
<script>
import _ from 'lodash'

import Modal from '@/components/common/Modal.vue'
import Login from '@/components/common/Login.vue'
import EventBus from '@/event-bus'
import ProjectList from "@/components/common/ProjectList.vue"
import { isOidcEnabled } from '../runtimeConfig';

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
      cdbSearchIndexStatus: {},
      useOidc: isOidcEnabled()
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
      if (!this.useOidc && this.$cookies.get('api-token')) {
          this.loginSuccessful = true
          this.isAdmin = this.$cookies.get('admin') === 'true'
          this.fetchProjects()
      } else if (this.useOidc && this.$keycloak && this.$keycloak.authenticated) {
          this.loginSuccessful = true
          this.isAdmin = (this.$keycloak.tokenParsed?.realm_access?.roles ?? []).includes('medcattrainer_superuser')
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
        }).catch((err) => {
          this.loadingProjects = false
          // 401: httpAuth interceptor already clears cookie + Authorization together
          // and opens the re-login prompt. Do not wipe cookies on other failures —
          // that left Authorization in memory while removing the cookie, so the tab
          // still sent a token until refresh forced an unexplained re-login.
          if (err.response?.status === 401) {
            this.loginSuccessful = false
          }
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

<style scoped lang="scss">
@import '@/styles/variables.scss';

.home-page {
  display: flex;
  flex-direction: column;
}

.home-tabs {
  display: flex;
  gap: 8px;
  width: 96%;
  margin: 8px auto 0;
  border-bottom: 2px solid var(--color-border);
  padding-bottom: 0;
  flex-shrink: 0;
}

.tab-button {
  padding: 10px 20px;
  background: transparent;
  border: none;
  border-bottom: 3px solid transparent;
  cursor: pointer;
  font-size: 0.95rem;
  font-weight: 500;
  color: var(--color-text-secondary);
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: -2px;

  &:hover {
    color: var(--color-primary, $primary);
    background: rgba(0, 0, 0, 0.02);
  }

  &.active {
    color: var(--color-primary, $primary);
    border-bottom-color: var(--color-primary, $primary);
    font-weight: 600;
  }
}

.home-content {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.project-group-table {
  height: 100%;
  padding: 10px 0;
  width: 96%;
  margin: 0 auto;
}

.home-title {
  font-size: 23px;
  padding: 30px 0;
}
</style>
