import _ from 'lodash'

export default {
  name: 'ConceptDetailService',
  methods: {
    fetchDetail (selectedEnt, cdbSearchIndex, callback) {
      if (selectedEnt && Object.keys(selectedEnt).length) {
        const queryEntId = selectedEnt.id
        this.$http.get(`/api/entities/${selectedEnt.entity}/`).then(resp => {
          if (selectedEnt && queryEntId === selectedEnt.id) {
            selectedEnt.cui = resp.data.label
            this.fetchConcept(selectedEnt, cdbSearchIndex, callback)
          }
        })
      } else {
        if (this.conceptSummary) {
          this.conceptSummary = {}
        }
      }
    },
    fetchConcept (selectedEnt, cdbSearchIndex, callback) {
      const cdbs = this.conceptSearchCdbs(cdbSearchIndex)
      if (!cdbs) {
        if (callback) {
          callback()
        }
        return
      }
      const query = `search=${encodeURIComponent(selectedEnt.cui)}&cdbs=${encodeURIComponent(cdbs)}`
      this.$http.get(`/api/search-concepts/?${query}`).then(resp => {
        const results = resp.data?.results || []
        if (selectedEnt && results.length > 0) {
          const docEnt = results[0]
          selectedEnt.desc = docEnt.desc
          selectedEnt.type_ids = docEnt.type_ids
          selectedEnt.pretty_name = Array.isArray(docEnt.pretty_name) ? docEnt.pretty_name[0] : docEnt.pretty_name
          selectedEnt.synonyms = docEnt.synonyms
          if ((docEnt.icd10 || []).length > 0) {
            selectedEnt.icd10 = []
            let that = this
            let getCodes = function (url) {
              that.$http.get(url).then(resp => {
                selectedEnt.icd10.push(...resp.data.results)
                if (resp.data.next) {
                  getCodes(`/api/${resp.data.next.split('/api/')[1]}`)
                } else if (callback) {
                  selectedEnt.icd10 = _.orderBy(selectedEnt.icd10, ['code'], ['asc'])
                  callback()
                }
              })
            }
            getCodes(`/api/icd-codes/?id__in=${docEnt.icd10.join(',')}`)
          } else {
            selectedEnt.icd10 = []
          }
          if ((docEnt.opcs4 || []).length > 0) {
            selectedEnt.opcs4 = []
            let that = this
            let getCodes = function (url) {
              that.$http.get(url).then(resp => {
                selectedEnt.opcs4.push(...resp.data.results)
                if (resp.data.next) {
                  getCodes(`/api/${resp.data.next.split('/api/')[1]}`)
                } else if (callback) {
                  selectedEnt.opcs4 = _.orderBy(selectedEnt.opcs4, ['code'], ['asc'])
                  callback()
                }
              })
            }
            getCodes(`/api/opcs-codes/?id__in=${docEnt.opcs4.join(',')}`)
          } else {
            selectedEnt.opcs4 = []
          }
        }
        if (callback) {
          callback()
        }
      })
    },
    conceptSearchCdbs (cdbSearchIndex) {
      if (Array.isArray(cdbSearchIndex)) {
        return cdbSearchIndex.filter(id => id).join(',')
      }
      if (!cdbSearchIndex) {
        return null
      }
      const searchIndex = String(cdbSearchIndex)
      const collectionMatch = searchIndex.match(/_id_(.+)$/)
      return collectionMatch ? collectionMatch[1] : searchIndex
    }
  }
}
