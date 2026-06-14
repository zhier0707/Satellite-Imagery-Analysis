/// <reference types="vite/client" />

// ==================== Vite 环境变量类型 ====================
interface ImportMetaEnv {
  /** 高德 Web 端 (JS API) Key */
  readonly VITE_AMAP_JS_KEY: string
  /** 高德安全密钥 (securityJsCode) */
  readonly VITE_AMAP_SECURITY_CODE: string
  /** 是否启用地图模块 */
  readonly VITE_ENABLE_MAP: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

// ==================== Vue SFC ====================
declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<{}, {}, any>
  export default component
}
