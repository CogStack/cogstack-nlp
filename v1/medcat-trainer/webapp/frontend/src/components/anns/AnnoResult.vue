<template>
  <tr class="result-container">
    <td class="doc-name">{{result['document name']}}</td>
    <td class="cui">{{result.cui}}</td>
    <td class="source-value">{{result['source value']}}</td>
    <td class="accu">{{Number(result.acc).toFixed(3)}}</td>
    <td class="text">
      <v-runtime-template :template="text"></v-runtime-template>
    </td>
  </tr>
</template>

<script>
import VRuntimeTemplate from 'vue3-runtime-template'

export default {
  name: 'AnnoResult.vue',
  components: { VRuntimeTemplate },
  props: {
    result: Object,
    type: {
      type: String,
      default: 'tp'
    },
    docText: String
  },
  computed: {
    text () {
      if (!this.result || !this.result.text || !this.result['source value']) {
        return ''
      }
      // default to tp
      let highlightClass = 'highlight-task-0'
      if (this.type === 'fp' || this.type === 'fn') {
        highlightClass = 'highlight-task-1'
      }
      
      const srcVal = this.result['source value']
      let outText = `<span>${this.docText.slice(this.result['start'] - 60, this.result['start'])}`
      outText += `<span class="${highlightClass}" @click="openAnno">${srcVal}</span>`
      outText += `${this.docText.slice(this.result['end'], this.result['end'] + 60)}</span>`
      return outText
    }
  },
  methods: {
    openAnno () {
      const routeData = this.$router.resolve(
        {
          path: `/train-annotations/${this.result['project id']}/${this.result['document id']}`,
          query: {
            annoStart: this.result['start'],
            annoEnd: this.result['end']
          }
      })
      window.open(routeData.href, '_blank');
    }
  }
}
</script>

<style scoped lang="scss">
.result-container {
  > td {
    padding: 10px;
  }
}
</style>
