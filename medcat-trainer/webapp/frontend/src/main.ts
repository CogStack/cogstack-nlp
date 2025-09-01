import 'bootstrap'
import 'bootstrap/dist/css/bootstrap.min.css'
import 'vue-select/dist/vue-select.css'
import 'vue-simple-context-menu/dist/vue-simple-context-menu.css'
import 'splitpanes/dist/splitpanes.css'

import '@/plugins/fontawesome'

import '@/assets/main.css'

import { createApp } from 'vue'

import App from './App.vue'
import router from './router'
import axios from 'axios'
import VueCookies from 'vue-cookies'
import vSelect from 'vue-select'
import VueSimpleContextMenu from 'vue-simple-context-menu'
import { FontAwesomeIcon } from '@fortawesome/vue-fontawesome'

import 'vuetify/styles'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'

const theme ={
  dark: false,
  colors: {
    primary: '#0072CE', //NHS Bright Blue
    danger: '#DA291C', //NHS Emergency Services Red
    warning: '#768692', // NHS Mid Grey
    info: '#E8EDEE', // NHS Pale Grey
    success: '#009639', // NHS Green
  }
}

const vuetify = createVuetify({
  components,
  directives,
  theme: {
    defaultTheme: 'theme',
    themes: {
      theme
    }
  }
})

const app = createApp(App)
app.config.globalProperties.$http = axios
app.component("v-select", vSelect)
app.component('vue-simple-context-menu', VueSimpleContextMenu)
app.component('font-awesome-icon', FontAwesomeIcon)
app.use(router)
app.use(VueCookies, { expires: '7d'})
app.use(vuetify);

(function () {
  const apiToken = document.cookie
    .split(';')
    .map(s => s.trim().split('='))
    .filter(s => s[0] === 'api-token')
  if (apiToken.length) {
    axios.defaults.headers.common['Authorization'] = `Token ${apiToken[0][1]}`
    axios.defaults.timeout = 6000000000
  }
})()

app.config.compilerOptions.whitespace = 'preserve';
app.mount('#app')
