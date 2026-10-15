<template>
  <div class="doc-summary">
    <div class="title">
      Clinical Notes
      <font-awesome-icon icon="search" class="search-icon" @click="activateSearch"></font-awesome-icon>
    </div>
    <div v-if="searching" class="search-docs">
      <div class="search-mode">
        <button type="button" class="btn btn-sm search-mode-name"
                :class="searchMode === 'name' ? 'btn-primary' : 'btn-outline-primary'"
                @click="setSearchMode('name')">Name</button>
        <button type="button" class="btn btn-sm search-mode-text"
                :class="searchMode === 'text' ? 'btn-primary' : 'btn-outline-primary'"
                @click="setSearchMode('text')">Text</button>
      </div>
      <input id="doc-search-input" type="text" class="form-control"
             :placeholder="searchMode === 'text' ? 'Search note text' : 'Search by note name'"
             :value="searchCrit" @keyup="searchDocs">
      <div v-if="searchMode === 'text' && searchCrit" class="search-status">
        <span v-if="textSearchLoading">Searching...</span>
        <span v-else-if="textSearchError">{{ textSearchError }}</span>
        <span v-else>{{ textSearchCount }} matching note{{ textSearchCount === 1 ? '' : 's' }}</span>
      </div>
    </div>
    <div v-if="loadingDoc" class="loading-doc"></div>

    <div id="doc-sum-list" class="doc-list">
      <div v-for="doc of displayedDocs" :key="doc.id" class="doc clickable"
           :class="{'selected-doc': selectedDocId === doc.id}" @click="loadDoc(doc)">
        <font-awesome-icon :id="'doc-sub-' + doc.id"
                           v-if="validatedDocIds.includes(doc.id)"
                           class="validated-doc" icon="check"></font-awesome-icon>
        <font-awesome-icon :id="'doc-prep-' + doc.id"
                           v-if="preparedDocIds.includes(doc.id)"
                           class="prepared-doc"
                           icon="clipboard-check"></font-awesome-icon>

        <div v-if="textSnippet(doc)" class="note-summary"><span
            v-for="(seg, i) of textSnippet(doc)" :key="i"
            :class="{'search-match': seg.match}">{{ seg.text }}</span></div>
        <div v-else class="note-summary">
          {{doc.text === 'nan' ? '' : (limitText(doc.text) || '')}}
        </div>
        <v-tooltip activator="parent"
                   v-if="preparedDocIds.includes(doc.id) || completeBgTasks.includes(doc.id)">
          Predictions ready for Doc: {{doc.id}}
        </v-tooltip>
        <v-tooltip activator="parent"
                   v-if="validatedDocIds.includes(doc.id)">
          Doc: {{doc.id}} complete
        </v-tooltip>
      </div>
      <div class="clickable" v-if="isTextSearch">
        <div v-if="textSearchNextUrl && !textSearchLoading" @click="loadMoreTextResults" class="more-docs">
          <font-awesome-icon icon="plus" class="icon"></font-awesome-icon>More Results
        </div>
      </div>
      <div class="clickable" v-else>
        <div v-if="moreDocs" @click="loadMoreDocs" class="more-docs">
          <font-awesome-icon icon="plus" class="icon"></font-awesome-icon>More Docs
        </div>
      </div>
    </div>
  </div>
</template>

<script>
const TEXT_SEARCH_DEBOUNCE_MS = 300
const SNIPPET_CONTEXT_CHARS = 60

