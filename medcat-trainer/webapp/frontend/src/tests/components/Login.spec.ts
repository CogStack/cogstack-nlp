import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import EventBus from '@/event-bus'

const { mockAxiosPost } = vi.hoisted(() => ({
  mockAxiosPost: vi.fn()
}))

vi.mock('axios', () => ({
  default: {
    create: () => ({ post: mockAxiosPost }),
    baseURL: ''
  }
}))

vi.mock('@/runtimeConfig.ts', () => ({
  isOidcEnabled: vi.fn(() => false)
}))

import Login from '@/components/common/Login.vue'

describe('Login.vue', () => {
  const mockGet = vi.fn()
  const mockCookies = {
    get: vi.fn((key: string) => (key === 'api-token' ? 'test-token' : undefined)),
    set: vi.fn(),
    remove: vi.fn()
  }

  beforeEach(() => {
    vi.clearAllMocks()
    mockAxiosPost.mockResolvedValue({ data: { token: 'test-token' } })
    mockGet.mockResolvedValue({
      data: {
        results: [{ id: 1, username: 'alice', is_staff: false, is_superuser: false }]
      }
    })
  })

  const mountLogin = () =>
    mount(Login, {
      props: { closable: true },
      global: {
        mocks: {
          $http: { get: mockGet, defaults: { headers: { common: {} } } },
          $cookies: mockCookies
        },
        stubs: {
          Modal: {
            template:
              '<div class="login-modal"><slot name="header" /><slot name="body" /><slot name="footer" /></div>'
          }
        }
      },
      attachTo: document.body
    })

  it('renders login form when OIDC is disabled', () => {
    const wrapper = mountLogin()
    expect(wrapper.find('.login-modal').exists()).toBe(true)
    expect(wrapper.text()).toContain('Login')
    expect(wrapper.find('#uname').exists()).toBe(true)
    expect(wrapper.find('#password').exists()).toBe(true)
  })

  it('posts credentials and sets cookies on successful login', async () => {
    const emitSpy = vi.spyOn(EventBus, '$emit')
    const wrapper = mountLogin()
    await flushPromises()

    const vm = wrapper.vm as { uname: string; password: string; login: () => void }
    vm.uname = 'alice'
    vm.password = 'secret'
    vm.login()
    await flushPromises()

    expect(mockAxiosPost).toHaveBeenCalledWith(
      '/api/api-token-auth/',
      { username: 'alice', password: 'secret' },
      {}
    )
    expect(mockCookies.set).toHaveBeenCalledWith('api-token', 'test-token', { expires: 7 })
    expect(mockCookies.set).toHaveBeenCalledWith('username', 'alice')
    expect(mockGet).toHaveBeenCalledWith('/api/users/?username=alice')
    expect(emitSpy).toHaveBeenCalledWith('login:success')
    emitSpy.mockRestore()
    wrapper.unmount()
  })

  it('shows error message on failed login', async () => {
    mockAxiosPost.mockRejectedValueOnce(new Error('unauthorized'))
    const wrapper = mountLogin()
    await flushPromises()

    const vm = wrapper.vm as {
      uname: string
      password: string
      login: () => void
      failed: boolean
    }
    vm.uname = 'alice'
    vm.password = 'wrong'
    vm.login()
    await flushPromises()

    expect(vm.failed).toBe(true)
    expect(wrapper.text()).toContain('incorrect')
    wrapper.unmount()
  })

  it('emits login:close when modal close is triggered', async () => {
    const wrapper = mountLogin()
    await wrapper.vm.$emit('login:close')
    expect(wrapper.emitted('login:close')).toBeTruthy()
    wrapper.unmount()
  })
})
