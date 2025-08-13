<template>
  <div @keydown.stop>
    <v-select v-model="selectedCUI" @search="searchCUI"
              :inputId="'searchBox'"
              :clearSearchOnSelect="true"
              :filterable="false"
              :appendToBody="true"
              :options="searchResults"
              :loading="loadingResults"
              label="cui"
              @open="$emit('picker:opened')"
              @close="$emit('picker:closed')">
      <template v-slot:no-options="{ search, searching }">
        <template v-if="error">
          <span class="text-danger">{{ error }}</span>
        </template>
        <template v-if="searching">No results found for <em>{{ search }}</em>.
        </template>
        <em v-if="!error" style="opacity: 0.5">Start typing to search for a concept.</em>
      </template>
      <template v-slot:option="option">
        <span class="select-option">{{option.name}}</span>
        <span class="select-option-cui"> - {{option.cui}}</span>
      </template>
    </v-select>
  </div>
</template>

<script>
import vSelect from 'vue-select'
import _ from 'lodash'

export default {
  name: 'ConceptPicker',
  components: {
    vSelect
  },
  emits: [
    'picker:opened',
    'picker:closed',
    'pickedResult:concept'
  ],
  props: {
    restrict_concept_lookup: Boolean,
    cui_filter: String,
    cdb_search_filter: Array,
    concept_db: Number,
    selection: String
  },
  created () {
    let that = this
    window.setTimeout(function () {
      const el = document.getElementById('searchBox')
      el.focus()
      el.value = that.selection
      that.searchCUI(that.selection)
    }, 150)
  },
  data () {
    return {
      selectedCUI: null,
      searchResults: [],
      loadingResults: false
    }
  },
  watch: {
    'selectedCUI' (newVal) {
      this.$emit('pickedResult:concept', newVal)
    },
    'selection': 'selectionChange'
  },
  methods: {
    searchCUI: _.debounce(function (term) {
      this.loadingResults = true

      if (!term || term.trim().length === 0) {
        this.loadingResults = false
        return
      }

      const mapResult = function (r, allResults) {
        const isDupName = allResults.filter(res => res.pretty_name === r.pretty_name).length > 1
        return {
          name: isDupName ? `${r.pretty_name} : ${r.cui}` : r.pretty_name,
          cui: r.cui,
          type_ids: r.type_ids,
          desc: r.desc,
          icd10: r.icd10,
          opcs4: r.opcs4,
          semantic_type: r.semantic_type,
          synonyms: r.synonyms
        }
      }

      const that = this
      const conceptDBset = new Set(this.cdb_search_filter.concat(this.concept_db))
      conceptDBset.delete(null)
      const conceptDbs = Array.from(conceptDBset).join(',')
      const searchByTerm = function () {
        let searchConceptsQueryParams = `search=${term}&cdbs=${conceptDbs}`
        that.$http.get(`/api/search-concepts/?${searchConceptsQueryParams}`).then(resp => {
          that.searchResults = filterResults(resp.data.results.map(res => mapResult(res, resp.data.results)))
          // loading(false)
          that.loadingResults = false
        }).catch(err => {
          that.error = err.response?.data?.message || 'Error searching concepts - check project setup or contact project support'
          that.loadingResults = false
          that.searchResults = []
        })
      }
      const filterResults = function (results) {
        if (that.restrict_concept_lookup) {
          if (that.cui_filter) {
            let cuis = that.cui_filter.split(',').map(c => c.trim())
            results = results.filter(r => cuis.indexOf(r.cui) !== -1)
          }
        }
        return results
      }
      searchByTerm()
    }, 500)
  }
}
</script>

<style scoped lang="scss">
.select-option {
  white-space: pre-wrap;
  padding: 3px 0;
}
.select-option-cui {
  opacity: 50%;
  padding: 3px 0;
}
</style>
