import { describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ConceptSummary from '@/components/common/ConceptSummary.vue'

describe('ConceptSummary.vue', () => {
  it('shows the CUI after fetching the entity label when no concept search index is configured', async () => {
    const mockGet = vi.fn((url: string) => {
      if (url === '/api/entities/10/') {
        return Promise.resolve({ data: { label: 'C0022660' } })
      }
      return Promise.reject(new Error(`Unexpected request: ${url}`))
    })

    const wrapper = mount(ConceptSummary, {
      props: {
        project: {},
        selectedEnt: null,
        altSearch: false,
        searchFilterDBIndex: null
      },
      global: {
        mocks: {
          $http: { get: mockGet }
        },
        stubs: {
          'concept-picker': true,
          'font-awesome-icon': true
        }
      }
    })

    await wrapper.setProps({
      selectedEnt: {
        id: 1,
        entity: 10,
        value: 'acute kidney failure',
        start_ind: 10,
        end_ind: 30,
        acc: 0.99,
        assignedValues: {
          'Concept Annotation': null
        },
        deleted: false
      }
    })
    await flushPromises()

    expect(mockGet).toHaveBeenCalledTimes(1)
    expect(mockGet).toHaveBeenCalledWith('/api/entities/10/')
    expect(wrapper.text()).toContain('C0022660')
  })

  it('shows the CUI when the concept lookup response has no results', async () => {
    const mockGet = vi.fn((url: string) => {
      if (url === '/api/entities/10/') {
        return Promise.resolve({ data: { label: 'C0022660' } })
      }
      if (url === '/api/search-concepts/?search=C0022660&cdbs=1') {
        return Promise.resolve({ data: { results: [] } })
      }
      return Promise.reject(new Error(`Unexpected request: ${url}`))
    })

    const wrapper = mount(ConceptSummary, {
      props: {
        project: {},
        selectedEnt: null,
        altSearch: false,
        searchFilterDBIndex: '1'
      },
      global: {
        mocks: {
          $http: { get: mockGet }
        },
        stubs: {
          'concept-picker': true,
          'font-awesome-icon': true
        }
      }
    })

    await wrapper.setProps({
      selectedEnt: {
        id: 1,
        entity: 10,
        value: 'acute kidney failure',
        start_ind: 10,
        end_ind: 30,
        acc: 0.99,
        assignedValues: {
          'Concept Annotation': null
        },
        deleted: false
      }
    })
    await flushPromises()

    expect(mockGet).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('C0022660')
  })

  it('shows concept details returned by the backend concept search endpoint', async () => {
    const mockGet = vi.fn((url: string) => {
      if (url === '/api/entities/10/') {
        return Promise.resolve({ data: { label: 'C0022660' } })
      }
      if (url === '/api/search-concepts/?search=C0022660&cdbs=1') {
        return Promise.resolve({
          data: {
            results: [{
              cui: 'C0022660',
              pretty_name: 'Acute kidney failure',
              type_ids: ['T047'],
              synonyms: ['AKF']
            }]
          }
        })
      }
      return Promise.reject(new Error(`Unexpected request: ${url}`))
    })

    const wrapper = mount(ConceptSummary, {
      props: {
        project: {},
        selectedEnt: null,
        altSearch: false,
        searchFilterDBIndex: '1'
      },
      global: {
        mocks: {
          $http: { get: mockGet }
        },
        stubs: {
          'concept-picker': true,
          'font-awesome-icon': true
        }
      }
    })

    await wrapper.setProps({
      selectedEnt: {
        id: 1,
        entity: 10,
        value: 'acute kidney failure',
        start_ind: 10,
        end_ind: 30,
        acc: 0.99,
        assignedValues: {
          'Concept Annotation': null
        },
        deleted: false
      }
    })
    await flushPromises()

    expect(mockGet).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('Acute kidney failure')
    expect(wrapper.text()).toContain('T047')
    expect(wrapper.text()).toContain('C0022660')
  })
})
