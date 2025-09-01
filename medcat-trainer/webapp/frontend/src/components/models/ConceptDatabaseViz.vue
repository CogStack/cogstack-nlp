<template>
  <div class="mc-tree-container">
    <div class="zoom-controls">
      <button class="btn btn-default" @click="zoomIn"><font-awesome-icon icon="plus"></font-awesome-icon></button>
      <button  class="btn btn-default" @click="zoomOut"><font-awesome-icon icon="minus"></font-awesome-icon></button>
      <button class="btn btn-default" @click="resetZoom">1:1</button>
    </div>
    <v-overlay :model-value="loading"
               class="align-center justify-center"
               color="primary"
               activator="parent"
               :disabled="true"
               :persistent="true">
      <v-progress-circular indeterminate color="'primary'"></v-progress-circular>
      <span class="overlay-message">Retrieving Concept Tree...</span>
    </v-overlay>
    <div class="mc-tree-view">
      <vue-tree
        style="width: 1500px; height: 1000px;"
        :dataset="cdbData"
        :config="treeConfig"
        :direction="'vertical'"
        :linkStyle="'straight'"
        ref="tree">
        <template v-slot:node="{ node, collapsed }">
          <div @click="getData(node)" class="node">
            {{ node.pretty_name }} - {{ node.cui }}
            <button @click.stop.prevent class="btn btn-outline select-node-btn" @click="selectNode(node)">
              <font-awesome-icon icon="chevron-right"></font-awesome-icon>
            </button>
          </div>
        </template>
      </vue-tree>
    </div>
  </div>
</template>

<script>
import VueTree from '@/components/models/VueTree.vue'
import _ from 'lodash'

export default {
  name: 'ConceptDatabaseViz',
  components: { VueTree },
  props: {
    cdb: Object,
    selectedCui: String
  },
  emits: [
    'select:node'
  ],
  data () {
    return {
      CDB: {},
      cdbData: {},
      nodeCuis: [],
      loading: false,
      treeConfig: { nodeWidth: 120, nodeHeight: 150, levelHeight: 150 },
      zoomSetting: 0
    }
  },
  created () {
    this.loading = true
    this.$http.get(`api/model-concept-children/${this.cdb.id}/`).then(resp => {
      const rootTerm = resp.data.results[0]
      this.cdbData = {
        pretty_name: rootTerm.pretty_name,
        cui: rootTerm.cui,
        _key: rootTerm.cui
      }
      this.getData(this.cdbData)
    })
  },
  mounted () {
    this.debouncedScroll = _.debounce(this.onScroll, 100)
    window.addEventListener('scroll', this.debouncedScroll)
  },
  beforeDestroy () {
    window.removeEventListener('scroll', this.debouncedScroll)
  },
  methods: {
    getData (node) {
      if (this.nodeCuis.indexOf(node.cui) === -1 || node.complete) {
        this.$http.get(`api/model-concept-children/${this.cdb.id}/?parent_cui=${node.cui}`).then(resp => {
          this.loading = false
          node.children = resp.data.results.map(r => {
            return {
              pretty_name: r.pretty_name,
              cui: r.cui,
              _key: r.cui
            }
          })
          this.nodeCuis.push(node.cui)
        })
      }
    },
    selectNode (node) {
      this.$emit('select:node', node)
    },
    onScroll (e) {
      if (this.zoomSetting < e.scrollY) {
        this.zoomOut()
      } else {
        this.zoomIn()
      }
      this.zoomSetting = e.scrollY
    },
    zoomOut () {
      this.$refs.tree.zoomOut()
    },
    zoomIn () {
      this.$refs.tree.zoomIn()
    },
    resetZoom () {
      this.$refs.tree.restoreScale()
    }
  },
  watch: {
    selectedCui (newVal) {
      if (newVal) {
        this.$http.get(`api/concept-path/?cdb_id=${this.cdb.id}&cui=${newVal}`).then(resp => {
          this.cdbData.children = resp.data.results['node_path'].children
          this.cdbData.links = resp.data.results['links']
          this.cdbData.identifier = 'cui'
        })
      }
      this.nodeCuis.push(newVal)
      this.loading = false
    }
  }
}
</script>

<style scoped lang="scss">
.mc-tree-container {
  flex: 1 1 auto;
  overflow-y: auto;
  background: rgba(0, 114, 206, .2);
  padding: 40px 40px 0 40px;
  border-radius: 10px;
  height: 100%;
}

.mc-tree-view {
  background: white;
  overflow-y: auto;
  height: 100%;
  box-shadow: 0 -2px 3px 2px rgba(0, 0, 0, 0.2);
  padding: 25px;
  white-space: pre-wrap;
}

.node {
  width: 260px;
  padding: 3px;
  display: flex;
  flex-direction: row;
  align-items: flex-start;
  justify-content: center;
  font-size: .8rem;
  color: $color-2;
  background-color: $task-color-0;
  opacity: 1;
  border-radius: 3px;
  margin: 3px;
  box-shadow: 0 5px 5px -5px $task-color-0;
}

.zoom-controls {
  position: absolute;
  right: 0;
}

.select-node-btn {
  position: absolute;
  right: 0;
  width: 20px;
}
</style>
