import { describe, it, expect, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import Home from '@/views/Home.vue';
import { createRouter, createWebHistory } from 'vue-router'

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

    const mockCookies = {
      get: vi.fn((key) => {
        if (key === 'api-token') return 'token';
        if (key === 'admin') return 'false';
        return null;
      }),
      remove: vi.fn()
    };

    mount(Home, {
      global: {
        plugins: [router],
        mocks: {
          $http: { get: mockGet },
          $cookies: mockCookies
        },
        stubs: ['login', 'modal', 'project-list', 'v-data-table', 'transition', 'router-link', 'router-view']
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
});