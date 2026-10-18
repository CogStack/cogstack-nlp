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

function sameMention (slice, sourceValue) {
  return slice === sourceValue || slice.toLowerCase() === sourceValue.toLowerCase()
}

// Stats examples often store end equal to start. The mention still begins at
// start, so a trailing slice from end repeats it beside the clickable span.
export function resolvedExampleEnd (fullText, start, end, sourceValue) {
  if (typeof fullText !== 'string' || !sourceValue) return null
  if (!Number.isFinite(start) || !Number.isFinite(end) || start < 0 || start > fullText.length) return null
  if (end >= start && end <= fullText.length && sameMention(fullText.slice(start, end), sourceValue)) return end
  const byLength = start + sourceValue.length
  if (byLength <= fullText.length && sameMention(fullText.slice(start, byLength), sourceValue)) return byLength
  return null
}

// MedCAT context windows are doc[max(0, start - 60): end + 60], so the
// annotated mention is at min(start, 60), not the first copy in that window.
export function contextMentionIndex (context, start, sourceValue) {
  if (typeof context !== 'string' || !sourceValue) return -1
  const at = (index) => index >= 0 &&
    index + sourceValue.length <= context.length &&
    sameMention(context.slice(index, index + sourceValue.length), sourceValue)
  if (Number.isFinite(start) && at(Math.min(Math.max(start, 0), 60))) {
    return Math.min(Math.max(start, 0), 60)
  }
  const exact = context.indexOf(sourceValue)
  if (exact !== -1) return exact
  return context.toLowerCase().indexOf(sourceValue.toLowerCase())
}
