import { describe, it, expect, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import MetaAnnotationTaskContainer from '@/components/usecases/MetaAnnotationTaskContainer.vue'

const mountContainer = () => {
  const mockGet = vi.fn((url: string) => {
    if (url === '/api/meta-tasks/') {
      return Promise.resolve({
        data: {
          results: [
            { id: 1, name: 'Temporality', description: 'When', values: [10, 11] },
            { id: 2, name: 'Negation', description: 'Affirmed or negated', values: [12, 13] }
          ]
        }
      })
    }
    if (url === '/api/meta-task-values/') {
      return Promise.resolve({
        data: {
          results: [
            { id: 10, name: 'Current' },
            { id: 11, name: 'Historical' },
            { id: 12, name: 'Affirmed' },
            { id: 13, name: 'Negated' }
          ]
        }
      })
    }
    if (url.startsWith('/api/meta-annotations/')) {
      return Promise.resolve({ data: { results: [] } })
    }
    return Promise.reject(new Error(`Unexpected request: ${url}`))
  })

  const wrapper = mount(MetaAnnotationTaskContainer, {
    props: {
      modelPackSet: true,
      taskIDs: [1, 2],
      selectedEnt: { id: 99 }
    },
    global: {
      mocks: {
        $http: { get: mockGet, put: vi.fn(), post: vi.fn(), delete: vi.fn() }
      }
    }
  })

  return { wrapper, mockGet }
}

describe('MetaAnnotationTaskContainer.vue', () => {
  it('renders fetched meta tasks in a scrollable list', async () => {
    const { wrapper } = mountContainer()
    await flushPromises()

    expect(wrapper.find('.meta-task-container').exists()).toBe(true)
    expect(wrapper.find('.meta-task-list').exists()).toBe(true)
    expect(wrapper.findAllComponents({ name: 'MetaAnnotationTask' })).toHaveLength(2)
    expect(wrapper.text()).toContain('Temporality')
    expect(wrapper.text()).toContain('Negation')
  })
})
