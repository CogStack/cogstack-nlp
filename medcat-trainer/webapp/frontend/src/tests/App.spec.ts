import { describe, it, expect, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createWebHistory } from 'vue-router'
import App from '../App.vue'
import { authCookieNames } from '@/authCookies'

const names = authCookieNames()
const cookieGet = (overrides: Record<string, string> = {}) =>
  vi.fn((key: string) => {
    if (key in overrides) return overrides[key]
    if (key === names.username) return 'testUser'
    return null
  })

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
            get: cookieGet(),
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
    expect(links.length).toBeGreaterThanOrEqual(4)
    expect(links[0].props('to')).toBe('/')
    expect(links[1].props('to')).toBe('/metrics-reports')
    expect(links[2].props('to')).toBe('/model-explore')
    expect(links[3].props('to')).toBe('/demo')
  })


  it('calls /api/version/ when created', async () => {
    const mockGet = vi.fn().mockResolvedValue({ data: 'v1.2.3' });
    mount(App, {
      global: {
        plugins: [router],
        mocks: {
          $http: { get: mockGet },
          $cookies: {
            get: cookieGet(),
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
          $http: { get: mockGet, defaults: { headers: { common: {} } } },
          $cookies: {
            get: cookieGet({ [names.token]: 'token' }),
            remove: vi.fn()
          }
        },
        stubs: ['login', 'font-awesome-icon', 'router-link', 'router-view']
      }
    })
    await router.isReady()
    await flushPromises()

    expect(wrapper.text()).toContain('testUser');
    expect(wrapper.find('.logout-link').exists()).toBe(true);
    expect(wrapper.vm.loginModal).toBe(false);
  });

  it('shows the project-admin link from this app admin cookie', async () => {
    const wrapper = mount(App, {
      global: {
        plugins: [router],
        mocks: {
          $http: { get: mockGet },
          $cookies: {
            get: cookieGet({ [names.admin]: 'true', [names.token]: 'token' }),
            remove: vi.fn()
          }
        },
        stubs: ['login', 'font-awesome-icon', 'router-view']
      }
    })
    await router.isReady()
    await flushPromises()

    const adminLink = wrapper.findAllComponents({ name: 'RouterLink' })
      .find(link => link.props('to') === '/project-admin')
    expect(adminLink).toBeTruthy()
  })

  it('does not treat a generic admin cookie from another app as this app admin', async () => {
    const wrapper = mount(App, {
      global: {
        plugins: [router],
        mocks: {
          $http: { get: mockGet },
          $cookies: {
            get: vi.fn((key: string) => {
              if (key === 'admin') return 'true'
              if (key === names.username) return 'testUser'
              return null
            }),
            remove: vi.fn()
          }
        },
        stubs: ['login', 'font-awesome-icon', 'router-view']
      }
    })
    await router.isReady()
    await flushPromises()

    const adminLink = wrapper.findAllComponents({ name: 'RouterLink' })
      .find(link => link.props('to') === '/project-admin')
    expect(adminLink).toBeUndefined()
  })

  it('does not show a logged-in header from a username cookie without a token', async () => {
    const wrapper = mount(App, {
      global: {
        plugins: [router],
        mocks: {
          $http: { get: mockGet, defaults: { headers: { common: {} } } },
          $cookies: {
            get: cookieGet(),
            remove: vi.fn()
          }
        },
        stubs: ['login', 'font-awesome-icon', 'router-view']
      }
    })
    await router.isReady()
    await flushPromises()

    expect(wrapper.find('.logout-link').exists()).toBe(false)
    expect(wrapper.vm.loginModal).toBe(true)
    const login = wrapper.findComponent({ name: 'login' })
    expect(login.exists()).toBe(true)
    expect(login.props('closable')).toBe(false)
  })

  it('keeps the login modal open until the user authenticates', async () => {
    const wrapper = mount(App, {
      global: {
        plugins: [router],
        mocks: {
          $http: { get: mockGet, defaults: { headers: { common: {} } } },
          $cookies: {
            get: vi.fn(() => null),
            remove: vi.fn()
          }
        },
        stubs: ['login', 'font-awesome-icon', 'router-view']
      }
    })
    await router.isReady()
    await flushPromises()

    expect(wrapper.vm.loginModal).toBe(true)
    expect(wrapper.findComponent({ name: 'login' }).props('closable')).toBe(false)

    wrapper.vm.onUnauthorized()
    await flushPromises()
    expect(wrapper.vm.sessionExpired).toBe(true)
    expect(wrapper.vm.loginModal).toBe(true)
  })
});
