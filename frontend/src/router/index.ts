/**
 * 路由表
 *
 * 用户端：/app        -> AppLayout（6 菜单项）
 * 管理端：/admin      -> AdminLayout（5 菜单项）
 * 公开：  /login      -> LoginView
 * 兜底：  /           重定向到 /app
 *         /:pathMatch(.*)*  -> NotFoundView
 */
import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router'
import { installGuards } from './guards'

const routes: RouteRecordRaw[] = [
  // ==================== 公开 ====================
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/LoginView.vue'),
    meta: { public: true, layout: 'blank' },
  },
  {
    path: '/',
    redirect: '/app',
  },

  // ==================== 用户端 ====================
  {
    path: '/app',
    component: () => import('@/views/AppLayout.vue'),
    meta: { requiresAuth: true },
    children: [
      { path: '', redirect: '/app/upload' },
      { path: 'upload', name: 'user-upload', component: () => import('@/views/user/UploadView.vue') },
      { path: 'top5', name: 'user-top5', component: () => import('@/views/user/Top5View.vue') },
      { path: 'heatmap', name: 'user-heatmap', component: () => import('@/views/user/HeatmapView.vue') },
      { path: 'stats', name: 'user-stats', component: () => import('@/views/user/StatsView.vue') },
      { path: 'change', name: 'user-change', component: () => import('@/views/user/ChangeView.vue') },
      { path: 'reports', name: 'user-reports', component: () => import('@/views/user/ReportsView.vue') },
    ],
  },

  // ==================== 管理端 ====================
  {
    path: '/admin',
    component: () => import('@/views/AdminLayout.vue'),
    meta: { requiresAuth: true, requiresAdmin: true },
    children: [
      { path: '', redirect: '/admin/users' },
      { path: 'users', name: 'admin-users', component: () => import('@/views/admin/UserManageView.vue') },
      { path: 'records', name: 'admin-records', component: () => import('@/views/admin/AllRecordsView.vue') },
      { path: 'training', name: 'admin-training', component: () => import('@/views/admin/TrainingJobsView.vue') },
      { path: 'convert', name: 'admin-convert', component: () => import('@/views/admin/ConvertView.vue') },
      { path: 'reports', name: 'admin-reports', component: () => import('@/views/admin/ReportManageView.vue') },
    ],
  },

  // ==================== 兜底 ====================
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: () => import('@/views/NotFoundView.vue'),
    meta: { public: true, layout: 'blank' },
  },
]

export const router = createRouter({
  history: createWebHistory(),
  routes,
})

installGuards(router)
