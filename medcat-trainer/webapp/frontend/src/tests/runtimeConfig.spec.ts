import { describe, it, expect, beforeEach, vi } from 'vitest'
import {
  getRuntimeConfig,
  isOidcEnabled,
  loadRuntimeConfig
} from '@/runtimeConfig'

describe('runtimeConfig', () => {
  beforeEach(() => {
    delete window.__RUNTIME_CONFIG__
    vi.restoreAllMocks()
  })

  describe('getRuntimeConfig', () => {
    it('returns defaults when window config is unset', () => {
      const config = getRuntimeConfig()
      expect(config.USE_OIDC).toBe('0')
      expect(config.KEYCLOAK_URL).toBe('')
      expect(config.KEYCLOAK_REALM).toBe('')
      expect(config.KEYCLOAK_CLIENT_ID).toBe('')
    })

    it('returns window config when set', () => {
      window.__RUNTIME_CONFIG__ = {
        USE_OIDC: '1',
        KEYCLOAK_URL: 'https://auth.example.com',
        KEYCLOAK_REALM: 'mct',
        KEYCLOAK_CLIENT_ID: 'frontend',
        KEYCLOAK_LOGOUT_REDIRECT_URI: 'https://app.example.com',
        KEYCLOAK_TOKEN_MIN_VALIDITY: 30,
        KEYCLOAK_TOKEN_REFRESH_INTERVAL: 60
      }
      const config = getRuntimeConfig()
      expect(config.USE_OIDC).toBe('1')
      expect(config.KEYCLOAK_URL).toBe('https://auth.example.com')
    })
  })

  describe('isOidcEnabled', () => {
    it('returns false when USE_OIDC is 0', () => {
      window.__RUNTIME_CONFIG__ = {
        USE_OIDC: '0',
        KEYCLOAK_URL: '',
        KEYCLOAK_REALM: '',
        KEYCLOAK_CLIENT_ID: '',
        KEYCLOAK_LOGOUT_REDIRECT_URI: '',
        KEYCLOAK_TOKEN_MIN_VALIDITY: 0,
        KEYCLOAK_TOKEN_REFRESH_INTERVAL: 0
      }
      expect(isOidcEnabled()).toBe(false)
    })

    it('returns true when USE_OIDC is 1', () => {
      window.__RUNTIME_CONFIG__ = {
        USE_OIDC: '1',
        KEYCLOAK_URL: 'https://auth.example.com',
        KEYCLOAK_REALM: 'mct',
        KEYCLOAK_CLIENT_ID: 'frontend',
        KEYCLOAK_LOGOUT_REDIRECT_URI: '',
        KEYCLOAK_TOKEN_MIN_VALIDITY: 0,
        KEYCLOAK_TOKEN_REFRESH_INTERVAL: 0
      }
      expect(isOidcEnabled()).toBe(true)
    })
  })

  describe('loadRuntimeConfig', () => {
    it('loads config from /static/config.json', async () => {
      const mockConfig = { USE_OIDC: '1', KEYCLOAK_URL: 'https://kc' }
      vi.stubGlobal(
        'fetch',
        vi.fn().mockResolvedValue({
          ok: true,
          json: async () => mockConfig
        })
      )

      await loadRuntimeConfig()

      expect(window.__RUNTIME_CONFIG__).toEqual(mockConfig)
      expect(fetch).toHaveBeenCalledWith('/static/config.json')
    })

    it('falls back to defaults when fetch fails', async () => {
      vi.stubGlobal(
        'fetch',
        vi.fn().mockResolvedValue({
          ok: false,
          status: 404,
          statusText: 'Not Found'
        })
      )

      await loadRuntimeConfig()

      expect(window.__RUNTIME_CONFIG__?.USE_OIDC).toBe('0')
    })

    it('falls back to defaults when fetch throws', async () => {
      vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network error')))

      await loadRuntimeConfig()

      // loadRuntimeConfig catches errors without setting config on network throw
      // getRuntimeConfig should still return defaults
      expect(getRuntimeConfig().USE_OIDC).toBe('0')
    })
  })
})
