import { createRouter, createWebHistory } from 'vue-router'
import Home from '../views/Home.vue'
import TrainAnnotations from '../views/TrainAnnotations.vue'
import Demo from '../views/Demo.vue'
import Metrics from '../views/Metrics.vue'
import MetricsHome from '../views/MetricsHome.vue'
import ConceptDatabase from '../views/ConceptDatabase.vue'


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
          path: '/:pathMatch(.*)',
          name: 'home',
          component: Home
      }
  ]
})

export default router


