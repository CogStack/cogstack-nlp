// MedCAT stats examples have used two key styles:
// legacy trainer payloads ("document id") and current get_stats payloads (document_id).
export function exampleField (example, ...keys) {
  if (!example || typeof example !== 'object') return undefined
  for (const key of keys) {
    const value = example[key]
    if (value !== undefined && value !== null && value !== '') return value
  }
  return undefined
}

// Clinical text is compiled as a Vue template. Escape markup and mustache
// delimiters so a note cannot break the dialog render.
export function escapeTemplateText (value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
    .replace(/\{/g, '&#123;')
    .replace(/\}/g, '&#125;')
}

export function documentTextForExample (docs2text, example) {
  if (!docs2text || !example) return ''
  const docId = exampleField(example, 'document id', 'document_id')
  if (docId == null) return ''
  if (docs2text[docId] != null) return docs2text[docId]
  const asString = String(docId)
  if (docs2text[asString] != null) return docs2text[asString]
  const asNumber = Number(docId)
  if (!Number.isNaN(asNumber) && docs2text[asNumber] != null) return docs2text[asNumber]
  return ''
}
