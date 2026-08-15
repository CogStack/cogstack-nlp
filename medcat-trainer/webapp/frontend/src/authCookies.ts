/**
 * Auth cookies must be unique per deployment.
 *
 * Browser cookies are scoped by name + domain + path, not port. Bare names
 * like `admin` / `api-token` are shared by every MCT version and every local
 * deploy on the same host (v1 on :8000 vs this app on :8001). The generic
 * `admin` cookie is also a common name for unrelated apps. Either collision
 * can leave this app logged in as a non-admin, so /project-admin never appears.
 */

const COOKIE_EXPIRES = '7d'

function sanitize(value: string, fallback = 'x'): string {
  return value.replace(/[^a-zA-Z0-9]+/g, '-').replace(/^-|-$/g, '') || fallback
}

export function authCookiePrefix(): string {
  const { hostname, port, protocol } = window.location
  const resolvedPort = port || (protocol === 'https:' ? '443' : '80')
  const base = sanitize(import.meta.env.BASE_URL || '/', 'root')
  return `mct-${sanitize(hostname, 'local')}-${resolvedPort}-${base}-`
}

export type AuthCookieNames = {
  token: string
  username: string
  admin: string
  userId: string
}

export function authCookieNames(): AuthCookieNames {
  const prefix = authCookiePrefix()
  return {
    token: `${prefix}api-token`,
    username: `${prefix}username`,
    admin: `${prefix}admin`,
    userId: `${prefix}user-id`
  }
}

export function authCookieNameList(): string[] {
  const names = authCookieNames()
  return [names.token, names.username, names.admin, names.userId]
}

export function isAdminCookieValue(value: unknown): boolean {
  return value === true || value === 'true'
}

export type TraditionalSession = {
  token: string
  username: string
  isAdmin: boolean
  userId: string | null
}

/**
 * A session is valid only when this app's token and username cookies are both
 * present. Token-without-username (or the reverse) is how the header can show
 * Login while the project list is still populated.
 */
export function readTraditionalSession(
  getCookie: (name: string) => unknown
): TraditionalSession | null {
  const names = authCookieNames()
  const token = getCookie(names.token)
  const username = getCookie(names.username)
  if (typeof token !== 'string' || token === '' || typeof username !== 'string' || username === '') {
    return null
  }
  const userId = getCookie(names.userId)
  return {
    token,
    username,
    isAdmin: isAdminCookieValue(getCookie(names.admin)),
    userId: userId == null || userId === '' ? null : String(userId)
  }
}

export function readTraditionalSessionFromDocument(): TraditionalSession | null {
  return readTraditionalSession(readRawCookie)
}

/** Last matching cookie wins (most recently written, given equal path). */
export function readRawCookie(name: string): string | null {
  const parts = document.cookie.split(';')
  for (let i = parts.length - 1; i >= 0; i--) {
    const [key, ...rest] = parts[i].trim().split('=')
    if (key !== name) {
      continue
    }
    const raw = rest.join('=')
    try {
      return decodeURIComponent(raw) || null
    } catch {
      return raw || null
    }
  }
  return null
}

export function isAdminFromDocumentCookie(): boolean {
  return readTraditionalSessionFromDocument()?.isAdmin === true
}

export function clearAuthCookies(): void {
  for (const name of authCookieNameList()) {
    document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/`
  }
}

export { COOKIE_EXPIRES }
