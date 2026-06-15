import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/dashboard' },
    { path: '/dashboard', component: () => import('@/views/DashboardView.vue') },
    { path: '/knowledge', component: () => import('@/views/KnowledgeView.vue') },
    { path: '/rag-detection', component: () => import('@/views/RagDetectionView.vue') },
    { path: '/agent-trust', component: () => import('@/views/AgentTrustView.vue') },
    { path: '/cascade-detection', component: () => import('@/views/CascadeView.vue') },
    { path: '/trace-graph', component: () => import('@/views/TraceGraphView.vue') },
    { path: '/correction', component: () => import('@/views/CorrectionView.vue') },
    { path: '/reports', component: () => import('@/views/ReportsView.vue') },
  ],
})

export default router
