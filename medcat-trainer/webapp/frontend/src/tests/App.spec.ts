import { describe, it, expect, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createWebHistory } from 'vue-router'
import App from '../App.vue'

// Mock routes for router
const routes = [
  { path: '/', name: 'projects', component: { template: '<div>Projects</div>' } },
  { path: '/metrics-reports', name: 'metrics-reports', component: { template: '<div>Metrics</div>' } },
  { path: '/model-explore', name: 'model-explore', component: { template: '<div>Concepts</div>' } },
  { path: '/demo', name: 'demo', component: { template: '<div>Demo</div>' } }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// Mock $http
const mockGet = vi.fn().mockResolvedValue({ data: 'v1.2.3' })

vi.mock('vue', async () => {
  const actual = await vi.importActual<typeof import('vue')>('vue')
  return {
    ...actual,
  }
})

describe('App.vue', () => {
  it('renders navigation links and version', async () => {
    const wrapper = mount(App, {
      global: {
        plugins: [router],
        mocks: {
          $http: { get: mockGet },
          $cookies: {
            get: vi.fn((key) => key === 'username' ? 'testUser' : null),
            remove: vi.fn()
        }
        },
        stubs: ['login', 'font-awesome-icon', 'router-view']
      }
    })
    await router.isReady()
    await flushPromises()

    // Check version is rendered
    expect(wrapper.text()).toContain('v1.2.3')

    // Check that router-link stubs exist with correct props
    const links = wrapper.findAllComponents({ name: 'RouterLink' })
    expect(links.length).toBeGreaterThanOrEqual(5)
    expect(links[0].props('to')).toBe('/')
    expect(links[1].props('to')).toBe('/')
    expect(links[2].props('to')).toBe('/metrics-reports')
    expect(links[3].props('to')).toBe('/model-explore')
    expect(links[4].props('to')).toBe('/demo')
  })

  
  it('calls /api/version/ when created', async () => {
    const mockGet = vi.fn().mockResolvedValue({ data: 'v1.2.3' });
    mount(App, {
      global: {
        plugins: [router],
        mocks: {
          $http: { get: mockGet },
          $cookies: {
            get: vi.fn((key) => key === 'username' ? 'testUser' : null),
            remove: vi.fn()
          }
        },
        stubs: ['login', 'font-awesome-icon', 'router-view']
      }
    });
    await flushPromises();
    expect(mockGet).toHaveBeenCalledWith('/api/version/');
  });

  it('shows username and logout when logged in', async () => {
    const wrapper = mount(App, {
      global: {
        plugins: [router],
        mocks: {
          $http: { get: mockGet },
          $cookies: {
          get: vi.fn((key) => key === 'username' ? 'testUser' : null),
          remove: vi.fn()
        }
        },
        stubs: ['login', 'font-awesome-icon', 'router-link', 'router-view']
      },
      data() {
        return {
          uname: 'testuser',
          loginModal: false,
          version: 'v1.2.3'
        }
      }
    })
    await router.isReady()
    await flushPromises()

        expect(wrapper.text()).toContain('testuser');
        expect(wrapper.find('.logout').exists()).toBe(true);
      });
    });