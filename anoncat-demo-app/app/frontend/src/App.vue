<template>
  <div class="wrapper">
    <div class="title">
      <div class="cs-title">
        <img src="./assets/cs-logo.png" class="logo">
        CogStack
      </div>
      <div class="app-title">
        Anon
        <img src="./assets/logo.png" class="logo">
        AT
      </div>
      <span class="help">
        <v-icon icon="mdi-help-circle-outline" @click="helpModal = true"></v-icon>
      </span>
    </div>

    <modal v-if="helpModal" :closable="true" @modal:close="helpModal = false">
      <template #body>
        <p>Demo app for the deidentification of private health information using the CogStack AnonCAT model</p>
        <br>
        <p>Please DO NOT test with any real sensitive PHI data.</p>
        <br>
        <p>Local validation and fine-tuning available via <a href="https://github.com/CogStack/cogstack-nlp/tree/main/medcat-trainer">MedCATtrainer</a>.
          Email us, <a href="mailto:contact@cogstack.org">contact@cogstack.org</a>, to discuss model access, model performance, and your use case.
        </p>
        <br>
        <p>The following PHI items have been trained:</p>
        <v-table>
          <thead>
            <tr>
              <th>PHI Item</th>
              <th>Description</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>NHS Number</td>
              <td>UK National Health Service Numbers.</td>
            </tr>
            <tr>
              <td>Name</td>
              <td>All names, first, middle, last of patients, relatives, care providers etc.
                Importantly, does not redact conditions that are named after a name, e.g. "Parkinsons's disease".</td>
            </tr>
            <tr>
              <td>Date of Birth</td>
              <td>DOBs. Does not include other dates that may be in the record, i.e. dates of visit etc.</td>
            </tr>
            <tr>
              <td>Hospital Number</td>
              <td>A unique number provided by the hospital. Distinct from the NHS number</td>
            </tr>
            <tr>
              <td>Address Line</td>
              <td>Address lines - first, second, third or fourth</td>
            </tr>
            <tr>
              <td>Postcode</td>
              <td>UK postal codes - 6 or 7 alphanumeric codes as part of addresses</td>
            </tr>
            <tr>
              <td>Telephone Number</td>
              <td>Telephone numbers, extensions, mobile / cell phone numbers</td>
            </tr>
            <tr>
              <td>Email</td>
              <td>Email addresses</td>
            </tr>
            <tr>
              <td>Initials</td>
              <td>Patient, relatives, care provider name initials.</td>
            </tr>
          </tbody>
        </v-table>
      </template>
    </modal>

    <modal v-if="loginModal" :closable="false">
      <template #header>
        <p>Demo app for the deidentification of private health information using the CogStack AnonCAT model</p>
        <br>
        <p>Email us for access! <a href="mailto:contact@cogstack.org">contact@cogstack.org</a></p>
      </template>
      <template #body>
        <div class="login-form">
          <form @submit.prevent class="form">
            <v-text-field label="Password" v-model="password" type="password"
                          :error="failed" :error-messages="errorMessages"></v-text-field>
          </form>
          <!--          <span v-if="failedAdminStatusCheck" class="text-danger">Cannot determine admin status of username</span>-->
        </div>
      </template>
      <template #footer>
        <v-btn color="info" class="login-submit" @click="login()">Access</v-btn>
      </template>
    </modal>
  </div>
  <RouterView/>
</template>

<script lang="ts">
import { RouterLink, RouterView } from 'vue-router'
import axios from "axios";
import Modal from "./components/Modal.vue";

const instance = axios.create({
  baseURL: axios.baseURL,
  headers: {}
})

export default {
  name: 'App',
  components: {Modal},
  data () {
    return {
      loginModal: !this.$cookies.get('username'),
      helpModal: false,
      uname: this.$cookies.get('username') || null,
      version: '',
      password: '',
      failed: false,
      errorMessages: ''
    }
  },
  methods: {
    login () {
      let payload = {
        username: 'test',
        password: this.password
      }
      instance.post('/api/api-token-auth/', payload).then(resp => {
        // this.$cookies.set('api-token', resp.data.token)
        // this.$cookies.set('username', this.uname)
        axios.defaults.headers.common['Authorization'] = `Token ${resp.data.token}`
        window.removeEventListener('keyup', this.keyup)
        this.loginModal = false
      }).catch((err) => {
        this.failed = true
        this.errorMessages = 'Password incorrect'
      })
    },
    keyup (e) {
      if (e.keyCode === 13 && this.password.length > 0) {
        this.login()
      }
    },
    loginSuccessful () {
      this.loginModal = false
      if (this.$route.name !== 'home') {
        this.$router.push({ name: 'home' })
      }
    }
  },
  created () {
    window.addEventListener('keyup', this.keyup)
  }
}

</script>

<style scoped>
.wrapper {
  background: var(--color-background-mute);
  border: 0 !important;
  height: 95px !important;
}

.title {
  padding-left: 10px;
  color: var(--vt-c-white-soft);
  vertical-align: middle;
}

.cs-title {
  display: inline-block;
  width: 200px;
}

.app-title {
  width: calc(100% - 200px);
  padding-right: 200px;
  display: inline-block;
  text-align: center;
  font-size: 52px;
}

.logo {
  height: 52px;
  vertical-align: middle;
}

.help {
  padding-right: 20px;
  font-size: 23px;
  position: absolute;
  top: 35px;
  right: 30px;

  &:hover {
    cursor: pointer;
  }
}


</style>
