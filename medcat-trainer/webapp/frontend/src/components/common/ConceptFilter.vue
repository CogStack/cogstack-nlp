<template>
  <div class="concept-filter-parent">
    <v-overlay :model-value="loading"
               class="align-center justify-center"
               color="#005EB8"
               activator="parent"
               contained
               :disabled="true"
               :persistent="true">
      <v-progress-circular indeterminate color="'primary'"></v-progress-circular>
    </v-overlay>
    <div>
      <v-row class="search-bar">
        <v-text-field v-model="filter" type="search"
                      label="Concept search"></v-text-field>
        <div class="search-results">
            <span v-if="filter === ''">Project concept filter size: <strong>{{(allItems || []).length}}</strong></span>
            <span v-if="filter !== ''">Found <strong>{{allFilteredItems.length}}</strong> - showing first {{items.length}}</span>
        </div>
      </v-row>


      <v-table density="compact" id="concept-table">
        <thead>
          <tr>
            <th>CUI</th>
            <th>Name</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in items" :key="item.cui">
            <td>{{item.cui}}</td>
            <td><span v-html="item.name"></span></td>
          </tr>
        </tbody>
      </v-table>
    </div>
  </div>
</template>

<script>
import _ from 'lodash'

const ROW_LIMIT = 100

export default {
  name: "ConceptFilter",
  props: {
    cuis: String,
    cdb_id: Number
  },
  data () {
    return {
      rowLimit: ROW_LIMIT,
      currentPage: 1,
      loading: false,
      items: null,
      allItems: null,
      allFilteredItems: [],
      headers: [
        { value: 'cui', title: 'CUI' },
        { value: 'name', title: 'Name' }
      ],
      filter: '',
    }
  },
  created () {
    this.loading = true
    let payload = {
      cuis: this.cuis !== '' ? this.cuis.split(',') : null,
      cdb_id: this.cdb_id
    }
    this.$http.post('/api/cuis-to-concepts/', payload).then(resp => {
      const items = resp.data.concept_list.sort((a,b) => a.name.localeCompare(b.name))
      if (items.length > ROW_LIMIT) {
        this.items = items.slice(0, ROW_LIMIT)
        this.allItems = items
      } else {
        this.items = items
        this.allItems = this.items
      }
      this.loading = false
    })
  },
  methods: {
    filterItems: _.debounce(function(filterStr) {
      filterStr = filterStr.toLowerCase()
      function highlightCUINames(concepts, query) {
        const lowercaseQuery = query.toLowerCase();
        return concepts.map(concept => {
          const name = concept.name
          let lowercaseStr = name.toLowerCase();
          let result = '';
          let lastIndex = 0;

          while (true) {
            const index = lowercaseStr.indexOf(lowercaseQuery, lastIndex);
            if (index === -1) break;

            result += name.slice(lastIndex, index);
            result += `<span class="highlight">${name.slice(index, index + query.length)}</span>`;

            lastIndex = index + query.length;
          }
          result += name.slice(lastIndex);
          return {...concept, ...{ name: result }}
        });
      }
      let filteredItems = this.allItems.filter((v) => v.name.toLowerCase().includes(filterStr))
      filteredItems = filteredItems.sort((a,b) => {
        const aStartsWith = a.name.toLowerCase().startsWith(filterStr)
        const bStartsWith = b.name.toLowerCase().startsWith(filterStr)
        if (aStartsWith !== bStartsWith) {
          return aStartsWith ? -1 : 1
        }
        return a.name.length - b.name.length

      })
      filteredItems = highlightCUINames(filteredItems, filterStr)

      if (filteredItems.length > ROW_LIMIT) {
        this.allFilteredItems = filteredItems
        this.items = this.allFilteredItems.slice(0, ROW_LIMIT)
      } else {
        this.items = filteredItems
        this.allFilteredItems = []
      }
      this.currentPage = 0
      this.loading = false
    }, 500)
  },
  watch: {
    filter (newVal) {
      if (newVal.length > 0) {
        this.filterItems(newVal)
      } else {
        this.items = this.allItems.slice(0, ROW_LIMIT)
        this.allFilteredItems = []
        this.currentPage = 0
        this.loading = false
      }
    }
  }
}
</script>

<style lang="scss">
.concept-filter-parent {
  position: relative;
  padding: 5px;
}

.search-bar {
  flex-wrap: nowrap;
  //margin: 5px 0;
  width: calc(100% - 300px);

  input {
    display: inline-block;
    width: calc(100% - 300px);
  }

  span {
    float: right;
  }
}

.search-results {
  padding-left: 10px;
  padding-top: 10px;
}

.highlight {
  font-weight: bold;
}
</style>
