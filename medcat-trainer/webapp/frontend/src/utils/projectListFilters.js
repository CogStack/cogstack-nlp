export const ALL_FILTER = ''

export const STATUS_FILTER_OPTIONS = [
  { label: 'All', value: ALL_FILTER },
  { label: 'Annotating', value: 'A' },
  { label: 'Complete', value: 'C' },
  { label: 'Discontinued', value: 'D' }
]

export const MODE_FILTER_OPTIONS = [
  { label: 'All', value: ALL_FILTER },
  { label: 'Annotate', value: 'annotate' },
  { label: 'Validate', value: 'validate' }
]

export const SORT_OPTIONS = [
  { label: 'Last modified', value: 'last_modified' },
  { label: 'Create time', value: 'create_time' },
  { label: 'Title', value: 'name' }
]

const customKeySort = {
  name: (a, b) => String(a || '').localeCompare(String(b || ''), undefined, { sensitivity: 'base' }),
  create_time: (a, b) => new Date(a || 0) - new Date(b || 0),
  last_modified: (a, b) => new Date(a || 0) - new Date(b || 0)
}

export function hasActiveProjectFilters({ searchQuery, statusFilter, modeFilter }) {
  return Boolean(
    searchQuery?.trim() ||
    statusFilter !== ALL_FILTER ||
    modeFilter !== ALL_FILTER
  )
}

export function filterAndSortProjects(items, { searchQuery, statusFilter, modeFilter, sortBy, sortOrder }) {
  let result = [...(items || [])]
  const query = searchQuery?.trim().toLowerCase()

  if (query) {
    result = result.filter(p => (p.name || '').toLowerCase().includes(query))
  }
  if (statusFilter !== ALL_FILTER) {
    result = result.filter(p => p.project_status === statusFilter)
  }
  if (modeFilter === 'annotate') {
    result = result.filter(p => p.require_entity_validation === true)
  } else if (modeFilter === 'validate') {
    result = result.filter(p => p.require_entity_validation === false)
  }

  const direction = sortOrder === 'asc' ? 1 : -1
  const sorter = customKeySort[sortBy]
  if (sorter) {
    result.sort((a, b) => sorter(a[sortBy], b[sortBy]) * direction)
  }

  return result
}
