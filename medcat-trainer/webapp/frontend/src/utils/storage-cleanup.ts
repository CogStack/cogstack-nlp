/**
 * Utility to clear application-specific browser storage on startup to prevent auth state conflicts
 */

function clearAuthRelatedCookies() {
  console.debug('[StorageCleanup] Clearing auth-related cookies')
  const cookies = [
    'api-token', 'username', 'admin', 'user-id',
    'sessionid', 'AUTH_SESSION_ID', 'KC_RESTART', 'KEYCLOAK_IDENTITY', 'KEYCLOAK_SESSION',
    '_oauth2_proxy', '_oauth2_proxy_csrf', '_oauth2_proxy_1', '_oauth2_proxy_2'
  ]
  cookies.forEach(name => {
    document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;`
  })
}

function clearKeycloakDataFromLocalStorage() {
  console.debug('[StorageCleanup] Clearing Keycloak data from localStorage')
  Object.keys(localStorage).forEach(key => {
    if (key.startsWith('kc') || key.includes('keycloak')) {
      localStorage.removeItem(key)
    }
  })
}

function clearSessionStorage() {
  console.debug('[StorageCleanup] Clearing sessionStorage')
  sessionStorage.clear()
}

function removeOAuthParamsFromUrl() {
  console.debug('[StorageCleanup] Removing OAuth params from URL')
  const url = new URL(window.location.href)
  const hash = url.hash

  if (hash.includes('state=') || hash.includes('code=')) {
    const hashParams = new URLSearchParams(hash.substring(1))
    ;['state', 'session_state', 'iss', 'code'].forEach(param => hashParams.delete(param))
    url.hash = hashParams.toString() ? hashParams.toString() : ''
    window.history.replaceState({}, document.title, url.toString())
  }
}

export function performStartupCleanup(): void {
  console.log('[StorageCleanup] Performing startup cleanup')
  clearAuthRelatedCookies();
  clearKeycloakDataFromLocalStorage();
  clearSessionStorage();
  removeOAuthParamsFromUrl();
}
