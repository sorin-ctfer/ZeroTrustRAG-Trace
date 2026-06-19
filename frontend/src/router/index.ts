import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/dashboard' },
    { path: '/dashboard', component: () => import('@/views/DashboardView.vue') },
    { path: '/external-knowledge', component: () => import('@/views/ExternalKnowledgeView.vue') },
    { path: '/rag-training', component: () => import('@/views/RagTrainingView.vue') },
    { path: '/poison-samples', component: () => import('@/views/PoisonSamplesView.vue') },
    { path: '/knowledge', component: () => import('@/views/KnowledgeView.vue') },
    { path: '/interactive-rag-lab', component: () => import('@/views/InteractiveRagLab.vue') },
    { path: '/poison-propagation/:session_id?', component: () => import('@/views/PoisonPropagationView.vue') },
    { path: '/interactive-correction/:session_id', component: () => import('@/views/InteractiveCorrectionView.vue') },
    { path: '/reports', component: () => import('@/views/ReportsView.vue') },
  ],
})

export default router
