/**
 * 高德地图 JSAPI 加载工具
 * ====================
 *
 * 通过动态注入 loader.js,按需加载 SDK,避免在不需要地图的页面引入资源。
 * loader 内部会读取 window._AMapSecurityConfig(由 main.ts 预先设置)。
 *
 * 参考: ~/.agents/skills/amap-jsapi-skill/SKILL.md
 */

const LOADER_SRC = 'https://webapi.amap.com/loader.js'

export interface LoadAMapOptions {
  /** 需要预加载的插件,如 ['AMap.Scale', 'AMap.HeatMap', 'AMap.ToolBar'] */
  plugins?: string[]
  /** 强制重新加载(忽略缓存),仅在异常恢复时使用 */
  force?: boolean
}

// 单例 Promise:同会话内只加载一次 SDK
let cache: Promise<unknown> | null = null

/**
 * 异步加载高德地图 SDK,返回 AMap 全局对象
 *
 * @example
 *   const AMap = await loadAMap({ plugins: ['AMap.Scale', 'AMap.HeatMap'] })
 *   const map = new AMap.Map('map-container', { zoom: 12, center: [116.39, 39.90] })
 */
export function loadAMap(opts: LoadAMapOptions = {}): Promise<unknown> {
  const key = import.meta.env.VITE_AMAP_JS_KEY
  if (!key) {
    return Promise.reject(
      new Error('VITE_AMAP_JS_KEY 未配置,请检查 frontend/.env 文件'),
    )
  }
  if (cache && !opts.force) return cache

  cache = new Promise((resolve, reject) => {
    const AMapLoader = (window as any).AMapLoader
    if (AMapLoader) {
      return callLoader(AMapLoader).then(resolve, reject)
    }
    const script = document.createElement('script')
    script.src = LOADER_SRC
    script.async = true
    script.onload = () => {
      const loader = (window as any).AMapLoader
      if (!loader) {
        reject(new Error('AMapLoader 未在 window 上暴露'))
        return
      }
      callLoader(loader).then(resolve, reject)
    }
    script.onerror = () => reject(new Error('高德地图 loader.js 加载失败'))
    document.head.appendChild(script)
  })
  return cache

  function callLoader(loader: any) {
    return loader.load({
      key,
      version: '2.0',
      plugins: opts.plugins ?? [],
    })
  }
}

/** 检查 Key 是否已配置(用于 UI 上的友好提示) */
export function isAMapConfigured(): boolean {
  return Boolean(import.meta.env.VITE_AMAP_JS_KEY)
}
