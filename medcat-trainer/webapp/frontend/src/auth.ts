import type { App } from 'vue'
import Keycloak, { KeycloakConfig } from 'keycloak-js'
import axios from 'axios'
import { getRuntimeConfig} from './runtimeConfig'

let keycloak: Keycloak

export const authPlugin = {
  install: async (app: App) => {
    const config: KeycloakConfig = {
      url: getRuntimeConfig().KEYCLOAK_URL,
      realm: getRuntimeConfig().KEYCLOAK_REALM,
      clientId: getRuntimeConfig().KEYCLOAK_CLIENT_ID,
    }
    keycloak = new Keycloak(config)

    const authenticated = await keycloak.init({
      onLoad: 'login-required',
      pkceMethod: 'S256',
      checkLoginIframe: false,
    })

    if (!authenticated) {
      console.warn('[AuthPlugin] User is not authenticated')
      window.location.reload()
    }

    console.log('[AuthPlugin] User authenticated successfully')

    // configure axios
    axios.defaults.headers.common['Authorization'] = `Bearer ${keycloak.token}`

    const refreshIntervalSecs = Number(getRuntimeConfig().KEYCLOAK_TOKEN_REFRESH_INTERVAL)
    const minValiditySecs = Number(getRuntimeConfig().KEYCLOAK_TOKEN_MIN_VALIDITY)

    setInterval(() => {
      keycloak.updateToken(minValiditySecs)
        .then(refreshed => {
          if (refreshed) {
            console.log('[AuthPlugin] Token refreshed')
            axios.defaults.headers.common['Authorization'] = `Bearer ${keycloak.token}`
          }
        })
        .catch(err => {
          console.error('[AuthPlugin] Failed to refresh token', err)
        })
    }, (refreshIntervalSecs * 1000))


    app.config.globalProperties.$keycloak = keycloak
    app.config.globalProperties.$http = axios
  },
}
