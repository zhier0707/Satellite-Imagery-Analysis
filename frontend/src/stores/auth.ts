/**
 * Auth store - 认证状态管理
 *
 * state: { accessToken, refreshToken, user }
 * actions: login, register, logout, refresh, fetchMe
 *
 * 持久化策略：access/refresh token 与 user 一并存到 localStorage
 * （pinia-plugin-persistedstate 自动同步）
 */
import { defineStore } from 'pinia'
import * as api from '@/api'
import type { UserOut } from '@/api'

interface AuthState {
  accessToken: string
  refreshToken: string
  user: UserOut | null
  bootstrapped: boolean
}

export const useAuthStore = defineStore('auth', {
  state: (): AuthState => ({
    accessToken: '',
    refreshToken: '',
    user: null,
    bootstrapped: false,
  }),
  getters: {
    isAuthenticated: (s) => !!s.accessToken && !!s.user,
    isAdmin: (s) => s.user?.role === 'admin',
  },
  actions: {
    /** 应用启动时调用：有 token 就拉 /me 恢复身份 */
    async bootstrap() {
      this.accessToken = localStorage.getItem('access_token') || ''
      this.refreshToken = localStorage.getItem('refresh_token') || ''
      if (this.accessToken) {
        try {
          this.user = await api.fetchMe()
        } catch {
          this.clear()
        }
      }
      this.bootstrapped = true
    },
    async login(username: string, password: string) {
      const r = await api.login({ username, password })
      this.setSession(r.access_token, r.refresh_token, r.user)
    },
    async register(username: string, email: string, password: string) {
      const r = await api.register({ username, email, password })
      this.setSession(r.access_token, r.refresh_token, r.user)
    },
    async logout() {
      try {
        await api.logout()
      } catch {
        // 即便后端失败也要清本地
      }
      this.clear()
    },
    clear() {
      this.accessToken = ''
      this.refreshToken = ''
      this.user = null
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
    },
    setSession(access: string, refresh: string, user: UserOut) {
      this.accessToken = access
      this.refreshToken = refresh
      this.user = user
      localStorage.setItem('access_token', access)
      localStorage.setItem('refresh_token', refresh)
    },
  },
  persist: {
    key: 'auth',
    storage: localStorage,
    paths: ['accessToken', 'refreshToken', 'user'],
  },
})
