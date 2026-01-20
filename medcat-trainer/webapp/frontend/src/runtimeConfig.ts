/**
 * Runtime Configuration Helper
 *
 * This module provides safe access to runtime configuration loaded from /config.json.
 * It uses the window object to store config.
 */

export interface RuntimeConfig {
  USE_OIDC: string
  KEYCLOAK_URL: string
  KEYCLOAK_REALM: string
  KEYCLOAK_CLIENT_ID: string
  LOGOUT_REDIRECT_URI: string
  KEYCLOAK_TOKEN_MIN_VALIDITY: number
  KEYCLOAK_TOKEN_REFRESH_INTERVAL: number
}

// Extend window interface for TypeScript
declare global {
  interface Window {
    __RUNTIME_CONFIG__?: RuntimeConfig
  }
}

/**
 * Default configuration
 * Used as fallback if runtime config isn't loaded
 */
const DEFAULT_CONFIG: RuntimeConfig = {
  USE_OIDC: '0',
  KEYCLOAK_URL: 'http://keycloak.cogstack.localhost/',
  KEYCLOAK_REALM: 'cogstack-realm',
  KEYCLOAK_CLIENT_ID: 'cogstack-medcattrainer-frontend',
  LOGOUT_REDIRECT_URI: 'http://launch.cogstack.localhost/',
  KEYCLOAK_TOKEN_MIN_VALIDITY: 10000,
  KEYCLOAK_TOKEN_REFRESH_INTERVAL: 30
};

/**
 * Load runtime configuration from /static/config.json
 */
export async function loadRuntimeConfig(): Promise<void> {
  try {
    const response = await fetch('/static/config.json');

    if (!response.ok) {
      console.log(`HTTP ${response.status}: ${response.statusText}`);
      window.__RUNTIME_CONFIG__ = DEFAULT_CONFIG;
    } else {
      const config = await response.json();
      window.__RUNTIME_CONFIG__ = config;
      console.log('[RuntimeConfig] OIDC enabled:', config.USE_OIDC === '1');
    }
  } catch (error) {
    console.log('Failed to load runtime configuration:', error);
  }
}

/**
 * Get runtime configuration with safe fallback to defaults
 */
export function getRuntimeConfig(): RuntimeConfig {
  return window.__RUNTIME_CONFIG__ || DEFAULT_CONFIG;
}

/**
 * Check if OIDC authentication is enabled
 */
export function isOidcEnabled(): boolean {
  return getRuntimeConfig().USE_OIDC === '1';
}
