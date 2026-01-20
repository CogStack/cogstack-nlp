import { describe, it, expect, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import Demo from '@/views/Demo.vue'

describe('Demo.vue', () => {
  it('posts to /api/annotate-text/ with correct payload when annotate is clicked', async () => {
    vi.useFakeTimers()
    const mockPost = vi.fn().mockResolvedValue({ data: { entities: [], message: 'annotated!' } })
    const mockGet = vi.fn((url: string) => {
      if (url === '/api/project-annotate-entities/') {
        return Promise.resolve({
          data: {
            count: 1,
            results: [{ id: 42, name: 'Test Project', model_pack: 7, cdb_search_filter: [] }],
            next: null
          }
        })
      }
      if (url === '/api/modelpacks/') {
        return Promise.resolve({
          data: {
            count: 1,
            results: [{ id: 7, name: 'Test ModelPack' }],
            next: null
          }
        })
      }
      if (url === '/api/cache-modelpack/7/') {
        return Promise.resolve({ data: 'success' })
      }
      return Promise.resolve({ data: { count: 0, results: [], next: null } })
    })
    const wrapper = mount(Demo, {
      global: {
        mocks: {
          $http: { get: mockGet, post: mockPost }
        },
        stubs: {
          'clinical-text': true,
          'concept-summary': true,
          'concept-picker': true,
          'meta-annotations-summary': true
        }
      }
    })
    await flushPromises()
    // Paste CUIs (optional box) still drives payload
    await wrapper.setData({ cuiFilters: 'C1234,C5678' })

    // Enter message in the annotate component textarea
    const textarea = wrapper.find('textarea[name="message"]')
    expect(textarea.exists()).toBe(true)
    await textarea.setValue('Some text to annotate')
    // Debounced auto-annotate after 1500ms of inactivity
    vi.advanceTimersByTime(1500)
    await flushPromises()
    expect(mockPost).toHaveBeenCalledWith('/api/annotate-text/', expect.objectContaining({
      modelpack_id: 7,
      message: 'Some text to annotate',
      cuis: 'C1234,C5678',
      include_sub_concepts: false
    }))
    vi.useRealTimers()
  })
})
