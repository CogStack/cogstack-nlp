import { describe, it, expect, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import Demo from '@/views/Demo.vue'

describe('Demo.vue', () => {
  it('posts to /api/annotate-text/ with correct payload when annotate is clicked', async () => {
    const mockPost = vi.fn().mockResolvedValue({ data: { entities: [], message: 'annotated!' } })
    const mockGet = vi.fn().mockResolvedValue({ data: { count: 1, results: [{ id: 42, name: 'Test Project', cdb_search_filter: [] }], next: null } })
    const wrapper = mount(Demo, {
      global: {
        mocks: {
          $http: { get: mockGet, post: mockPost }
        },
        stubs: ['clinical-text', 'concept-summary']
      }
    })
    await flushPromises()
    // Set up form values
    await wrapper.setData({
      selectedProject: { id: 42, name: 'Test Project', cdb_search_filter: [] },
      exampleText: 'Some text to annotate',
      cuiFilters: 'C1234,C5678'
    })
    // Find and click the annotate button
    await wrapper.find('button.btn-primary').trigger('click')
    await flushPromises()
    expect(mockPost).toHaveBeenCalledWith('/api/annotate-text/', {
      project_id: 42,
      message: 'Some text to annotate',
      cuis: 'C1234,C5678'
    })
  })
})
