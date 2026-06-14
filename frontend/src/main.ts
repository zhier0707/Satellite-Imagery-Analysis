import { createApp } from 'vue'
import { createPinia } from 'pinia'
import piniaPluginPersistedstate from 'pinia-plugin-persistedstate'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import zhCn from 'element-plus/dist/locale/zh-cn.mjs'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import App from './App.vue'
import { router } from './router'

// ==================== 高德安全配置 ====================
// 必须在调用 AMapLoader.load() 之前执行,否则 JSAPI v2.0 会鉴权失败
const securityCode = import.meta.env.VITE_AMAP_SECURITY_CODE
if (securityCode) {
  ;(window as any)._AMapSecurityConfig = { securityJsCode: securityCode }
} else if (import.meta.env.VITE_AMAP_JS_KEY) {
  console.warn('[AMap] VITE_AMAP_SECURITY_CODE 未配置,JSAPI v2.0 鉴权可能失败')
}

const app = createApp(App)

// 全局注册 Element Plus 图标
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component as any)
}

// ==================== Pinia ====================
const pinia = createPinia()
pinia.use(piniaPluginPersistedstate)

app.use(pinia)
app.use(router)
app.use(ElementPlus, { locale: zhCn })
app.mount('#app')
