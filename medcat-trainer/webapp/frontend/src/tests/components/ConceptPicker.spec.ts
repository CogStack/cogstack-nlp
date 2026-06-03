import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import type { App } from 'vue'

vi.mock('lodash', () => {
  const immediateDebounce = <T extends (...args: never[]) => unknown>(fn: T) => {
    const debounced = function (this: unknown, ...args: Parameters<T>) {
      return fn.apply(this, args)
    }
    debounced.cancel = () => undefined
    debounced.flush = () => undefined
    return debounced
  }
  return {
    default: { debounce: immediateDebounce },
    debounce: immediateDebounce
  }
})

import ConceptPicker from '@/components/common/ConceptPicker.vue'

describe('ConceptPicker.vue', () => {
  const mockGet = vi.fn()
  const originalSetTimeout = window.setTimeout.bind(window)

  const httpPlugin = {
    install(app: App) {
      app.config.globalProperties.$http = { get: mockGet }
    }
  }

  beforeEach(() => {
    vi.spyOn(window, 'setTimeout').mockImplementation(((
      handler: TimerHandler,
      timeout?: number,
      ...args: unknown[]
    ) => {
      if (timeout === 150) {
        return 0 as unknown as ReturnType<typeof window.setTimeout>
      }
      return originalSetTimeout(handler, timeout, ...args) as unknown as ReturnType<
        typeof window.setTimeout
      >
    }) as unknown as typeof window.setTimeout)
    mockGet.mockResolvedValue({
      data: {
        results: [
          {
            cui: 'C001',
            pretty_name: 'Diabetes',
            type_ids: [],
            desc: '',
            icd10: [],
            opcs4: [],
            semantic_type: '',
            synonyms: []
          },
          {
            cui: 'C002',
            pretty_name: 'Diabetes',
            type_ids: [],
            desc: '',
            icd10: [],
            opcs4: [],
            semantic_type: '',
            synonyms: []
          }
        ]
      }
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  const mountPicker = (props: Record<string, unknown> = {}) =>
    mount(ConceptPicker, {
      props: {
        restrict_concept_lookup: false,
        cui_filter: '',
        cdb_search_filter: [],
        concept_db: 1,
        selection: '',
        ...props
      },
      global: {
        plugins: [httpPlugin],
        stubs: {
          'v-select': {
            template: '<div class="stub-v-select"></div>',
            props: ['modelValue', 'options', 'loading']
          }
        }
      }
    })

  it('does not search when term is empty', async () => {
    const wrapper = mountPicker()
    const vm = wrapper.vm as { searchCUI: (term: string) => void }
    vm.searchCUI('   ')
    await flushPromises()
    expect(mockGet).not.toHaveBeenCalled()
  })

  it('fetches concepts for a search term', async () => {
    const wrapper = mountPicker({ cdb_search_filter: [2] })
    const vm = wrapper.vm as {
      searchCUI: (term: string) => void
      searchResults: { cui: string; name: string }[]
      loadingResults: boolean
    }
    vm.searchCUI('diab')
    await flushPromises()

    expect(mockGet).toHaveBeenCalledWith('/api/search-concepts/?search=diab&cdbs=2,1')
    expect(vm.loadingResults).toBe(false)
    expect(vm.searchResults).toHaveLength(2)
    expect(vm.searchResults[0].name).toContain('C001')
  })

  it('restricts results to CUI filter when enabled', async () => {
    const wrapper = mountPicker({
      restrict_concept_lookup: true,
      cui_filter: 'C001'
    })
    const vm = wrapper.vm as {
      searchCUI: (term: string) => void
      searchResults: { cui: string }[]
    }
    vm.searchCUI('diab')
    await flushPromises()

    expect(vm.searchResults).toHaveLength(1)
    expect(vm.searchResults[0].cui).toBe('C001')
  })

  it('emits pickedResult:concept when selection changes', async () => {
    const wrapper = mountPicker()
    const concept = { cui: 'C001', name: 'Diabetes' }
    const vm = wrapper.vm as { selectedCUI: typeof concept }
    vm.selectedCUI = concept
    await wrapper.vm.$nextTick()

    expect(wrapper.emitted('pickedResult:concept')?.[0]).toEqual([concept])
  })

  it('sets error message when search fails', async () => {
    mockGet.mockRejectedValueOnce({
      response: { data: { message: 'Search unavailable' } }
    })
    const wrapper = mountPicker()
    const vm = wrapper.vm as { searchCUI: (term: string) => void; error: string | null }
    vm.searchCUI('fail')
    await flushPromises()

    expect(vm.error).toBe('Search unavailable')
  })
})
