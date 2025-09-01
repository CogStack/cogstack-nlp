<template>
  <div class="container-fluid cdb-view">
    <div class="l-sidebar">
      <div class="form-group">
        <label class="title">Concept Database Models</label>
        <select class="form-control" v-model="selectedConceptDB">
          <option :value="cdb" v-for="cdb of cdbs" :key="cdb.id">{{cdb.name}}</option>
        </select>
      </div>
      <div v-if="selectedConceptDB" class="form-group concept-search">
        <concept-picker :restrict_concept_lookup="false"
                        :cui_filter="[]"
                        :cdb_search_filter="[selectedConceptDB.id]"
                        :concept_db="selectedConceptDB.id"
                        @pickedResult:concept="pickedResult">
        </concept-picker>
      </div>
      <div class="title">Concept Filter</div>
      <div class="filter-desc">Selected Concepts:
        <span class="filter-text">{{filterLen}}</span>
      </div>
      <div class="selected-nodes">
        <div class="filter-desc" v-for="node of checkedNodes" :key="node.name" @click="toggleNodeChildViz(node.cui)">
          <font-awesome-icon class="ch-toggle" v-if="nodeChildOpen.indexOf(node.cui) !== -1" icon="chevron-down"/>
          <font-awesome-icon class="ch-toggle" v-else icon="chevron-right"/>
          <div class="selected-node">{{node.pretty_name}} <span class="sctid">- {{node.cui}}</span></div>
          <font-awesome-icon icon="times" class="remove-selected-node" @click.stop @click="removeNode(node)"/>
          <div v-if="nodeChildOpen.indexOf(node.cui) !== -1" @click.stop class="filter-ch-node" v-for="childNode of generatedFilter[node.cui]"
               @click="toggleExcludedCUI(childNode.cui)">
            <div class="node-icon-container">
              <font-awesome-icon icon="fa-regular fa-square-check" class="ch-node-icon" v-if="excludedNodes.indexOf(childNode.cui) === -1" />
              <font-awesome-icon icon="fa-regular fa-square" class="ch-node-icon" v-else />
            </div>
            <span class="selected-node">
              {{childNode.pretty_name}} <span class="sctid">- {{childNode.cui}}</span>
            </span>
          </div>
        </div>
      </div>
      <div id="concept-filter" class="concept-filter-footer">
        <button :disabled="filterLen === 0" class="btn btn-danger clear-filter" @click="clearFilter">Clear Filter</button>
        <button :disabled="exportingFilter || filterLen === 0" id="export-filter-btn" class="btn btn-primary export-filter" @click="exportFilter">
          <span v-if="!exportingFilter">Export Filter</span>
          <font-awesome-icon v-if="exportingFilter" icon="spinner" spin size="xs" />
        </button>
        <v-tooltip>
          Calculate all child concepts and download as a .json file - to upload into a Trainer project
        </v-tooltip>
      </div>
    </div>
    <div class="view-port">
      <concept-database-viz v-if="selectedConceptDB !== null" :cdb="selectedConceptDB"
                            :checkedNodes="checkedNodes"
                            :selectedCui="selectedCui"
                            @select:node="selectNode">
      </concept-database-viz>
    </div>
  </div>
</template>

<script>
import _ from "lodash"
import ConceptDatabaseViz from '@/components/models/ConceptDatabaseViz.vue'
import ConceptPicker from '@/components/common/ConceptPicker.vue'

