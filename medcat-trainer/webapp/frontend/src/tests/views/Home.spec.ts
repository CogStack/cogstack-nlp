import { describe, it, expect, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import Home from '@/views/Home.vue';
import { createRouter, createWebHistory } from 'vue-router'
import { authCookieNames } from '@/authCookies'

const names = authCookieNames()

const authCookies = (admin = 'false') => ({
  get: vi.fn((key: string) => {
    if (key === names.token) return 'token';
    if (key === names.username) return 'alice';
    if (key === names.admin) return admin;
    return null;
  }),
  remove: vi.fn()
})

// Mock routes for router
const routes = [
  { path: '/', name: 'home', component: Home }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

const testProjectsResponse = {
      "id": 1,
      "name": "Example Project",
      "description": "Example projects for Testing",
      "annotation_guideline_link": "",
      "create_time": "2025-09-08T06:24:34.380721Z",
      "last_modified": "2025-09-08T06:24:34.380737Z",
      "cuis": "",
      "annotation_classification": false,
      "meta_cat_predictions": false,
      "project_locked": false,
      "project_status": "A",
      "require_entity_validation": true,
      "train_model_on_submit": true,
      "add_new_entities": false,
      "restrict_concept_lookup": false,
      "terminate_available": true,
      "irrelevant_available": false,
      "deid_model_annotation": false,
      "enable_entity_annotation_comments": false,
      "polymorphic_ctype": 19,
      "dataset": 1,
      "group": null,
      "concept_db": 1,
      "vocab": 1,
      "model_pack": null,
      "members": [1],
      "validated_documents": [],
      "prepared_documents": [],
      "cdb_search_filter": [],
      "tasks": [],
      "relations": []
    };

  const testProjectProgress = {
    "1": {
        "validated_count": 1,
        "dataset_count": 1
    }
  };

describe('Home.vue', () => {
  it('gets project entities, groups, search index status and progress when user is logged in', async () => {
      const mockGet = vi.fn((url) => {
          if (url === '/api/behind-rp/') {
              return Promise.resolve({ data: { results: []} });
          }
          if (url === '/api/project-annotate-entities/') {
              return Promise.resolve({ data: { results: [testProjectsResponse], next: null } });
          }
          if (url.startsWith('/api/concept-db-search-index-created/')) {
              return Promise.resolve({ data: { results: []} });
          }
          if (url === '/api/project-progress/?projects=1') {
              return Promise.resolve({ data: testProjectProgress });
          }
          if (url.startsWith('/api/project-groups/')) {
              return Promise.resolve({ data: { results: [] } });
          }

          return Promise.resolve({});
      });

    const mockCookies = authCookies();

    mount(Home, {
      global: {
        plugins: [router],
        mocks: {
          $http: { get: mockGet },
          $cookies: mockCookies
        },
        stubs: ['login', 'modal', 'project-list', 'v-data-table', 'transition', 'router-link', 'router-view', 'font-awesome-icon', 'plugin-slot']
      }
    });

    await router.isReady();
    await flushPromises();

    // The second call should be to /api/project-annotate-entities/
    expect(mockGet).toHaveBeenCalledWith('/api/behind-rp/');
    expect(mockGet).toHaveBeenCalledWith('/api/project-annotate-entities/');
    expect(mockGet).toHaveBeenCalledWith('/api/concept-db-search-index-created/?cdbs=');
    expect(mockGet).toHaveBeenCalledWith('/api/project-progress/?projects=1');
    expect(mockGet).toHaveBeenCalledWith('/api/project-groups/?id__in=');
  });

  it('does not wipe auth cookies when project fetch fails with a non-401 error', async () => {
    const mockGet = vi.fn((url: string) => {
      if (url === '/api/behind-rp/') {
        return Promise.resolve({ data: true });
      }
      if (url === '/api/project-annotate-entities/') {
        return Promise.reject({ response: { status: 500, data: { message: 'boom' } } });
      }
      return Promise.resolve({});
    });
    const mockCookies = authCookies();

    const wrapper = mount(Home, {
      global: {
        plugins: [router],
        mocks: {
          $http: { get: mockGet },
          $cookies: mockCookies
        },
        stubs: ['login', 'modal', 'project-list', 'v-data-table', 'transition', 'router-link', 'router-view', 'font-awesome-icon', 'plugin-slot']
      }
    });

    await router.isReady();
    await flushPromises();

    expect(mockCookies.remove).not.toHaveBeenCalled();
    expect(wrapper.vm.loginSuccessful).toBe(true);
    expect(wrapper.vm.loadingProjects).toBe(false);
  });

  it('marks login unsuccessful on 401 without clearing cookies itself', async () => {
    const mockGet = vi.fn((url: string) => {
      if (url === '/api/behind-rp/') {
        return Promise.resolve({ data: true });
      }
      if (url === '/api/project-annotate-entities/') {
        return Promise.reject({ response: { status: 401, data: { detail: 'Invalid token.' } } });
      }
      return Promise.resolve({});
    });
    const mockCookies = authCookies();

    const wrapper = mount(Home, {
      global: {
        plugins: [router],
        mocks: {
          $http: { get: mockGet },
          $cookies: mockCookies
        },
        stubs: ['modal', 'project-list', 'v-data-table', 'transition', 'router-link', 'router-view', 'font-awesome-icon', 'plugin-slot']
      }
    });

    await router.isReady();
    await flushPromises();

    // Cookie wipe is owned by httpAuth on 401; Home must not double-clear.
    expect(mockCookies.remove).not.toHaveBeenCalled();
    expect(wrapper.vm.loginSuccessful).toBe(false);
  });

  it('shows Projects / Project Groups tabs for admins and switches the list', async () => {
    const mockGet = vi.fn((url: string) => {
      if (url === '/api/behind-rp/') {
        return Promise.resolve({ data: true });
      }
      if (url === '/api/project-annotate-entities/') {
        return Promise.resolve({ data: { results: [testProjectsResponse], next: null } });
      }
      if (url.startsWith('/api/concept-db-search-index-created/')) {
        return Promise.resolve({ data: { results: [] } });
      }
      if (url === '/api/project-progress/?projects=1') {
        return Promise.resolve({ data: testProjectProgress });
      }
      if (url.startsWith('/api/project-groups/')) {
        return Promise.resolve({ data: { results: [] } });
      }
      return Promise.resolve({});
    });
    const mockCookies = authCookies('true');

    const wrapper = mount(Home, {
      global: {
        plugins: [router],
        mocks: {
          $http: { get: mockGet },
          $cookies: mockCookies
        },
        stubs: ['modal', 'project-list', 'v-data-table', 'transition', 'router-link', 'router-view', 'font-awesome-icon', 'plugin-slot']
      }
    });

    await router.isReady();
    await flushPromises();

    const tabs = wrapper.findAll('.tab-button')
    expect(tabs).toHaveLength(2)
    expect(tabs[0].text()).toContain('Projects')
    expect(tabs[1].text()).toContain('Project Groups')
    expect(tabs[0].classes()).toContain('active')

    await tabs[1].trigger('click')
    expect(wrapper.vm.projectGroupView).toBe(true)
    expect(tabs[1].classes()).toContain('active')
  });

  it('does not render the project list without a complete session', async () => {
    const mockGet = vi.fn((url: string) => {
      if (url === '/api/behind-rp/') {
        return Promise.resolve({ data: true });
      }
      return Promise.resolve({});
    });
    const mockCookies = {
      get: vi.fn((key: string) => (key === names.token ? 'token' : null)),
      remove: vi.fn()
    };

    const wrapper = mount(Home, {
      global: {
        plugins: [router],
        mocks: {
          $http: { get: mockGet },
          $cookies: mockCookies
        },
        stubs: ['login', 'modal', 'project-list', 'v-data-table', 'transition', 'router-link', 'router-view', 'font-awesome-icon', 'plugin-slot']
      }
    });

    await router.isReady();
    await flushPromises();

    expect(wrapper.vm.loginSuccessful).toBe(false);
    expect(wrapper.find('.home-content').exists()).toBe(false);
    expect(mockGet).not.toHaveBeenCalledWith('/api/project-annotate-entities/');
  });

  it('clears loaded projects when the project fetch returns 401', async () => {
    const mockGet = vi.fn((url: string) => {
      if (url === '/api/behind-rp/') {
        return Promise.resolve({ data: true });
      }
      if (url === '/api/project-annotate-entities/') {
        return Promise.reject({ response: { status: 401, data: { detail: 'Invalid token.' } } });
      }
      return Promise.resolve({});
    });
    const mockCookies = authCookies();

    const wrapper = mount(Home, {
      global: {
        plugins: [router],
        mocks: {
          $http: { get: mockGet },
          $cookies: mockCookies
        },
        stubs: ['modal', 'project-list', 'v-data-table', 'transition', 'router-link', 'router-view', 'font-awesome-icon', 'plugin-slot']
      }
    });

    wrapper.vm.projects.items = [{ id: 1, name: 'Stale Project' }];
    await router.isReady();
    await flushPromises();

    expect(wrapper.vm.loginSuccessful).toBe(false);
    expect(wrapper.vm.projects.items).toEqual([]);
    expect(wrapper.find('.home-content').exists()).toBe(false);
  });

  it('shows Projects / Project Groups tabs for admins and switches the list', async () => {
    const mockGet = vi.fn((url: string) => {
      if (url === '/api/behind-rp/') {
        return Promise.resolve({ data: true });
      }
      if (url === '/api/project-annotate-entities/') {
        return Promise.resolve({ data: { results: [testProjectsResponse], next: null } });
      }
      if (url.startsWith('/api/concept-db-search-index-created/')) {
        return Promise.resolve({ data: { results: [] } });
      }
      if (url === '/api/project-progress/?projects=1') {
        return Promise.resolve({ data: testProjectProgress });
      }
      if (url.startsWith('/api/project-groups/')) {
        return Promise.resolve({ data: { results: [] } });
      }
      return Promise.resolve({});
    });
    const mockCookies = {
      get: vi.fn((key: string) => {
        if (key === 'api-token') return 'token';
        if (key === 'admin') return 'true';
        return null;
      }),
      remove: vi.fn()
    };

    const wrapper = mount(Home, {
      global: {
        plugins: [router],
        mocks: {
          $http: { get: mockGet },
          $cookies: mockCookies
        },
        stubs: ['login', 'modal', 'project-list', 'v-data-table', 'transition', 'router-link', 'router-view', 'font-awesome-icon', 'plugin-slot']
      }
    });

    await router.isReady();
    await flushPromises();

    const tabs = wrapper.findAll('.tab-button')
    expect(tabs).toHaveLength(2)
    expect(tabs[0].text()).toContain('Projects')
    expect(tabs[1].text()).toContain('Project Groups')
    expect(tabs[0].classes()).toContain('active')

    await tabs[1].trigger('click')
    expect(wrapper.vm.projectGroupView).toBe(true)
    expect(tabs[1].classes()).toContain('active')
  });
});