export default {
  name: 'DocumentSummary',
  props: {
    projId: Number,
    datasetId: Number,
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
      searchMode: 'name',
      filteredDocs: [],
      searchCrit: null,
      textSearchResults: [],
      textSearchCount: 0,
      textSearchNextUrl: null,
      textSearchLoading: false,
      textSearchError: null,
      textSearchTimer: null,
      textSearchReqId: 0,
      hoverDoc: null,
      completeBgTasks: [],
      runningBgTasks: []
    }
  },
  computed: {
    isTextSearch () {
      return this.searchMode === 'text' && !!this.searchCrit
    },
    displayedDocs () {
      if (!this.searchCrit) {
        return this.docs
      }
      return this.searchMode === 'text' ? this.textSearchResults : this.filteredDocs
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
        this.resetTextSearch()
      }
    },
    setSearchMode (mode) {
      if (this.searchMode === mode) {
        return
      }
      this.searchMode = mode
      this.runSearch()
    },
    searchDocs (event) {
      if (event.target.value === (this.searchCrit || '')) {
        // ignore keys that don't change the input, e.g. arrows used for doc navigation
        return
      }
      this.searchCrit = event.target.value
      this.runSearch()
    },
    runSearch () {
      this.resetTextSearch()
      if (!this.searchCrit) {
        this.filteredDocs = []
        return
      }
      if (this.searchMode === 'text') {
        this.textSearchLoading = true
        this.textSearchTimer = setTimeout(() => {
          this.textSearchTimer = null
          const params = new URLSearchParams({ dataset: this.datasetId, text: this.searchCrit })
          this.fetchTextResults(`/api/search-documents/?${params.toString()}`)
        }, TEXT_SEARCH_DEBOUNCE_MS)
      } else {
        this.filteredDocs = this.docs.filter(d => {
          return d.name.toLowerCase().startsWith(this.searchCrit.toLowerCase())
        })
      }
    },
    resetTextSearch () {
      if (this.textSearchTimer) {
        clearTimeout(this.textSearchTimer)
        this.textSearchTimer = null
      }
      this.textSearchReqId++
      this.textSearchResults = []
      this.textSearchCount = 0
      this.textSearchNextUrl = null
      this.textSearchLoading = false
      this.textSearchError = null
    },
    fetchTextResults (url) {
      const reqId = ++this.textSearchReqId
      this.textSearchLoading = true
      this.textSearchError = null
      this.$http.get(url).then(resp => {
        if (reqId !== this.textSearchReqId) {
          return
        }
        this.textSearchResults = this.textSearchResults.concat(resp.data.results)
        this.textSearchCount = resp.data.count
        this.textSearchNextUrl = resp.data.next
      }).catch(() => {
        if (reqId === this.textSearchReqId) {
          this.textSearchError = 'Search failed'
        }
      }).finally(() => {
        if (reqId === this.textSearchReqId) {
          this.textSearchLoading = false
        }
      })
    },
    loadMoreTextResults () {
      if (this.textSearchNextUrl) {
        this.fetchTextResults(`/api/search-documents/?${this.textSearchNextUrl.split('?').slice(-1)[0]}`)
      }
    },
    textSnippet (doc) {
      if (!this.isTextSearch) {
        return null
      }
      if (doc.highlight && doc.highlight.length) {
        return doc.highlight
      }
      if (!doc.text) {
        return null
      }
      const idx = doc.text.toLowerCase().indexOf(this.searchCrit.toLowerCase())
      if (idx === -1) {
        return null
      }
      const end = idx + this.searchCrit.length
      const start = Math.max(0, idx - SNIPPET_CONTEXT_CHARS)
      return [
        { text: (start > 0 ? '...' : '') + doc.text.slice(start, idx), match: false },
        { text: doc.text.slice(idx, end), match: true },
        { text: doc.text.slice(end, end + SNIPPET_CONTEXT_CHARS), match: false }
      ]
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
  beforeUnmount () {
    window.removeEventListener('keyup', this.keyup)
    this.resetTextSearch()
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

.search-mode {
  display: flex;
  gap: 4px;
  margin: 4px 0;

  .btn {
    flex: 1;
    padding: 0 4px;
    font-size: 10pt;
  }
}

.search-status {
  font-size: 9pt;
  opacity: 0.7;
  padding: 2px 4px;
}

.search-match {
  background: $warning;
  font-weight: bold;
}

</style>
