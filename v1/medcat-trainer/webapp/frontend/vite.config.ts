import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    vueDevTools(),
  ],
  resolve: {
    alias: {
      vue: 'vue/dist/vue.esm-bundler.js',
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  build: {
    sourcemap: true,
    assetsDir: 'static'
  },
  server: {
    host: '127.0.0.1',
    proxy: {
      '^/api/concepts/*': {
        target: 'http://127.0.0.1:8983/solr',
        changeOrigin: true,
        secure: false,
        rewrite: (path) => path.replace(/\/api\/concepts/, '/')
      },
      '^/api/*': {
        target: 'http://127.0.0.1:8001'
      } 
    }
  },
  css: {
    preprocessorOptions: {
      scss: {
        additionalData: `
          @import "@/styles/_variables.scss";
          @import "@/styles/_common.scss";
          @import "@/styles/_tabs.scss";
        `
      }
    }
  }
})
