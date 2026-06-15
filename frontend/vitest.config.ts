import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

/**
 * Vitest 配置
 * ====================
 * 仅用于跑 utils/amap 相关的纯函数/SDK 配置检测测试。
 * 不覆盖 E2E、组件测试;后续如需扩展可在此追加 include 规则。
 */
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  test: {
    environment: 'jsdom',
    globals: false,
    include: ['tests/**/*.spec.ts'],
    /** 单测跑得快,短超时 */
    testTimeout: 10_000,
    hookTimeout: 10_000,
  },
})
