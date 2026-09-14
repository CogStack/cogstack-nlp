import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ProjectAdmin from '@/views/ProjectAdmin.vue'

const emptyList = { data: { results: [] } }

function mountAdmin(http: { get: ReturnType<typeof vi.fn>; post: ReturnType<typeof vi.fn>; put?: ReturnType<typeof vi.fn> }) {
  return mount(ProjectAdmin, {
    global: {
      mocks: {
        $http: http,
        $toast: { success: vi.fn(), error: vi.fn() }
      },
      stubs: {
        'font-awesome-icon': true,
        'v-progress-circular': true,
        'plugin-slot': true,
        modal: true,
        'concept-picker': true,
        'projects-list': true,
        'model-packs-list': true,
        'model-pack-form': true,
        'datasets-list': true,
        'dataset-form': true,
        'users-list': true,
        'user-form': true
      }
    }
  })
}

describe('ProjectAdmin.vue project group create', () => {
  let mockGet: ReturnType<typeof vi.fn>
  let mockPost: ReturnType<typeof vi.fn>

  beforeEach(() => {
    mockGet = vi.fn((url: string) => {
      if (url === '/api/project-admin/projects/') {
        return Promise.resolve({ data: [] })
      }
      if (url === '/api/users/') {
        return Promise.resolve({
          data: { results: [{ id: 2, username: 'annotator' }, { id: 3, username: 'admin-user' }] }
        })
      }
      if (url === '/api/datasets/') {
        return Promise.resolve({ data: { results: [{ id: 10, name: 'Notes' }] } })
      }
      if (url === '/api/modelpacks/') {
        return Promise.resolve({
          data: { results: [{ id: 7, name: 'SNOMED', concept_db: 4 }] }
        })
      }
      if (url.startsWith('/api/concept-db-search-index-created/')) {
        return Promise.resolve({ data: { results: { 4: true } } })
      }
      return Promise.resolve(emptyList)
    })
    mockPost = vi.fn().mockResolvedValue({ data: { id: 99, name: 'Group A' } })
  })

  it('opens the form in group mode from the header toolbar', async () => {
    const wrapper = mountAdmin({ get: mockGet, post: mockPost })
    await flushPromises()
    await wrapper.find('.btn-create').trigger('click')
    const groupTab = wrapper.findAll('.form-type-btn').find(b => b.text().includes('Project Group'))
    expect(groupTab).toBeTruthy()
    await groupTab!.trigger('click')
    expect(wrapper.text()).toContain('Annotators')
    expect(wrapper.text()).toContain('Administrators')
    expect(wrapper.find('.form-toolbar').exists()).toBe(true)
  })

  it('posts to /api/project-groups/ when saving a new group', async () => {
    const wrapper = mountAdmin({ get: mockGet, post: mockPost })
    await flushPromises()
    const vm = wrapper.vm as unknown as {
      openCreateForm: (mode: string) => void
      formData: Record<string, unknown>
      saveProject: () => Promise<void>
    }
    vm.openCreateForm('group')
    vm.formData.name = 'Group A'
    vm.formData.dataset = 10
    vm.formData.model_pack = 7
    vm.formData.annotators = [2]
    await vm.saveProject()
    await flushPromises()
    expect(mockPost).toHaveBeenCalledWith(
      '/api/project-groups/',
      expect.objectContaining({
        name: 'Group A',
        dataset: 10,
        model_pack: 7,
        annotators: [2],
        create_associated_projects: true
      })
    )
  })

  it('does not post a group when annotators are missing', async () => {
    const wrapper = mountAdmin({ get: mockGet, post: mockPost })
    await flushPromises()
    const vm = wrapper.vm as unknown as {
      openCreateForm: (mode: string) => void
      formData: Record<string, unknown>
      saveProject: () => Promise<void>
      validationErrors: Record<string, string>
    }
    vm.openCreateForm('group')
    vm.formData.name = 'Group A'
    vm.formData.dataset = 10
    vm.formData.model_pack = 7
    await wrapper.vm.$nextTick()
    await vm.saveProject()
    expect(mockPost).not.toHaveBeenCalled()
    expect(vm.validationErrors.annotators).toBeTruthy()
  })
})
