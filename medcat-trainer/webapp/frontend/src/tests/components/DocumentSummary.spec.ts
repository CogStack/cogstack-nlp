import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import DocumentSummary from '@/components/common/DocumentSummary.vue'

const docs = [
  { id: 1, name: 'note-alpha', text: 'Line one\nLine two\nLine three\nLine four\nLine five\nLine six' },
  { id: 2, name: 'note-beta', text: 'Short note' },
  { id: 3, name: 'note-gamma', text: 'nan' }
]

describe('DocumentSummary.vue', () => {
  const originalSetTimeout = window.setTimeout.bind(window)

  beforeEach(() => {
    vi.spyOn(window, 'addEventListener')
    vi.spyOn(window, 'removeEventListener')
    Element.prototype.scrollIntoView = vi.fn()
    vi.spyOn(window, 'setTimeout').mockImplementation(((
      handler: TimerHandler,
      timeout?: number,
      ...args: unknown[]
    ) => {
      if (timeout === 50) {
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

  const defaultProps = {
    projId: 1,
    docs,
    moreDocs: true,
    selectedDocId: 1,
    loadingDoc: false,
    validatedDocIds: [1],
    preparedDocIds: [2]
  }

  const mountComponent = (props = {}) =>
    mount(DocumentSummary, {
      props: { ...defaultProps, ...props },
      global: {
        stubs: {
          'font-awesome-icon': true,
          'v-tooltip': true
        }
      }
    })

  it('renders document list and title', () => {
    const wrapper = mountComponent()
    expect(wrapper.text()).toContain('Clinical Notes')
    expect(wrapper.findAll('.doc')).toHaveLength(3)
  })

  it('highlights selected document', () => {
    const wrapper = mountComponent({ selectedDocId: 2 })
    const selected = wrapper.find('.selected-doc')
    expect(selected.exists()).toBe(true)
  })

  it('emits request:loadDoc when a document is clicked', async () => {
    const wrapper = mountComponent()
    const docEls = wrapper.findAll('.doc')
    await docEls[1].trigger('click')
    expect(wrapper.emitted('request:loadDoc')).toBeTruthy()
    expect(wrapper.emitted('request:loadDoc')?.[0]).toEqual([docs[1]])
  })

  it('emits request:nextDocSet when More Docs is clicked', async () => {
    const wrapper = mountComponent({ moreDocs: true })
    await wrapper.find('.more-docs').trigger('click')
    expect(wrapper.emitted('request:nextDocSet')).toBeTruthy()
  })

  it('limitText truncates to five lines', () => {
    const wrapper = mountComponent()
    const vm = wrapper.vm as { limitText: (v: string) => string }
    const long = 'a\nb\nc\nd\ne\nf\ng'
    expect(vm.limitText(long)).toBe('a\nb\nc\nd\ne')
    expect(vm.limitText('  single line  ')).toBe('single line')
  })

  it('searchDocs filters documents by name prefix', async () => {
    const wrapper = mountComponent()
    const vm = wrapper.vm as {
      activateSearch: () => void
      searchDocs: (e: { target: { value: string } }) => void
      filteredDocs: typeof docs
      searching: boolean
    }

    vm.activateSearch()
    await wrapper.vm.$nextTick()
    expect(vm.searching).toBe(true)

    vm.searchDocs({ target: { value: 'note-b' } })
    expect(vm.filteredDocs).toHaveLength(1)
    expect(vm.filteredDocs[0].name).toBe('note-beta')
  })

  it('shows search-filtered list when searchCrit is set', async () => {
    const wrapper = mountComponent()
    const vm = wrapper.vm as {
      activateSearch: () => void
      searchDocs: (e: { target: { value: string } }) => void
    }
    vm.activateSearch()
    vm.searchDocs({ target: { value: 'note-a' } })
    await wrapper.vm.$nextTick()
    expect(wrapper.findAll('.doc')).toHaveLength(1)
  })

  describe('text search', () => {
    type TextSearchVm = {
      searching: boolean
      searchMode: string
      searchDocs: (e: { target: { value: string } }) => void
      setSearchMode: (mode: string) => void
      textSearchResults: { id: number }[]
    }

    const textResults = [
      { id: 7, name: 'note-far', text: 'History: patient has chest pain on exertion.' }
    ]

    const mountWithHttp = (mockGet: ReturnType<typeof vi.fn>, props = {}) =>
      mount(DocumentSummary, {
        props: { ...defaultProps, datasetId: 5, ...props },
        global: {
          stubs: { 'font-awesome-icon': true, 'v-tooltip': true },
          mocks: { $http: { get: mockGet } }
        }
      })

    const flush = () => new Promise(resolve => originalSetTimeout(resolve, 0))

    beforeEach(() => {
      vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    })

    afterEach(() => {
      vi.useRealTimers()
    })

    it('queries the API for docs containing the span and lists the results', async () => {
      const mockGet = vi.fn().mockResolvedValue({
        data: { count: 1, next: null, results: textResults }
      })
      const wrapper = mountWithHttp(mockGet)
      const vm = wrapper.vm as unknown as TextSearchVm
      vm.searching = true
      await wrapper.vm.$nextTick()
      await wrapper.find('.search-mode-text').trigger('click')

      vm.searchDocs({ target: { value: 'chest pain' } })
      vm.searchDocs({ target: { value: 'chest pain' } })
      expect(mockGet).not.toHaveBeenCalled()
      vi.advanceTimersByTime(300)
      await flush()
      await wrapper.vm.$nextTick()

      expect(mockGet).toHaveBeenCalledTimes(1)
      expect(mockGet).toHaveBeenCalledWith('/api/documents/?text__icontains=chest+pain&dataset=5')
      const docEls = wrapper.findAll('.doc')
      expect(docEls).toHaveLength(1)
      expect(wrapper.find('.search-match').text()).toBe('chest pain')
      expect(wrapper.find('.search-status').text()).toContain('1 matching note')

      await docEls[0].trigger('click')
      expect(wrapper.emitted('request:loadDoc')?.[0]).toEqual([textResults[0]])
    })

    it('pages through further results with More Results', async () => {
      const mockGet = vi.fn()
        .mockResolvedValueOnce({
          data: { count: 2, next: 'http://host/api/documents/?dataset=5&page=2&text__icontains=pain', results: textResults }
        })
        .mockResolvedValueOnce({
          data: { count: 2, next: null, results: [{ id: 8, name: 'n8', text: 'pain' }] }
        })
      const wrapper = mountWithHttp(mockGet)
      const vm = wrapper.vm as unknown as TextSearchVm
      vm.searchMode = 'text'
      vm.searchDocs({ target: { value: 'pain' } })
      vi.advanceTimersByTime(300)
      await flush()
      await wrapper.vm.$nextTick()

      await wrapper.find('.more-docs').trigger('click')
      await flush()
      await wrapper.vm.$nextTick()
      expect(mockGet).toHaveBeenLastCalledWith('/api/documents/?dataset=5&page=2&text__icontains=pain')
      expect(wrapper.findAll('.doc')).toHaveLength(2)
      expect(wrapper.find('.more-docs').exists()).toBe(false)
    })

    it('ignores stale responses from superseded searches', async () => {
      let resolveFirst: (v: unknown) => void = () => {}
      const mockGet = vi.fn()
        .mockImplementationOnce(() => new Promise(resolve => { resolveFirst = resolve }))
        .mockResolvedValueOnce({ data: { count: 1, next: null, results: textResults } })
      const wrapper = mountWithHttp(mockGet)
      const vm = wrapper.vm as unknown as TextSearchVm
      vm.searchMode = 'text'
      vm.searchDocs({ target: { value: 'fever' } })
      vi.advanceTimersByTime(300)
      vm.searchDocs({ target: { value: 'chest' } })
      vi.advanceTimersByTime(300)
      await flush()
      resolveFirst({ data: { count: 1, next: null, results: [{ id: 99, name: 'stale', text: 'fever' }] } })
      await flush()
      await wrapper.vm.$nextTick()
      expect(vm.textSearchResults.map(d => d.id)).toEqual([7])
    })

    it('switching back to name mode filters loaded docs without calling the API', async () => {
      const mockGet = vi.fn()
      const wrapper = mountWithHttp(mockGet)
      const vm = wrapper.vm as unknown as TextSearchVm
      vm.searchMode = 'text'
      vm.searchDocs({ target: { value: 'note-b' } })
      vm.setSearchMode('name')
      vi.advanceTimersByTime(300)
      await wrapper.vm.$nextTick()
      expect(mockGet).not.toHaveBeenCalled()
      expect(wrapper.findAll('.doc')).toHaveLength(1)
    })
  })

  it('treats nan text as empty in preview', () => {
    const wrapper = mountComponent()
    const docWithNan = wrapper.findAll('.note-summary')[2]
    expect(docWithNan.text()).toBe('')
  })
})
