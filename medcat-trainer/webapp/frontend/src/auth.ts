import type { App } from 'vue'
import Keycloak, { KeycloakConfig } from 'keycloak-js'
import axios from 'axios'

let keycloak: Keycloak

export const authPlugin = {
  install: async (app: App) => {
    const config: KeycloakConfig = {
      url: import.meta.env.VITE_KEYCLOAK_URL,
      realm: import.meta.env.VITE_KEYCLOAK_REALM,
      clientId: import.meta.env.VITE_KEYCLOAK_CLIENT_ID,
    }

    keycloak = new Keycloak(config)

    const authenticated = await keycloak.init({
      onLoad: 'login-required',
      pkceMethod: 'S256',
      checkLoginIframe: false,
    })

    if (!authenticated) {
      console.warn('User is not authenticated')
      window.location.reload()
    }

    // configure axios
    axios.defaults.headers.common['Authorization'] = `Bearer ${keycloak.token}`

    const refreshInterval = Number(import.meta.env.VITE_KEYCLOAK_TOKEN_REFRESH_INTERVAL) || 10000
    const minValidity = Number(import.meta.env.VITE_KEYCLOAK_TOKEN_MIN_VALIDITY) || 30

    setInterval(() => {
      keycloak.updateToken(minValidity)
        .then(refreshed => {
          if (refreshed) {
            axios.defaults.headers.common['Authorization'] = `Bearer ${keycloak.token}`
          }
        })
        .catch(err => {
          console.error('Failed to refresh token', err)
        })
    }, refreshInterval)


    app.config.globalProperties.$keycloak = keycloak
    app.config.globalProperties.$http = axios
  },
}
