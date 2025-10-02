<template>
  <div class="full-height">
    <nav class="navbar">
      <router-link class="app-name" to="/">Med<img class="icon" src="./assets/cat-logo.png" >AT</router-link>
      <router-link class="navbar-brand" to="/">Projects</router-link>
      <router-link class="navbar-brand" to="/metrics-reports">Metrics</router-link>
      <router-link class="navbar-brand" to="/model-explore">Concepts</router-link>
      <router-link class="navbar-brand" to="/demo">Try Model</router-link>
      <span class="version-id">{{ version }}</span>
      <a class="navbar-brand ml-auto small">
        <span v-if="!uname" class="link" @click="openLogin">Login</span>
        <span v-else>
          <span class="link">
            ({{ uname }}) <font-awesome-icon icon="user"></font-awesome-icon>
          </span>
          <span class="link logout" @click="logout">logout</span>
        </span>
      </a>
    </nav>
    <router-view/>
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
  display:inline-block;
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

.version-id {
  display: inline-block;
  float: right;
  font-size: 10px;
  padding: 0 20px;
  color: $color-2;
}

</style>
