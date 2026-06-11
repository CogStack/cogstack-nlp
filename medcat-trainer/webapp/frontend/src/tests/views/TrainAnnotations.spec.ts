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

describe('TrainAnnotations.vue fetchData', () => {
  it('surfaces an error modal when the project request fails', async () => {
    const { wrapper } = mountView((url) => {
      if (url.startsWith('/api/project-annotate-entities/')) {
        return Promise.reject({ response: { status: 500, data: { message: 'Database unavailable' } } })
      }
      return new Promise(() => {})
    })

    wrapper.vm.fetchData()
    await flushPromises()

    expect(wrapper.vm.errors.modal).toBe(true)
    expect(wrapper.vm.errors.message).toBe('Database unavailable')
    expect(wrapper.vm.project).toBeNull()
  })

  it('does not show the error modal on 401 (handled globally by httpAuth)', async () => {
    const { wrapper } = mountView((url) => {
      if (url.startsWith('/api/project-annotate-entities/')) {
        return Promise.reject({ response: { status: 401, data: { detail: 'Invalid token.' } } })
      }
      return new Promise(() => {})
    })

    wrapper.vm.fetchData()
    await flushPromises()

    expect(wrapper.vm.errors.modal).toBe(false)
  })
})

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

  it('pages through document sets to reach a deep-linked doc beyond the first batch', async () => {
    // 15 single-doc pages: the target (id 12) only appears after the first
    // LOAD_NUM_DOC_PAGES (10) batch, exercising the recursive page-advance.
    const TOTAL_PAGES = 15
    const TARGET_ID = 12
    const pageUrl = (p: number) => `/api/documents/?dataset=1&page=${p}`
    const docsResponse = (page: number) => ({
      data: {
        results: [{ id: page, name: `doc-${page}`, text: `text ${page}` }],
        count: TOTAL_PAGES,
        previous: page === 1 ? null : pageUrl(page - 1),
        next: page === TOTAL_PAGES ? null : pageUrl(page + 1)
      }
    })

    await router.push({ name: 'train-annotations', params: { projectId: 1, docId: TARGET_ID } })

    const { wrapper, mockGet } = mountView((url) => {
      if (url.startsWith('/api/project-annotate-entities/')) {
        return Promise.resolve({
          data: { count: 1, results: [{ ...project, prepared_documents: [TARGET_ID] }] }
        })
      }
      if (url.startsWith('/api/documents/')) {
        // First call (no nextDocSetUrl) requests page 1; subsequent calls carry ?page=N.
        const match = url.match(/page=(\d+)/)
        const page = match ? Number(match[1]) : 1
        return Promise.resolve(docsResponse(page))
      }
      if (url.startsWith('/api/annotated-entities/')) {
        return Promise.resolve({ data: { results: [], previous: null, next: null } })
      }
      return new Promise(() => {})
    })

    wrapper.vm.fetchData()
    await flushPromises()

    // The deep-linked document is selected and every page was fetched exactly once.
    expect(wrapper.vm.currentDoc.id).toBe(TARGET_ID)
    const docPageCalls = mockGet.mock.calls.filter(c => String(c[0]).startsWith('/api/documents/'))
    expect(docPageCalls).toHaveLength(TOTAL_PAGES)
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
