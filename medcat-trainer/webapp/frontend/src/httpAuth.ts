import type { AxiosInstance } from 'axios'
import EventBus from './event-bus'

/**
 * Emitted when an authenticated request is rejected with a 401, i.e. the
 * stored token is no longer valid server-side (e.g. after a DB reset / fresh
 * deploy or an expired session). Listeners are responsible for prompting the
 * user to re-authenticate.
 */
export const UNAUTHORIZED_EVENT = 'auth:unauthorized'

const AUTH_COOKIES = ['api-token', 'username', 'admin', 'user-id']

// Guard so that a burst of parallel requests all returning 401 only triggers a
// single re-login prompt. Reset via resetUnauthorizedGuard() on login success.
let handlingUnauthorized = false

/** Clear axios Authorization and auth cookies together so they cannot diverge. */
export function clearClientAuth(http: AxiosInstance): void {
  delete http.defaults.headers.common['Authorization']
  for (const name of AUTH_COOKIES) {
    document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/`
  }
}

/** Clear stale auth state and notify the app that re-login is required. */
export function handleUnauthorized(http: AxiosInstance): void {
  if (handlingUnauthorized) {
    return
  }
  handlingUnauthorized = true

  clearClientAuth(http)
  EventBus.$emit(UNAUTHORIZED_EVENT)
}

/**
 * Traditional (non-OIDC) auth gate for project views.
 *
 * - No token cookie → force re-login (clears any leftover Authorization header).
 * - Token cookie present but Authorization header missing → restore the header
 *   so in-memory axios state matches the durable cookie.
 *
 * Returns false when the caller must stop and wait for re-login.
 */
export function ensureTraditionalAuth(
  http: AxiosInstance,
  token: string | null | undefined
): boolean {
  if (!token) {
    handleUnauthorized(http)
    return false
  }
  if (!http.defaults.headers.common['Authorization']) {
    http.defaults.headers.common['Authorization'] = `Token ${token}`
  }
  return true
}

/** Re-arm the guard once the user has successfully re-authenticated. */
export function resetUnauthorizedGuard(): void {
  handlingUnauthorized = false
}

/**
 * Register a global response interceptor that turns any 401 into a single
 * re-login prompt. The traditional login request uses its own axios instance,
 * so a wrong-password 401 there is unaffected by this handler.
 */
export function registerUnauthorizedInterceptor(http: AxiosInstance): number {
  return http.interceptors.response.use(
    response => response,
    error => {
      if (error?.response?.status === 401) {
        handleUnauthorized(http)
      }
      return Promise.reject(error)
    }
  )
}
