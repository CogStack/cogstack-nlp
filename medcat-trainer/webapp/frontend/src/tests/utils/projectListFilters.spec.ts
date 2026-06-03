import { describe, it, expect } from 'vitest'
import {
  ALL_FILTER,
  STATUS_FILTER_OPTIONS,
  MODE_FILTER_OPTIONS,
  SORT_OPTIONS,
  hasActiveProjectFilters,
  filterAndSortProjects
} from '@/utils/projectListFilters'

const sampleProjects = [
  {
    name: 'Alpha Project',
    project_status: 'A',
    require_entity_validation: true,
    last_modified: '2024-06-01T10:00:00Z',
    create_time: '2024-01-01T00:00:00Z'
  },
  {
    name: 'Beta Complete',
    project_status: 'C',
    require_entity_validation: false,
    last_modified: '2024-05-01T10:00:00Z',
    create_time: '2024-02-01T00:00:00Z'
  },
  {
    name: 'Gamma Discontinued',
    project_status: 'D',
    require_entity_validation: true,
    last_modified: '2024-04-01T10:00:00Z',
    create_time: '2024-03-01T00:00:00Z'
  }
]

describe('projectListFilters constants', () => {
  it('exports filter option lists with All entries', () => {
    expect(STATUS_FILTER_OPTIONS[0]).toEqual({ label: 'All', value: ALL_FILTER })
    expect(MODE_FILTER_OPTIONS[0]).toEqual({ label: 'All', value: ALL_FILTER })
    expect(SORT_OPTIONS.length).toBeGreaterThanOrEqual(3)
  })
})

describe('hasActiveProjectFilters', () => {
  it('returns false when all filters are default', () => {
    expect(
      hasActiveProjectFilters({
        searchQuery: '',
        statusFilter: ALL_FILTER,
        modeFilter: ALL_FILTER
      })
    ).toBe(false)
  })

  it('returns true when search query is non-empty', () => {
    expect(
      hasActiveProjectFilters({
        searchQuery: 'alpha',
        statusFilter: ALL_FILTER,
        modeFilter: ALL_FILTER
      })
    ).toBe(true)
  })

  it('returns true when status filter is set', () => {
    expect(
      hasActiveProjectFilters({
        searchQuery: '',
        statusFilter: 'C',
        modeFilter: ALL_FILTER
      })
    ).toBe(true)
  })

  it('returns true when mode filter is set', () => {
    expect(
      hasActiveProjectFilters({
        searchQuery: '',
        statusFilter: ALL_FILTER,
        modeFilter: 'validate'
      })
    ).toBe(true)
  })
})

describe('filterAndSortProjects', () => {
  it('returns all projects when no filters active', () => {
    const result = filterAndSortProjects(sampleProjects, {
      searchQuery: '',
      statusFilter: ALL_FILTER,
      modeFilter: ALL_FILTER,
      sortBy: 'name',
      sortOrder: 'asc'
    })
    expect(result).toHaveLength(3)
    expect(result[0].name).toBe('Alpha Project')
  })

  it('filters by name search (case-insensitive)', () => {
    const result = filterAndSortProjects(sampleProjects, {
      searchQuery: 'beta',
      statusFilter: ALL_FILTER,
      modeFilter: ALL_FILTER,
      sortBy: 'name',
      sortOrder: 'asc'
    })
    expect(result).toHaveLength(1)
    expect(result[0].name).toBe('Beta Complete')
  })

  it('filters by project status', () => {
    const result = filterAndSortProjects(sampleProjects, {
      searchQuery: '',
      statusFilter: 'C',
      modeFilter: ALL_FILTER,
      sortBy: 'name',
      sortOrder: 'asc'
    })
    expect(result).toHaveLength(1)
    expect(result[0].project_status).toBe('C')
  })

  it('filters annotate mode (require_entity_validation true)', () => {
    const result = filterAndSortProjects(sampleProjects, {
      searchQuery: '',
      statusFilter: ALL_FILTER,
      modeFilter: 'annotate',
      sortBy: 'name',
      sortOrder: 'asc'
    })
    expect(result).toHaveLength(2)
    expect(result.every(p => p.require_entity_validation)).toBe(true)
  })

  it('filters validate mode (require_entity_validation false)', () => {
    const result = filterAndSortProjects(sampleProjects, {
      searchQuery: '',
      statusFilter: ALL_FILTER,
      modeFilter: 'validate',
      sortBy: 'name',
      sortOrder: 'asc'
    })
    expect(result).toHaveLength(1)
    expect(result[0].require_entity_validation).toBe(false)
  })

  it('sorts by name descending', () => {
    const result = filterAndSortProjects(sampleProjects, {
      searchQuery: '',
      statusFilter: ALL_FILTER,
      modeFilter: ALL_FILTER,
      sortBy: 'name',
      sortOrder: 'desc'
    })
    expect(result[0].name).toBe('Gamma Discontinued')
    expect(result[2].name).toBe('Alpha Project')
  })

  it('sorts by last_modified ascending', () => {
    const result = filterAndSortProjects(sampleProjects, {
      searchQuery: '',
      statusFilter: ALL_FILTER,
      modeFilter: ALL_FILTER,
      sortBy: 'last_modified',
      sortOrder: 'asc'
    })
    expect(result[0].name).toBe('Gamma Discontinued')
    expect(result[2].name).toBe('Alpha Project')
  })

  it('handles null/undefined items list', () => {
    expect(
      filterAndSortProjects(null as unknown as typeof sampleProjects, {
        searchQuery: '',
        statusFilter: ALL_FILTER,
        modeFilter: ALL_FILTER,
        sortBy: 'name',
        sortOrder: 'asc'
      })
    ).toEqual([])
  })
})
