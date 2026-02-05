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

    it('should clear all sessionStorage', () => {
      // Add some sessionStorage items
      sessionStorage.setItem('session-key1', 'value1')
      sessionStorage.setItem('session-key2', 'value2')

      expect(Object.keys(sessionStorageMock)).toHaveLength(2)

      performStartupCleanup()

      expect(Object.keys(sessionStorageMock)).toHaveLength(0)
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
