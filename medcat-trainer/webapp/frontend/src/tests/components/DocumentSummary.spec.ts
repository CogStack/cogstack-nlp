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

  it('treats nan text as empty in preview', () => {
    const wrapper = mountComponent()
    const docWithNan = wrapper.findAll('.note-summary')[2]
    expect(docWithNan.text()).toBe('')
  })
})
