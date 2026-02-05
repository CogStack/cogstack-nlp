/**
 * Utility to clear application-specific browser storage on startup to prevent auth state conflicts
 */

function clearAuthRelatedCookies() {
  console.debug('[StorageCleanup] Clearing auth-related cookies')
  // Omit keycloak cookies ( 'AUTH_SESSION_ID', 'KC_RESTART', 'KEYCLOAK_IDENTITY', 'KEYCLOAK_SESSION',) as removing them breaks the oauth callback flow when OIDC auth is enabled
  const cookies = [
    'api-token', 'username', 'admin', 'user-id',
    'sessionid',
    '_oauth2_proxy', '_oauth2_proxy_csrf', '_oauth2_proxy_1', '_oauth2_proxy_2'
  ]
  cookies.forEach(name => {
    document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;`
  })
}

function clearSessionStorage() {
  console.debug('[StorageCleanup] Clearing sessionStorage')
  sessionStorage.clear()
}


export function performStartupCleanup(): void {
  console.log('[StorageCleanup] Performing startup cleanup')
  clearAuthRelatedCookies();
  clearSessionStorage();
}
