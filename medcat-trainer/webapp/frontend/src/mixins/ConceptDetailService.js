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
      this.$http.get(`/api/concepts/${cdbSearchIndex}/select?q=cui:${selectedEnt.cui}`).then(resp => {
        if (selectedEnt && resp.data.response.docs.length > 0) {
          const docEnt = resp.data.response.docs[0]
          selectedEnt.desc = docEnt.desc
          selectedEnt.type_ids = docEnt.type_ids
          selectedEnt.pretty_name = docEnt.pretty_name[0]
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
    }
  }
}
