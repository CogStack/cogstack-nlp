import { fileURLToPath, URL } from 'node:url'
import path from 'node:path'

import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

// Resolve env at module load so this stays a plain object. vitest.config.ts
// uses mergeConfig(), which cannot merge callback-style Vite configs.
const env = {
  ...loadEnv(process.env.MODE || process.env.NODE_ENV || 'development', process.cwd(), ''),
  ...process.env,
}
const mctEeRoot = env.MCT_EE_ROOT || path.resolve(
  fileURLToPath(new URL('../../../../cogstack-private/medcat-trainer-ee/frontend/src', import.meta.url))
)

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue(),
  ],
  resolve: {
    alias: {
      vue: 'vue/dist/vue.esm-bundler.js',
      '@': fileURLToPath(new URL('./src', import.meta.url)),
      // Always resolve so Vite/Rollup can analyse the dynamic import in
      // enterprise.ts. OSS builds get a local noop stub; EE builds point at
      // the private package when VITE_MCT_EE=1.
      '@mctee/enterprise': env.VITE_MCT_EE === '1'
        ? path.join(mctEeRoot, 'index.ts')
        : fileURLToPath(new URL('./src/plugins/enterprise-stub.ts', import.meta.url)),
    }
  },
  build: {
    sourcemap: true,
    assetsDir: 'static',
    chunkSizeWarningLimit: 1000,
    rollupOptions: {
      output: {
        manualChunks: {
          'vue-vendor': ['vue', 'vue-router'],
          'vuetify-vendor': ['vuetify'],
          'plotly-vendor': ['plotly.js-dist']
        }
      }
    }
  },
  server: {
    host: '127.0.0.1',
    proxy: {
      '^/api/concepts/*': {
        target: 'http://127.0.0.1:8983/solr',
        changeOrigin: true,
        secure: false,
        rewrite: (path: string) => path.replace(/\/api\/concepts/, '/')
      },
      '^/api/*': {
        target: 'http://127.0.0.1:8001'
      }
    }
  },
  css: {
    preprocessorOptions: {
      scss: {
        // Bootstrap 5.x still uses deprecated Sass color/import builtins; harmless until v6.
        // https://getbootstrap.com/docs/5.3/customize/sass/#sass-deprecation-warnings
        silenceDeprecations: [
          'color-functions',
          'global-builtin',
          'import',
          'if-function'
        ],
        additionalData: `
          @import "@/styles/_variables.scss";
          @import "@/styles/_common.scss";
          @import "@/styles/_tabs.scss";
        `
      }
    }
  }
})
