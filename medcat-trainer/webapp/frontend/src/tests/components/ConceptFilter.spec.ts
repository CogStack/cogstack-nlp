import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ConceptFilter from '@/components/common/ConceptFilter.vue'

const conceptList = [
  { cui: 'C001', name: 'Aspirin' },
  { cui: 'C002', name: 'Ibuprofen' },
  { cui: 'C003', name: 'Paracetamol' }
]

describe('ConceptFilter.vue', () => {
  const mockPost = vi.fn()

  beforeEach(() => {
    mockPost.mockResolvedValue({ data: { concept_list: [...conceptList] } })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  const mountFilter = (props: Record<string, unknown> = {}) =>
    mount(ConceptFilter, {
      props: { cuis: 'C001,C002,C003', cdb_id: 1, ...props },
      global: {
        mocks: { $http: { post: mockPost } },
        stubs: {
          'v-overlay': true,
          'v-progress-circular': true,
          'v-row': { template: '<div class="stub-row"><slot /></div>' },
          'v-text-field': {
            template:
              '<input class="stub-search" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
            props: ['modelValue']
          },
          'v-table': {
            template: '<table class="stub-table"><slot /></table>'
          }
        }
      }
    })

  it('loads concepts on create and shows project filter size', async () => {
    const wrapper = mountFilter()
    await flushPromises()

    expect(mockPost).toHaveBeenCalledWith('/api/cuis-to-concepts/', {
      cuis: ['C001', 'C002', 'C003'],
      cdb_id: 1
    })
    expect(wrapper.text()).toContain('Project concept filter size:')
    expect(wrapper.text()).toContain('3')
    expect(wrapper.findAll('#concept-table tbody tr')).toHaveLength(3)
  })

  it('sends null cuis when filter string is empty', async () => {
    mountFilter({ cuis: '' })
    await flushPromises()

    expect(mockPost).toHaveBeenCalledWith('/api/cuis-to-concepts/', {
      cuis: null,
      cdb_id: 1
    })
  })

  it('filterItems narrows rows and highlights matches', async () => {
    vi.useFakeTimers()
    const wrapper = mountFilter()
    await flushPromises()

    const vm = wrapper.vm as {
      filterItems: (q: string) => void
      items: { cui: string; name: string }[]
    }
    vm.filterItems('ibu')
    await vi.advanceTimersByTimeAsync(500)
    expect(vm.items).toHaveLength(1)
    expect(vm.items[0].cui).toBe('C002')
    expect(vm.items[0].name).toContain('<span class="highlight">')
    vi.useRealTimers()
  })

  it('clears search restores first page of all items', async () => {
    const wrapper = mountFilter()
    await flushPromises()

    const vm = wrapper.vm as {
      filter: string
      allItems: typeof conceptList
      items: unknown[]
    }
    vm.filter = 'asp'
    await wrapper.vm.$nextTick()
    vm.filter = ''
    await wrapper.vm.$nextTick()

    expect(vm.items).toHaveLength(vm.allItems.length)
  })
})