export default {
  name: 'ConceptDatabase',
  components: { ConceptPicker, ConceptDatabaseViz },
  data () {
    return {
      cdbs: [],
      selectedConceptDB: null,
      checkedNodes: [],
      selectedCui: '',
      filterLen: 0,
      generatedFilter: {},
      nodeChildOpen: [],
      excludedNodes: [],
      exportingFilter: false
    }
  },
  created () {
    let cdbList = []
    let that = this
    const baseUrl = '/api/concept-dbs/'
    let getCDBs = function (url) {
      that.$http.get(url).then(resp => {
        if (!resp.data.next) {
          that.cdbs = cdbList.concat(_.uniqBy(resp.data.results, r => r.id))
        } else {
          const nextUrl = `${baseUrl}?${resp.data.next.split('?').slice(-1)}`
          cdbList = cdbList.concat(_.uniqBy(resp.data.results, r => r.id))
          getCDBs(nextUrl)
        }
      })
    }
    getCDBs(baseUrl)
  },
  methods: {
    pickedResult (res) {
      // picked result is used to search upwards to find path to root. via backend...
      if (res) {
        this.selectedCui = res.cui
      }
    },
    selectNode (node) {
      const idxOf = this.checkedNodes.indexOf(node)
      if (idxOf === -1) {
        this.checkedNodes.push(node)
        this.nodeChildOpen.push(node.cui)
        this.generateFilter()
      }
    },
    removeNode (nodeToggled) {
      const idxOf = this.checkedNodes.indexOf(nodeToggled)
      this.checkedNodes.splice(idxOf, 1)
      this.generateFilter()
    },
    generateFilter () {
      const payload = this.checkedNodes.map(r => r.cui)
      this.$http.post('/api/generate-concept-filter/',
        { 'cuis': payload, 'cdb_id': this.selectedConceptDB.id }).then(resp => {
        this.generatedFilter = resp.data.filter
        this.filterLen = resp.data.filter_len
      })
    },
    clearFilter () {
      this.checkedNodes = []
      this.filterLen = 0
      this.generatedFilter = {}
      this.excludedNodes = []
      this.nodeChildOpen = []
    },
    toggleNodeChildViz (cui) {
      const idxOf = this.nodeChildOpen.indexOf(cui)
      if (idxOf === -1) {
        this.nodeChildOpen.push(cui)
      } else {
        this.nodeChildOpen.splice(idxOf, 1)
      }
    },
    toggleExcludedCUI (cui) {
      const idxOf = this.excludedNodes.indexOf(cui)
      if (idxOf === -1) {
        this.excludedNodes.push(cui)
        this.recalcFilterLen()
      } else {
        this.excludedNodes.splice(idxOf, 1)
        this.recalcFilterLen()
      }
    },
    recalcFilterLen () {
      this.filterLen = _.keys(this.generatedFilter).concat(
        _.flatten(_.values(this.generatedFilter))
          .map(i => i.cui)
          .filter(i => this.excludedNodes.indexOf(i) === -1)
      ).length
    },
    exportFilter () {
      const payload = {
        'cuis': this.checkedNodes.map(r => r.cui),
        'cdb_id': this.selectedConceptDB.id,
        'excluded_nodes': this.excludedNodes
      }
      this.exportingFilter = true
      this.$http.post('/api/generate-concept-filter-json/', payload).then(resp => {
        const url = window.URL.createObjectURL(new Blob([JSON.stringify(resp.data)], {type: 'application/json'}))
        const link = document.createElement('a')
        link.href = url
        link.download = resp.headers['content-disposition'].split('=')[1]
        link.click()
        this.exportingFilter = false
      })
    }
  }
}
</script>

<style scoped lang="scss">
.cdb-view {
  height: calc(100% - 71px);
  display: flex;
}

.filter-desc {
  padding: 5px 5px;
}

.view-port {
  flex: 1 1 auto;
  display: flex;
}

.l-sidebar {
  display: flex;
  flex-direction: column;
  flex: 0 0 450px;
  height: 100%;

  .form-group {
    width: 95%;
  }

  div {
    flex-direction: row;
    flex: 0 0 42px;
  }

  div.selected-nodes {
    flex: 1 1 auto;
    overflow-y: auto;
    box-shadow: 0 5px 5px -5px rgba(0,0,0,0.2);
  }

  .filter-text {
    padding: 10px 10px 0 0;
  }

  .clear-filter {
    margin: 10px 10px 0 0;
  }

  .export-filter {
    float: right;
    margin: 10px 10px 0 0;
  }
}

.selected-node {
  display: inline-block;
  width: calc(100% - 20px - 25px); /** icons either site **/
}

.ch-toggle {
  width: 20px;
  padding-right: 2px;
}

.filter-ch-node {
  padding-left: 15px;
  margin: 1px;
  &:hover {
    box-shadow: rgba(149, 157, 165, 0.2) 0 8px 24px;
    cursor: pointer;
  }

  .ch-node-icon {
    padding-right: 2px;
  }
}

.sctid {
  opacity: .4;
}

.node-icon-container {
  display: inline-block;
  vertical-align: center;
  font-size: 18px;
  padding-right: 3px;
}

.remove-selected-node {
  width: 20px;
  display: inline-block;
  color: $danger;

  &:hover {
    cursor: pointer;
  }
}

</style>
