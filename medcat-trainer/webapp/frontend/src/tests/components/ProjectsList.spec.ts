import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ProjectsList from '@/components/admin/ProjectsList.vue'
import { ALL_FILTER } from '@/utils/projectListFilters'

const projects = [
  {
    id: 1,
    name: 'Zebra Study',
    description: 'First project',
    project_status: 'A',
    require_entity_validation: true,
    dataset: 10,
    create_time: '2024-01-01T00:00:00Z',
    last_modified: '2024-06-01T10:00:00Z'
  },
  {
    id: 2,
    name: 'Alpha Trial',
    description: 'Second project',
    project_status: 'C',
    require_entity_validation: false,
    dataset: 20,
    create_time: '2024-02-01T00:00:00Z',
    last_modified: '2024-05-01T10:00:00Z'
  }
]

const datasets = [
  { id: 10, name: 'Dataset A' },
  { id: 20, name: 'Dataset B' }
]

describe('ProjectsList.vue', () => {
  const adminStubs = {
    'v-data-table': {
      template: '<div class="stub-table"><slot name="no-data" /></div>',
      props: ['items', 'headers']
    },
    'font-awesome-icon': true
  }

  const mountList = (props: Record<string, unknown> = {}) =>
    mount(ProjectsList, {
      props: { projects, datasets, ...props },
      global: { stubs: adminStubs }
    })

  it('shows empty state when there are no projects', () => {
    const wrapper = mountList({ projects: [] })
    expect(wrapper.text()).toContain('No Projects Yet')
    expect(wrapper.find('.btn-create-empty').exists()).toBe(true)
  })

  it('getStatusText and getModeText format badges', () => {
    const wrapper = mountList()
    const vm = wrapper.vm as {
      getStatusText: (s: string) => string
      getModeText: (v: boolean) => string
      getDatasetName: (id: number) => string
    }
    expect(vm.getStatusText('A')).toBe('Annotating')
    expect(vm.getStatusText('C')).toBe('Complete')
    expect(vm.getModeText(true)).toBe('Annotate')
    expect(vm.getModeText(false)).toBe('Validate')
    expect(vm.getDatasetName(10)).toBe('Dataset A')
    expect(vm.getDatasetName(999)).toBe('N/A')
  })

  it('filteredProjects respects debounced search query', async () => {
    const wrapper = mountList()
    const vm = wrapper.vm as {
      debouncedSearchQuery: string
      filteredProjects: typeof projects
    }
    vm.debouncedSearchQuery = 'zebra'
    await wrapper.vm.$nextTick()
    expect(vm.filteredProjects).toHaveLength(1)
    expect(vm.filteredProjects[0].name).toBe('Zebra Study')
  })

  it('clearFilters resets filter state', () => {
    const wrapper = mountList()
    const vm = wrapper.vm as {
      searchQuery: string
      statusFilter: string
      modeFilter: string
      clearFilters: () => void
    }
    vm.searchQuery = 'alpha'
    vm.statusFilter = 'C'
    vm.modeFilter = 'annotate'
    vm.clearFilters()
    expect(vm.searchQuery).toBe('')
    expect(vm.statusFilter).toBe(ALL_FILTER)
    expect(vm.modeFilter).toBe(ALL_FILTER)
  })

  it('toggleSort switches column and order', () => {
    const wrapper = mountList()
    const vm = wrapper.vm as {
      sortBy: string
      sortOrder: string
      toggleSort: (k: string) => void
    }
    vm.sortBy = 'name'
    vm.sortOrder = 'asc'
    vm.toggleSort('name')
    expect(vm.sortOrder).toBe('desc')
    vm.toggleSort('create_time')
    expect(vm.sortBy).toBe('create_time')
    expect(vm.sortOrder).toBe('desc')
  })

  it('emits create-project from empty-state button', async () => {
    const wrapper = mountList({ projects: [] })
    await wrapper.find('.btn-create-empty').trigger('click')
    expect(wrapper.emitted('create-project')).toBeTruthy()
  })
})
