/**
 * 路由守卫：实现三件事
 * 1. 未登录访问受保护路由 -> 跳 /login（带 redirect）
 * 2. user 访问 /admin -> 跳 /app + toast
 * 3. 已登录访问 /login -> 跳 角色对应 defaultRoute / 角色匹配的 queryRedirect
 */
import { Router, RouteLocationNormalized } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

export function installGuards(router: Router) {
  router.beforeEach(async (to: RouteLocationNormalized) => {
    const auth = useAuthStore()
    if (!auth.bootstrapped) {
      await auth.bootstrap()
    }

    // 1. 公开路由无需鉴权
    if (to.meta.public) {
      if (to.name === 'login' && auth.isAuthenticated) {
        // Phase C: 角色感知跳转 - admin 自动回管理端,user 回用户端
        const redirectQuery = to.query.redirect
        const target = auth.postLoginRedirect(
          typeof redirectQuery === 'string' ? redirectQuery : undefined,
        )
        return { path: target }
      }
      return true
    }

    // 2. 未登录 -> 跳登录
    if (!auth.isAuthenticated) {
      return { path: '/login', query: { redirect: to.fullPath } }
    }

    // 3. role 不匹配 -> 跳到对应端
    if (to.meta.requiresAdmin && !auth.isAdmin) {
      return { path: '/app' }
    }
    return true
  })
}
