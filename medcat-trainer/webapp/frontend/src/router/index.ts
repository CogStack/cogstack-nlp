import { createRouter, createWebHistory } from 'vue-router'
import Home from '../views/Home.vue'
import TrainAnnotations from '../views/TrainAnnotations.vue'
import Demo from '../views/Demo.vue'
import Metrics from '../views/Metrics.vue'
import MetricsHome from '../views/MetricsHome.vue'
import ConceptDatabase from '../views/ConceptDatabase.vue'
import ProjectAdmin from '../views/ProjectAdmin.vue'
import { isOidcEnabled } from '../runtimeConfig'


const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
      {
          path: '/train-annotations/:projectId/:docId?',
          name: 'train-annotations',
          component: TrainAnnotations,
          props: true,
          // query: true
      },
      {
          path: '/metrics-reports/',
          name: 'metrics-reports',
          component: MetricsHome,
      },
      {
          path: '/metrics/:reportId/',
          name: 'metrics',
          component: Metrics,
          props: router => ({reportId: parseInt(router.params.reportId)})
      },
      {
          path: '/demo',
          name: 'demo',
          component: Demo
      },
      {
          path: '/model-explore',
          name: 'model-explore',
          component: ConceptDatabase
      },
      {
          path: '/project-admin',
          name: 'project-admin',
          component: ProjectAdmin,
          beforeEnter: (to, from, next) => {
            // Check if user is admin/staff
            // For non-OIDC: check cookie
            // For OIDC: backend will handle permission check
            const useOidc = isOidcEnabled()
            let isAdmin = false
            
            if (!useOidc) {
              // Check cookie for admin status
              const cookies = document.cookie.split(';').reduce((acc, cookie) => {
                const [key, value] = cookie.trim().split('=')
                acc[key] = value
                return acc
              }, {} as Record<string, string>)
              isAdmin = cookies['admin'] === 'true'
            } else {
              // For OIDC, allow access - backend will verify permissions
              // The backend API endpoint already checks permissions
              isAdmin = true
            }
            
            if (isAdmin) {
              next()
            } else {
              // Redirect to home if not admin
              next({ name: 'home' })
            }
          }
      },
      {
          path: '/:pathMatch(.*)',
          name: 'home',
          component: Home
      }
  ]
})

export default router


