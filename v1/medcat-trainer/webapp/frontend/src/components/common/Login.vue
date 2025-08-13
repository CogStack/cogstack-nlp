<template>
  <modal class="login" :closable="closable" @modal:close="$emit('login:close')">
    <template #header>
      <h3>Login</h3>
    </template>
    <template #body>
      <form @submit.prevent class="form">
        <label>Username:</label>
        <input v-model="uname" class="form-control" id="uname">
        <label>Password:</label>
        <input v-model="password" class="form-control" type="password" id="password">
        <a v-if="reset_pw" href="/reset_password/">Forgotten Password</a>
      </form>
      <span v-if="failed" class="text-danger">Username and/or password incorrect</span>
      <span v-if="failedAdminStatusCheck" class="text-danger">Cannot determine admin status of username</span>
    </template>
    <template #footer>
      <button class="login-submit btn btn-primary" @click="login()">Login</button>
    </template>
  </modal>
</template>

<script>
import Modal from '@/components/common/Modal.vue'
import EventBus from '@/event-bus'
import axios from 'axios'

const instance = axios.create({
  baseURL: axios.baseURL,
  headers: {}
})

export default {
  name: 'Login',
  props: {
    closable: Boolean
  },
  emits: [
    'login:close'
  ],
  components: {
    Modal
  },
  data () {
    return {
      uname: '',
      password: '',
      failed: false,
      failedAdminStatusCheck: false,
      reset_pw: import.meta.env.VITE_APP_EMAIL === '1',
    }
  },
  methods: {
    login () {
      let payload = {
        username: this.uname,
        password: this.password
      }

      instance.post('/api/api-token-auth/', payload, {}).then(resp => {
        this.$cookies.set('api-token', resp.data.token, { expires: 7 })
        this.$cookies.set('username', this.uname)
        this.$http.defaults.headers.common['Authorization'] = `Token ${this.$cookies.get('api-token')}`
        window.removeEventListener('keyup', this.keyup)
        this.$http.get(`/api/users/?username=${this.uname}`).then(resp => {
          if (resp.data.results.length > 0) {
            const adminState = resp.data.results[0].is_staff || resp.data.results[0].is_superuser
            const userId = resp.data.results[0].id
            this.$cookies.set('admin', adminState)
            this.$cookies.set('user-id', userId)
            EventBus.$emit('login:success')
          } else {
            this.failedAdminStatusCheck = true
            setTimeout(() => {
              this.$cookies.set('admin', false)
              this.$cookies.remove('user-id')
              EventBus.$emit('login:success')
            }, 1000)
          }
        }).catch(() => {
          this.failed = true
        })
      }).catch(() => {
        this.failed = true
      })
    },
    keyup (e) {
      if (e.keyCode === 13 && this.uname.length > 0 && this.password.length > 0) {
        this.login()
      }
    }
  },
  created () {
    window.addEventListener('keyup', this.keyup)
    this.$nextTick(function () {
      document.getElementById('uname').focus()
    })
  }
}
</script>

<style lang="scss">
.login-submit {
  margin-top: 10px;
}

.login {
  .modal-container {
    width: 400px;
  }
}


</style>
