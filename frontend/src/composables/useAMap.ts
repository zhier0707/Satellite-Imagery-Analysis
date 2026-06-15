/**
 * useAMap - 父子组件间共享地图实例
 * ====================
 *
 * 设计目标:
 *   - AMapContainer 提供 map 实例
 *   - 子组件 (HeatmapLayer / PolygonLayer / POISearchBox) 通过 inject 拿到 map
 *   - 即便没有 AMapContainer,useAMap 也能返回"空实现",不抛错
 *
 * API:
 *   - { map, isReady, flyTo, setLayers, registerOverlay, unregisterOverlay, getOverlays }
 *
 * 注意:
 *   - 这里不直接调 AMap 构造,只做"实例共享 + 几何/图层操作";
 *   - 真正的 AMap 对象 (globalThis.AMap) 由其他 subagent 的 utils/amap/ 维护;
 *   - 我们 flyTo / setLayers 时只假设 map 已存在;若不存在,方法静默 noop。
 */
import { inject, provide, ref, type InjectionKey, type Ref, type InjectionKey as _Key } from 'vue'

/** 简单坐标点 [lng, lat] */
export type LngLat = [number, number]

/** 地图对外暴露的最小接口(duck-typing) */
export interface AMapLike {
  setCenter: (c: LngLat) => void
  setZoom: (z: number) => void
  getZoom: () => number
  getCenter?: () => LngLat
  add: (overlays: any[]) => void
  remove: (overlays: any[]) => void
  setLayers?: (layers: any[]) => void
  on?: (event: string, cb: (...args: any[]) => void) => void
  off?: (event: string, cb: (...args: any[]) => void) => void
  destroy?: () => void
}

interface AMapContext {
  map: Ref<AMapLike | null>
  isReady: Ref<boolean>
  overlays: Ref<any[]>
  setMap: (m: AMapLike | null) => void
  registerOverlay: (o: any) => void
  unregisterOverlay: (o: any) => void
}

const AMAP_KEY: InjectionKey<AMapContext> = Symbol('amap-context')

/** 父组件 (AMapContainer) 调用: 在 setup 内 provide */
export function provideAMap() {
  const map = ref<AMapLike | null>(null)
  const isReady = ref(false)
  const overlays = ref<any[]>([])

  const setMap = (m: AMapLike | null) => {
    map.value = m
    isReady.value = m !== null
    // 注册先前累积的 overlays
    if (m && overlays.value.length) {
      try { m.add(overlays.value) } catch (e) { /* swallow */ }
    }
  }
  const registerOverlay = (o: any) => {
    overlays.value.push(o)
    if (map.value) {
      try { map.value.add([o]) } catch (e) { /* swallow */ }
    }
  }
  const unregisterOverlay = (o: any) => {
    overlays.value = overlays.value.filter((x) => x !== o)
    if (map.value) {
      try { map.value.remove([o]) } catch (e) { /* swallow */ }
    }
  }

  const ctx: AMapContext = { map, isReady, overlays, setMap, registerOverlay, unregisterOverlay }
  provide(AMAP_KEY, ctx)
  return ctx
}

/** 子组件调用: 拿到父组件共享的 map;若没有,返回空实现不抛错 */
export function useAMap(): {
  map: Ref<AMapLike | null>
  isReady: Ref<boolean>
  overlays: Ref<any[]>
  flyTo: (point: LngLat, zoom?: number) => void
  setLayers: (layers: any[]) => void
  registerOverlay: (o: any) => void
  unregisterOverlay: (o: any) => void
} {
  const ctx = inject(AMAP_KEY, null)
  const noopMap = ref<AMapLike | null>(null)
  const noopReady = ref(false)
  const noopOverlays = ref<any[]>([])

  const safeCtx = ctx ?? {
    map: noopMap, isReady: noopReady, overlays: noopOverlays,
    setMap: () => {}, registerOverlay: () => {}, unregisterOverlay: () => {},
  }

  const flyTo = (point: LngLat, zoom?: number) => {
    const m = safeCtx.map.value
    if (!m) return
    try {
      m.setCenter(point)
      if (zoom !== undefined) m.setZoom(zoom)
    } catch (e) { /* swallow */ }
  }

  const setLayers = (layers: any[]) => {
    const m = safeCtx.map.value
    if (!m?.setLayers) return
    try { m.setLayers(layers) } catch (e) { /* swallow */ }
  }

  return {
    map: safeCtx.map,
    isReady: safeCtx.isReady,
    overlays: safeCtx.overlays,
    flyTo,
    setLayers,
    registerOverlay: safeCtx.registerOverlay,
    unregisterOverlay: safeCtx.unregisterOverlay,
  }
}
