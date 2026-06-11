import { describe, it, expect, vi } from 'vitest'
import { shallowMount, flushPromises } from '@vue/test-utils'
import { createRouter, createWebHistory } from 'vue-router'
import TrainAnnotations from '@/views/TrainAnnotations.vue'

const routes = [
  { path: '/train-annotations/:projectId/:docId?', name: 'train-annotations', component: TrainAnnotations }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

const project = {
  id: 1,
  name: 'Example Project',
  dataset: 1,
  require_entity_validation: true,
  validated_documents: [],
  prepared_documents: [123],
  cdb_search_filter: [],
  tasks: [],
  relations: []
}

// Mount the view without triggering the created() data-fetch cascade: the default
// $http.get returns a promise that never settles so we can drive fetchEntities directly.
const mountView = (getImpl: (url: string) => Promise<unknown>) => {
  const mockGet = vi.fn(getImpl)
  const wrapper = shallowMount(TrainAnnotations, {
    props: { projectId: 1 },
    global: {
      plugins: [router],
      mocks: {
        $http: { get: mockGet }
      }
    }
  })
  return { wrapper, mockGet }
}

describe('TrainAnnotations.vue fetchEntities', () => {
  it('surfaces an error and clears the loading state when annotated-entities fails', async () => {
    const { wrapper } = mountView((url) => {
      if (url.startsWith('/api/annotated-entities/')) {
        return Promise.reject({ response: { data: { message: 'Invalid token.' } } })
      }
      // Stall created() lifecycle requests so they don't interfere with the test.
      return new Promise(() => {})
    })

    wrapper.vm.project = project
    wrapper.vm.currentDoc = { id: 123, text: 'some clinical text' }
    wrapper.vm.loadingMsg = 'Preparing Document...'

    wrapper.vm.fetchEntities()
    await flushPromises()

    expect(wrapper.vm.errors.modal).toBe(true)
    expect(wrapper.vm.errors.message).toBe('Invalid token.')
    // The document must not be left stuck on a perpetual loading state.
    expect(wrapper.vm.loadingMsg).toBeNull()
    expect(wrapper.vm.nextEntSetUrl).toBeNull()
  })

  it('loads entities and clears the loading state on success', async () => {
    const { wrapper } = mountView((url) => {
      if (url.startsWith('/api/annotated-entities/')) {
        return Promise.resolve({
          data: {
            results: [{ id: 10, start_ind: 0, end_ind: 4, validated: 1, correct: 1 }],
            previous: null,
            next: null
          }
        })
      }
      return new Promise(() => {})
    })

    wrapper.vm.project = project
    wrapper.vm.currentDoc = { id: 123, text: 'some clinical text' }
    wrapper.vm.loadingMsg = 'Preparing Document...'

    wrapper.vm.fetchEntities()
    await flushPromises()

    expect(wrapper.vm.errors.modal).toBe(false)
    expect(wrapper.vm.loadingMsg).toBeNull()
    expect(wrapper.vm.ents).toHaveLength(1)
    expect(wrapper.vm.currentEnt.id).toBe(10)
  })
})
