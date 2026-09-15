import { describe, it, expect, beforeEach } from 'vitest'
import {
  authCookieNames,
  authCookiePrefix,
  isAdminCookieValue,
  isAdminFromDocumentCookie,
  readRawCookie,
  readTraditionalSession,
  clearAuthCookies
} from '@/authCookies'

function clearAllCookies() {
  for (const part of document.cookie.split(';')) {
    const name = part.split('=')[0]?.trim()
    if (name) {
      document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/`
    }
  }
}

describe('authCookies', () => {
  beforeEach(() => {
    clearAllCookies()
  })

  it('namespaces cookie names with host, port and base path', () => {
    const names = authCookieNames()
    const prefix = authCookiePrefix()
    const port = window.location.port || '80'

    expect(prefix).toMatch(/^mct-/)
    expect(prefix).toContain(port)
    expect(prefix).toContain('-root-')
    expect(names.token).not.toBe('api-token')
    expect(names.admin).not.toBe('admin')
    expect(names.username).not.toBe('username')
    expect(names.userId).not.toBe('user-id')
    expect(names.token).toBe(`${prefix}api-token`)
    expect(names.admin).toBe(`${prefix}admin`)
  })

  it('does not treat another app token as this app session', () => {
    document.cookie = 'api-token=other-app-token; path=/'
    expect(readRawCookie(authCookieNames().token)).toBeNull()
  })

  it('ignores a generic admin cookie from another app or MCT version', () => {
    const names = authCookieNames()
    document.cookie = 'admin=false; path=/'
    document.cookie = `${names.token}=tok; path=/`
    document.cookie = `${names.username}=alice; path=/`
    document.cookie = `${names.admin}=true; path=/`

    expect(isAdminFromDocumentCookie()).toBe(true)
    expect(readRawCookie('admin')).toBe('false')
  })

  it('does not treat admin=true without a token and username as a session', () => {
    document.cookie = `${authCookieNames().admin}=true; path=/`
    expect(isAdminFromDocumentCookie()).toBe(false)
    expect(readTraditionalSession(readRawCookie)).toBeNull()
  })

  it('requires both token and username for a traditional session', () => {
    const names = authCookieNames()
    const store: Record<string, string> = {
      [names.token]: 'tok',
      [names.admin]: 'true'
    }
    expect(readTraditionalSession(name => store[name])).toBeNull()

    store[names.username] = 'alice'
    const session = readTraditionalSession(name => store[name])
    expect(session).toEqual({
      token: 'tok',
      username: 'alice',
      isAdmin: true,
      userId: null
    })
  })

  it('treats boolean true and string true as admin', () => {
    expect(isAdminCookieValue(true)).toBe(true)
    expect(isAdminCookieValue('true')).toBe(true)
    expect(isAdminCookieValue(false)).toBe(false)
    expect(isAdminCookieValue('false')).toBe(false)
    expect(isAdminCookieValue(null)).toBe(false)
  })

  it('clearAuthCookies only removes this app namespaced cookies', () => {
    document.cookie = 'api-token=legacy; path=/'
    document.cookie = `${authCookieNames().token}=ours; path=/`

    clearAuthCookies()

    expect(readRawCookie(authCookieNames().token)).toBeNull()
    expect(readRawCookie('api-token')).toBe('legacy')
  })
})
