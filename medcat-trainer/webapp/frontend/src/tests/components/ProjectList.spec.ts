import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ProjectList from '@/components/common/ProjectList.vue'
import { ALL_FILTER } from '@/utils/projectListFilters'

const sampleProjects = [
  {
    id: 1,
    name: 'Zebra Project',
    description: 'desc',
    create_time: '2024-01-01T00:00:00Z',
    last_modified: '2024-06-01T10:00:00Z',
    cuis: 'C001,C002',
    require_entity_validation: true,
    project_status: 'A',
    project_locked: false,
    annotation_classification: false,
    progress: 2,
    progress_max: 10,
    cdb_search_filter: 1
  },
  {
    id: 2,
    name: 'Alpha Project',
    description: 'desc2',
    create_time: '2024-02-01T00:00:00Z',
    last_modified: '2024-05-01T10:00:00Z',
    cuis: '',
    require_entity_validation: false,
    project_status: 'C',
    project_locked: true,
    annotation_classification: true,
    progress: 5,
    progress_max: 5,
    cdb_search_filter: null
  }
]

describe('ProjectList.vue', () => {
  const mockGet = vi.fn()
  const mockPost = vi.fn()
  const mockDelete = vi.fn()
  const originalSetTimeout = window.setTimeout.bind(window)

  beforeEach(() => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/api/prep-docs-bg-tasks/') {
        return Promise.resolve({ data: { comp_tasks: [], running_tasks: [] } })
      }
      if (url === '/api/model-loaded/') {
        return Promise.resolve({ data: { model_states: {} } })
      }
      return Promise.resolve({ data: {} })
    })
    mockPost.mockResolvedValue({ data: {} })
    mockDelete.mockResolvedValue({ data: 'success' })
    vi.spyOn(window, 'setTimeout').mockImplementation(((
      handler: TimerHandler,
      timeout?: number,
      ...args: unknown[]
    ) => {
      if (timeout === 8000) {
        return 0 as unknown as ReturnType<typeof window.setTimeout>
      }
      return originalSetTimeout(handler, timeout, ...args) as unknown as ReturnType<
        typeof window.setTimeout
      >
    }) as unknown as typeof window.setTimeout)
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  const mountList = (props: Record<string, unknown> = {}) =>
    mount(ProjectList, {
      props: {
        projectItems: sampleProjects,
        isAdmin: false,
        cdbSearchIndexStatus: { 1: true },
        ...props
      },
      global: {
        mocks: {
          $http: { get: mockGet, post: mockPost, delete: mockDelete }
        },
        stubs: {
          'v-data-table': {
            template: '<div class="stub-table"><slot name="no-data" /></div>',
            props: ['items', 'headers']
          },
          'v-overlay': true,
          'v-progress-circular': true,
          'v-progress-linear': true,
          'v-tooltip': true,
          'font-awesome-icon': true,
          Modal: true,
          'router-link': true
        }
      }
    })

  it('formatShortDate returns em dash for empty values', async () => {
    const wrapper = mountList()
    await flushPromises()
    const vm = wrapper.vm as { formatShortDate: (v: string | null) => string }
    expect(vm.formatShortDate(null)).toBe('—')
    expect(vm.formatShortDate('2024-06-01T10:00:00Z')).toBe(
      new Date('2024-06-01T10:00:00Z').toLocaleDateString()
    )
  })

  it('clearFilters resets filter state', async () => {
    const wrapper = mountList()
    await flushPromises()
    const vm = wrapper.vm as {
      searchQuery: string
      statusFilter: string
      modeFilter: string
      clearFilters: () => void
    }
    vm.searchQuery = 'zebra'
    vm.statusFilter = 'C'
    vm.modeFilter = 'annotate'
    vm.clearFilters()
    expect(vm.searchQuery).toBe('')
    expect(vm.statusFilter).toBe(ALL_FILTER)
    expect(vm.modeFilter).toBe(ALL_FILTER)
  })

  it('toggleSort flips order for same column', async () => {
    const wrapper = mountList()
    await flushPromises()
    const vm = wrapper.vm as {
      sortBy: string
      sortOrder: string
      toggleSort: (k: string) => void
    }
    vm.sortBy = 'name'
    vm.sortOrder = 'asc'
    vm.toggleSort('name')
    expect(vm.sortOrder).toBe('desc')
    vm.toggleSort('last_modified')
    expect(vm.sortBy).toBe('last_modified')
    expect(vm.sortOrder).toBe('desc')
  })

  it('filteredProjectItems filters by debounced search query', async () => {
    const wrapper = mountList()
    await flushPromises()
    const vm = wrapper.vm as {
      debouncedSearchQuery: string
      filteredProjectItems: typeof sampleProjects
    }
    vm.debouncedSearchQuery = 'zebra'
    await wrapper.vm.$nextTick()
    expect(vm.filteredProjectItems).toHaveLength(1)
    expect(vm.filteredProjectItems[0].name).toBe('Zebra Project')
  })

  it('visibleHeaders hides admin-only columns for non-admin', async () => {
    const wrapper = mountList({ isAdmin: false })
    await flushPromises()
    const vm = wrapper.vm as { visibleHeaders: { value: string }[] }
    const values = vm.visibleHeaders.map(h => h.value)
    expect(values).not.toContain('run_model')
    expect(values).not.toContain('save_model')
  })

  it('visibleHeaders includes admin columns for admin users', async () => {
    const wrapper = mountList({ isAdmin: true })
    await flushPromises()
    const vm = wrapper.vm as { visibleHeaders: { value: string }[] }
    const values = vm.visibleHeaders.map(h => h.value)
    expect(values).toContain('run_model')
    expect(values).toContain('metrics')
  })

  it('fetches model loaded state on create', async () => {
    mountList()
    await flushPromises()
    expect(mockGet).toHaveBeenCalledWith('/api/model-loaded/')
  })
})
