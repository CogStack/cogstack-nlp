<template>
  <tr class="result-container">
    <td class="doc-name">{{ documentName }}</td>
    <td class="cui">{{ result && result.cui }}</td>
    <td class="source-value">{{ sourceValue }}</td>
    <td class="accu">{{ accuracy }}</td>
    <td class="text">
      <v-runtime-template v-if="text" :template="text"></v-runtime-template>
    </td>
  </tr>
</template>

<script>
import VRuntimeTemplate from 'vue3-runtime-template'
import { contextMentionIndex, escapeTemplateText, exampleField, resolvedExampleEnd } from '@/components/metrics/exampleFields'

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
    documentName () {
      return exampleField(this.result, 'document name', 'document_name') || ''
    },
    sourceValue () {
      return exampleField(this.result, 'source value', 'source_value') || ''
    },
    projectId () {
      return exampleField(this.result, 'project id', 'project_id')
    },
    documentId () {
      return exampleField(this.result, 'document id', 'document_id')
    },
    accuracy () {
      const acc = this.result ? (this.result.acc ?? this.result.confidence) : undefined
      const numeric = Number(acc)
      return Number.isFinite(numeric) ? numeric.toFixed(3) : ''
    },
    text () {
      const srcVal = this.sourceValue
      if (!this.result || !srcVal) return ''

      let highlightClass = 'highlight-task-0'
      if (this.type === 'fp' || this.type === 'fn') {
        highlightClass = 'highlight-task-1'
      }
      const highlight = `<span class="${highlightClass}" @click="openAnno">${escapeTemplateText(srcVal)}</span>`
      const snippet = this.snippetAround(srcVal)
      return `<span>${snippet.before}${highlight}${snippet.after}</span>`
    }
  },
  methods: {
    snippetAround (srcVal) {
      const start = Number(this.result.start)
      const end = Number(this.result.end)
      const fullText = typeof this.docText === 'string' ? this.docText : ''
      const resolvedEnd = resolvedExampleEnd(fullText, start, end, srcVal)
      if (resolvedEnd != null) {
        return {
          before: escapeTemplateText(fullText.slice(Math.max(0, start - 60), start)),
          after: escapeTemplateText(fullText.slice(resolvedEnd, resolvedEnd + 60))
        }
      }

      const context = typeof this.result.text === 'string' ? this.result.text : ''
      const idx = contextMentionIndex(context, start, srcVal)
      if (idx === -1) {
        return { before: escapeTemplateText(context), after: '' }
      }
      return {
        before: escapeTemplateText(context.slice(0, idx)),
        after: escapeTemplateText(context.slice(idx + srcVal.length))
      }
    },
    openAnno () {
      if (this.projectId == null || this.documentId == null) return
      const start = Number(this.result.start)
      const end = Number(this.result.end)
      const fullText = typeof this.docText === 'string' ? this.docText : ''
      const resolvedEnd = resolvedExampleEnd(fullText, start, end, this.sourceValue)
      const routeData = this.$router.resolve(
        {
          path: `/train-annotations/${this.projectId}/${this.documentId}`,
          query: {
            annoStart: this.result.start,
            annoEnd: resolvedEnd == null ? this.result.end : resolvedEnd
          }
      })
      window.open(routeData.href, '_blank')
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
