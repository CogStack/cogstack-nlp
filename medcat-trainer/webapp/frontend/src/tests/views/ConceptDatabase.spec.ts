import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ConceptDatabase from '@/views/ConceptDatabase.vue'

const mockCdbsPage1 = {
  results: [
    { id: 1, name: 'CDB One' },
    { id: 2, name: 'CDB Two' }
  ],
  next: null
}

describe('ConceptDatabase.vue', () => {
  let mockGet
  beforeEach(() => {
    mockGet = vi.fn((url) => {
      if (url === '/api/concept-dbs/') {
        return Promise.resolve({ data: mockCdbsPage1 })
      }
      return Promise.resolve({ data: { results: [], next: null } })
    })
  })

  it('fetches concept databases (cdbs) on created', async () => {
    const wrapper = mount(ConceptDatabase, {
      global: {
        mocks: { $http: { get: mockGet } },
        stubs: ['concept-picker', 'concept-database-viz', 'font-awesome-icon', 'v-tooltip']
      }
    })
    await flushPromises()
    expect(mockGet).toHaveBeenCalledWith('/api/concept-dbs/')
    expect(wrapper.vm.cdbs).toEqual([
      { id: 1, name: 'CDB One' },
      { id: 2, name: 'CDB Two' }
    ])
  })
})
