<template>
  <div class="doc-summary">
    <div class="title">
      Clinical Notes
      <font-awesome-icon icon="search" class="search-icon" @click="activateSearch"></font-awesome-icon>
    </div>
    <div v-if="searching" class="search-docs">
      <input id="doc-search-input" type="text" class="form-control" placeholder="Search by note name"
             :value="searchCrit" @keyup="searchDocs">
    </div>
    <div v-if="loadingDoc" class="loading-doc"></div>

    <div id="doc-sum-list" class="doc-list">
      <div v-for="doc of (searchCrit ? filteredDocs : docs)" :key="doc.id" class="doc clickable"
           :class="{'selected-doc': selectedDocId === doc.id}" @click="loadDoc(doc)">
        <font-awesome-icon :id="'doc-sub-' + doc.id"
                           v-if="validatedDocIds.includes(doc.id)"
                           class="validated-doc" icon="check"></font-awesome-icon>
        <font-awesome-icon :id="'doc-prep-' + doc.id"
                           v-if="preparedDocIds.includes(doc.id)"
                           class="prepared-doc"
                           icon="clipboard-check"></font-awesome-icon>

        <div class="note-summary">
          {{doc.text === 'nan' ? '' : (limitText(doc.text) || '')}}
        </div>
        <v-tooltip activator="parent"
                   v-if="preparedDocIds.includes(doc.id) || completeBgTasks                                   .includes(doc.id)">
          Predictions ready for Doc: {{doc.id}}
        </v-tooltip>
        <v-tooltip activator="parent"
                   v-if="validatedDocIds.includes(doc.id)">
          Doc: {{doc.id}} complete
        </v-tooltip>
      </div>
      <div class="clickable">
        <div v-if="moreDocs" @click="loadMoreDocs" class="more-docs">
          <font-awesome-icon icon="plus" class="icon"></font-awesome-icon>More Docs
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'DocumentSummary',
  props: {
    projId: Number,
    docs: Array,
    moreDocs: Boolean,
    selectedDocId: Number,
    loadingDoc: Boolean,
    validatedDocIds: Array,
    preparedDocIds: Array
  },
  emits: [
    'request:nextDocSet',
    'request:loadDoc'
  ],
  data () {
    return {
      searching: false,
      filteredDocs: [],
      searchCrit: null,
      hoverDoc: null,
      completeBgTasks: [],
      runningBgTasks: []
    }
  },
  methods: {
    scrollSelectedDocId () {
      const el = document.getElementsByClassName('selected-doc')
      if (el.length > 0) {
        el[0].scrollIntoView({
          block: 'center',
          behavior: 'smooth'
        })
      }
    },
    loadMoreDocs () {
      this.$emit('request:nextDocSet')
    },
    loadDoc (docId) {
      this.$emit('request:loadDoc', docId)
    },
    keyup (e) {
      if (!this.loadingDoc && e.keyCode === 40 && this.selectedDocId !== this.docs.slice(-1).id) {
        // down
        this.$emit('request:loadDoc', this.docs[this.docs.map(d => d.id).indexOf(this.selectedDocId) + 1])
        this.$nextTick(this.scrollSelectedDocId)
      } else if (!this.loadingDoc && e.keyCode === 38 && this.selectedDocId !== this.docs[0].id && !this.loadingDoc) {
        // up
        this.$emit('request:loadDoc', this.docs[this.docs.map(d => d.id).indexOf(this.selectedDocId) - 1])
        this.$nextTick(this.scrollSelectedDocId)
      }
    },
    activateSearch () {
      this.searching = !this.searching
      if (this.searching) {
        // keyboard focus on that element.
        setTimeout(function () {
          const el = document.getElementById('doc-search-input')
          el.focus()
        }, 50)
      } else {
        this.searchCrit = null
      }
    },
    searchDocs (event) {
      this.searchCrit = event.target.value
      if (this.searchCrit) {
        this.filteredDocs = this.docs.filter(d => {
          return d.name.toLowerCase().startsWith(this.searchCrit.toLowerCase())
        })
      } else {
        this.filteredDocs = []
      }
    },
    limitText (value) {
      value = value.trim()
      let splitText = value.split('\n')
      if (splitText.length > 5) {
        return splitText.slice(0, 5).join('\n')
      }
      return value
    }
  },
  mounted () {
    window.addEventListener('keyup', this.keyup)
  },
  beforeDestroy () {
    window.removeEventListener('keyup', this.keyup)
  },
}
</script>

<style scoped lang="scss">
@import "bootstrap";

$width: 175px;

.title {
  padding: 5px 10px;
  font-size: 16pt;
  box-shadow: 0 5px 5px -5px rgba(0,0,0,0.2);
}

.doc-summary {
  flex: 0 0 $width;
  padding: 5px;
  position: relative;
  background: $background;
}

.doc-list {
  overflow: auto;
  height: calc(100% - 41px);
  width: $width;
}

.doc {
  position: relative;
  padding: 5px 3px;
  border-radius: 5px;
  color: $color-5;
  margin: 15px 15px;
  box-shadow: 2px 1px 4px 3px rgba(0,0,0,0.2);

  &:hover {
    cursor: pointer;
  }
}

.prepared-doc {
  color: $color-1;
  position: absolute;
  font-size: 15px;
  left: -7px;
}

.selected-doc {
  border-left: 5px solid $primary;
}

.validated-doc {
  float: right;
  color: $success
}

.clickable {
  cursor: pointer;
}

.loading-doc {
  position: absolute;
  height: 100%;
  width: 100%;
  background: $loading-background-color;
  opacity: 0.3;
}

.more-docs {
  color: $primary;
  text-align: center;

  .icon {
    position: relative;
    bottom: 2px;
    padding-right: 3px;
  }
}

.note-summary {
  white-space: pre-wrap;
  font-size: 10px;
  overflow: hidden;
  position: relative;
  height: 6em; /* 5 lines */

  &:after {
    content: "";
    text-align: right;
    position: absolute;
    bottom: 0;
    right: 0;
    width: 80%;
    height: 1.2em;
  }
}

.search-icon {
  font-size: 10pt;
  vertical-align: center;
  opacity: 0.5;
  text-align: right;

  &:hover {
    opacity: 1;
  }
}

.search-docs {
  width: 100%;
}

</style>
