<template>
  <div class="full-height">
    <header class="header-gradient">
      <div class="header-container">
        <div class="header-content">
          <!-- CogStack Branding and App Name -->
          <div class="branding-section">
            <div class="logo-container">
              <img src="./assets/brand-logo.png" alt="CogStack Logo" class="brand-logo" />
            </div>
            <div class="divider"></div>
            <h1 class="app-title" @click="navigateToHome">
              Med<img src="./assets/cat-logo.png" alt="MedCAT Logo" class="cat-logo" />AT
            </h1>
            <span class="version-id">{{ version }}</span>

            <!-- Navigation Links -->
            <div class="navigation-links">
              <router-link class="nav-link" to="/">Projects</router-link>
              <router-link class="nav-link" to="/metrics-reports">Metrics</router-link>
              <router-link class="nav-link" to="/model-explore">Concepts</router-link>
              <router-link class="nav-link" to="/demo">Try Model</router-link>
            </div>
          </div>



          <!-- Action Buttons -->
          <div class="action-buttons">
            <div class="user-section">
              <span v-if="!uname" class="login-link" @click="openLogin">Login</span>
              <span v-else class="user-info">
                <span class="username">({{ uname }}) <font-awesome-icon icon="user"></font-awesome-icon></span>
                <span class="logout-link" @click="logout">logout</span>
              </span>
            </div>
          </div>
        </div>
      </div>
    </header>
    <main class="main-content">
      <router-view/>
    </main>
    <login v-if="!useOidc && loginModal"
           @login:success="loginSuccessful"
           :closable="true"
           @login:close="loginModal=false" />
  </div>
</template>

<script>
import Login from '@/components/common/Login.vue'
import EventBus from '@/event-bus'

const USE_OIDC = import.meta.env.VITE_USE_OIDC === '1'

export default {
  name: 'App',
  components: { Login },
  data () {
    return {
      loginModal: false,
      uname: null,
      version: '',
      useOidc: USE_OIDC,
    }
  },
  methods: {
    navigateToHome () {
      this.$router.push('/')
    },

    openLogin () {
      if (!this.useOidc) {
        this.loginModal = true
      } else {
        // Kick off OIDC login if needed
        if (this.$keycloak && !this.$keycloak.authenticated) {
          this.$keycloak.login()
        }
      }
    },
    loginSuccessful () {
      if (!this.useOidc) {
        this.loginModal = false
        this.uname = this.$cookies.get('username')
      } else {
        this.updateOidcUser()
      }
      if (this.$route.name !== 'home') {
        this.$router.push({ name: 'home' })
      }
    },
    updateOidcUser () {
      if (this.$keycloak && this.$keycloak.tokenParsed) {
        this.uname = this.$keycloak.tokenParsed.preferred_username || null
        this.$http.defaults.headers.common['Authorization'] = `Bearer ${this.$keycloak.token}`
      }
    },
    logout () {
      this.uname = null
      this.$cookies.remove('username')
      this.$cookies.remove('api-token')
      this.$cookies.remove('admin')

      if (this.useOidc && this.$keycloak && this.$keycloak.authenticated) {
        this.$keycloak.logout({
          redirectUri: import.meta.env.VITE_LOGOUT_REDIRECT_URI || 'http://home.cogstack.localhost/'
        })
      } else {
        if (this.$route.name !== 'home') {
          this.$router.push({name: 'home'})
        } else {
          this.$router.go()
        }
      }
    }
  },
  mounted () {
    EventBus.$on('login:success', this.loginSuccessful)

    if (!this.useOidc) {
      this.uname = this.$cookies.get('username') || null
    } else {
      if (this.$keycloak && this.$keycloak.authenticated) {
        this.updateOidcUser()
        // Watch for token refresh events
        this.$keycloak.onAuthRefreshSuccess = () => this.updateOidcUser()
        this.$keycloak.onAuthSuccess = () => this.updateOidcUser()
      }
    }
  },
  beforeDestroy () {
    EventBus.$off('login:success', this.loginSuccessful)
  },
  created () {
    this.$http.get('/api/version/').then(resp => {
      this.version = resp.data || ''
    })
  }
}
</script>

<style scoped lang="scss">
.full-height {
  min-height: 100vh;
}

.header-gradient {
  background: linear-gradient(135deg, #126cad 0%, #3d0372 50%, #8e1b73 100%);
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 50;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.header-container {
  width: 100%;
  padding: 0 24px;
}

.header-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 0;
  min-height: 60px;
}

.main-content {
  padding-top: 81px;
  height: 100vh; /* Account for header height (60px + 32px padding) */
}

.branding-section {
  display: flex;
  align-items: center;
  gap: 16px;
}

.logo-container {
  display: flex;
  align-items: center;
}

.brand-logo {
  height: 48px;
  width: auto;
}

.divider {
  height: 24px;
  width: 1px;
  background-color: rgba(255, 255, 255, 0.3);
}

.app-title {
  font-size: 24px;
  font-weight: bold;
  color: white;
  display: flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
  margin: 0;
  text-decoration: none;

  &:hover {
    color: white;
    text-decoration: none;
  }
}

.cat-logo {
  height: 32px;
  width: 32px;
}

.navigation-links {
  display: flex;
  gap: 20px;
}

.nav-link {
  color: white;
  text-decoration: none;
  padding: 8px 0;
  border-bottom: 1px solid transparent;
  transition: all 0.2s ease;

  &:hover {
    color: white;
    border-bottom: 1px solid white;
    text-decoration: none;
  }

  &:focus {
    color: white
  }

  &.router-link-active {
    border-bottom: 1px solid white;
  }
}

.action-buttons {
  display: flex;
  gap: 8px;
  align-items: center;
}

.user-section {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-left: 16px;
}

.login-link {
  color: white;
  cursor: pointer;
  font-size: 14px;

  &:hover {
    opacity: 0.8;
  }
}

.user-info {
  display: flex;
  align-items: center;
  gap: 16px;
  color: white;
  font-size: 14px;
}

.username {
  display: flex;
  align-items: center;
  gap: 4px;
}

.logout-link {
  cursor: pointer;

  &:hover {
    opacity: 0.8;
  }
}

.version-id {
  font-size: 10px;
  color: rgba(255, 255, 255, 0.7);
  margin-left: 16px;
}

// Legacy styles for backward compatibility
.right {
  float: right;
}

.small {
  font-size: 14px;
  color: #fff !important;
}

.navbar {
  height: 60px;
  background-color: $navbar-bg;
}

.app-name {
  padding: 0 10px;
  font-size: 2.25rem;
  text-decoration: none;
  color: #fff;

  &:hover {
    color: #fff !important;
    text-decoration: none;
  }
  &:focus {
    color: #fff;
  }
}

.navbar-brand {
  color: #fff;
  border-bottom: 1px solid transparent;
  margin-left: 20px;
  padding: 3px 0;

  &:hover {
    color: #fff;
    border-bottom: 1px solid #fff;
  }
  &:focus {
    color: #fff;
  }
}

.link {
  display: inline-block;
  height: 25px;
  cursor: pointer;

  &:hover {
    opacity: 0.6;
  }
}

.logout {
  padding-left: 20px;
}

.icon {
  height: 38px;
  position: relative;
  bottom: 7px;
}

</style>
