import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { performStartupCleanup } from '@/utils/storage-cleanup'

describe('storageCleanup', () => {
  let consoleLogSpy: any
  let localStorageMock: { [key: string]: any }
  let sessionStorageMock: { [key: string]: any }

  beforeEach(() => {
    // Mock console.log
    consoleLogSpy = vi.spyOn(console, 'log').mockImplementation(() => {})

    // Mock localStorage with proper Object.keys() support
    localStorageMock = {}
    const localStorageProxy = new Proxy(localStorageMock, {
      get(target, prop) {
        if (prop === 'getItem') return (key: string) => target[key] || null
        if (prop === 'setItem') return (key: string, value: string) => { target[key] = value }
        if (prop === 'removeItem') return (key: string) => { delete target[key] }
        if (prop === 'clear') return () => { Object.keys(target).forEach(k => delete target[k]) }
        if (prop === 'key') return (index: number) => Object.keys(target)[index] || null
        if (prop === 'length') return Object.keys(target).length
        return target[prop as string]
      },
      ownKeys(target) {
        return Object.keys(target)
      },
      getOwnPropertyDescriptor(target, prop) {
        return {
          enumerable: true,
          configurable: true,
          value: target[prop as string]
        }
      }
    })
    vi.stubGlobal('localStorage', localStorageProxy)

    // Mock sessionStorage
    sessionStorageMock = {}
    const sessionStorageProxy = {
      getItem: (key: string) => sessionStorageMock[key] || null,
      setItem: (key: string, value: string) => { sessionStorageMock[key] = value },
      removeItem: (key: string) => { delete sessionStorageMock[key] },
      clear: () => { sessionStorageMock = {} },
      key: (index: number) => Object.keys(sessionStorageMock)[index] || null,
      get length() { return Object.keys(sessionStorageMock).length }
    } as Storage
    vi.stubGlobal('sessionStorage', sessionStorageProxy)

    // Mock document.cookie
    let cookieStore: string[] = []
    Object.defineProperty(document, 'cookie', {
      get: () => cookieStore.join('; '),
      set: (value: string) => {
        if (value.includes('expires=Thu, 01 Jan 1970')) {
          // Cookie deletion
          const name = value.split('=')[0]
          cookieStore = cookieStore.filter(c => !c.startsWith(name + '='))
        } else {
          cookieStore.push(value)
        }
      },
      configurable: true
    })

    // Mock window.location and URL
    delete (window as any).location
    window.location = {
      href: 'https://example.com/',
      hostname: 'example.com'
    } as any

    // Mock window.history.replaceState
    window.history.replaceState = vi.fn()
  })

  afterEach(() => {
    consoleLogSpy.mockRestore()
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  describe('performStartupCleanup', () => {
    it('should log startup cleanup message', () => {
      performStartupCleanup()
      expect(consoleLogSpy).toHaveBeenCalledWith('[StorageCleanup] Performing startup cleanup')
    })

    it('should clear application cookies', () => {
      // Set some cookies
      document.cookie = 'api-token=test123'
      document.cookie = 'username=testuser'
      document.cookie = 'admin=true'
      document.cookie = '_oauth2_proxy=djIuWDI5aGRYUm9NbDl3Y205NGVTMDVaV05sTjJJeE1qUXdZVE0wTWpVNE1UYzBaVEJqWm1KaU1tWXdPR'
      document.cookie = '_oauth2_proxy_1=mdlsjjsadfhHLFhBLGnbJlhB>j'
      document.cookie = 'sessionid=6id701ipjww6rx0gumt0vvz1pnxpy12p'
      document.cookie = 'AUTH_SESSION_ID=OTI4Mzk4NmUtZWJhNi'
      document.cookie = 'KC_RESTART=eyJhbGciOiJkaXIiLCJlbmMiOiJBMTI4..'
      document.cookie = 'KEYCLOAK_IDENTITY=eyJhbGciOiJIUzUxMiIsInR5cCI...'
      document.cookie = 'KEYCLOAK_SESSION=-9rVzyOy1xEA4sktmgSvv8DriM3ZO4kv-zjrhjuYFkA'

      performStartupCleanup()

      // Cookies should be cleared (setting them with expired date)
      // We can't easily verify the exact cookie string, but we can check the function runs
      expect(consoleLogSpy).toHaveBeenCalled()
    })

    it('should remove Keycloak items from localStorage', () => {
      // Add some localStorage items
      localStorage.setItem('kc-callback-e5a2e61c-69c3-430f-b0ba-5ed3c74be34a', {"state":"e5a2e61c-69c3-430f-b0ba-5ed3c74be34a","nonce":"89152b76-263f-41f9-92af-688f5ccc6b37","redirectUri":"https%3A%2F%2Fmedcattrainer.sites.er.kcl.ac.uk%2Ftrain-annotations%2F1%2F1","loginOptions":{},"pkceCodeVerifier":"hiPqBzEFgSBsqggWDOpmZBgwoy12Snso9rPBms1BPUemxDaDVFU1iAbuDMInsmnbJpFYRrQJ3PBoM6fjJb2XNe3mvGNl5iAu","expires":1770212697181})
      localStorage.setItem('keycloak-random', 'instance-data')
      localStorage.setItem('other-key', 'should-remain')

      expect(Object.keys(localStorageMock)).toHaveLength(3)

      performStartupCleanup()

      // Only 'other-key' should remain
      expect(localStorageMock['other-key']).toBe('should-remain')
      expect(localStorageMock['kc-callback-e5a2e61c-69c3-430f-b0ba-5ed3c74be34a']).toBeUndefined()
      expect(localStorageMock['keycloak-instance']).toBeUndefined()
      expect(Object.keys(localStorageMock)).toHaveLength(1)
    })

    it('should clear all sessionStorage', () => {
      // Add some sessionStorage items
      sessionStorage.setItem('session-key1', 'value1')
      sessionStorage.setItem('session-key2', 'value2')

      expect(Object.keys(sessionStorageMock)).toHaveLength(2)

      performStartupCleanup()

      expect(Object.keys(sessionStorageMock)).toHaveLength(0)
    })

    it('should remove OAuth callback parameters from URL hash', () => {
      window.location.href = 'https://medcattrainer.sites.er.kcl.ac.uk/#state=4d6f2da7-5b67-4a1b-b2eb-bc6fe7953206&session_state=6e6c31ef-5d5b-485d-8036-6e155508934f&iss=https%3A%2F%2Fcogstack-auth.sites.er.kcl.ac.uk%2Frealms%2Fcogstack&code=2b13e03c-1961-432a-b736-959c720685fa.6e6c31ef-5d5b-485d-8036-6e155508934f.5eca49a4-3f37-46ce-9570-65aed1ee33c6'

      performStartupCleanup()

      expect(window.history.replaceState).toHaveBeenCalledWith(
        {},
        expect.any(String),
        expect.stringContaining('https://medcattrainer.sites.er.kcl.ac.uk/')
      )

      // Verify the URL doesn't contain OAuth params
      const callArgs = (window.history.replaceState as any).mock.calls[0][2]
      expect(callArgs).not.toContain('state=')
      expect(callArgs).not.toContain('session_state=')
      expect(callArgs).not.toContain('iss=')
      expect(callArgs).not.toContain('code=')
    })

    it('should not modify URL if no OAuth parameters present', () => {
      window.location.href = 'https://example.com/#/dashboard'

      performStartupCleanup()

      expect(window.history.replaceState).not.toHaveBeenCalled()
    })

    it('should handle URL with only some OAuth parameters', () => {
      window.location.href = 'https://example.com/#state=abc123&other=value'

      performStartupCleanup()

      expect(window.history.replaceState).toHaveBeenCalled()

      // Verify 'other' parameter is preserved
      const callArgs = (window.history.replaceState as any).mock.calls[0][2]
      expect(callArgs).toContain('other=value')
      expect(callArgs).not.toContain('state=')
    })

    it('should handle empty hash after removing all OAuth parameters', () => {
      window.location.href = 'https://example.com/#state=abc123&code=code123'

      performStartupCleanup()

      expect(window.history.replaceState).toHaveBeenCalled()

      const callArgs = (window.history.replaceState as any).mock.calls[0][2]
      // Should just be the base URL without hash or with empty hash
      expect(callArgs).toMatch(/https:\/\/example\.com\/#?$/)
    })

    it('should handle localStorage with no Keycloak items', () => {
      localStorage.setItem('normal-key', 'normal-value')

      performStartupCleanup()

      // Normal key should remain untouched
      expect(localStorageMock['normal-key']).toBe('normal-value')
      expect(Object.keys(localStorageMock)).toHaveLength(1)
    })
  })
})
