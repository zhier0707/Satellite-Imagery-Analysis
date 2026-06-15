/**
 * AMap JSAPI 命名空间声明
 * ====================
 *
 * 手写最小可用类型,避免依赖 @types/amap-js-api。
 * 仅声明本项目实际使用的类与成员,未覆盖的 API 通过 any 兜底。
 *
 * 官方参考: https://lbs.amap.com/api/jsapi-v2/documentation
 */

declare namespace AMap {
  // ==================== 基础类型 ====================
  /** 经纬度坐标 [lng, lat] */
  type LngLatTuple = [number, number]

  /** 像素坐标 [x, y] */
  type Pixel = [number, number]

  /** 通用像素尺寸 [width, height] */
  type Size = [number, number]

  /** 地图视图模式 */
  type ViewMode = '2D' | '3D'

  /** 地图事件回调 */
  type EventHandler = (event: unknown) => void

  // ==================== LngLat ====================
  class LngLat {
    constructor(lng: number, lat: number)
    constructor(lng: number, lat: number, noWrap: boolean)
    lng: number
    lat: number
    equals(other: LngLat): boolean
    getLng(): number
    getLat(): number
    /** 偏移后的新 LngLat(单位:米) */
    offset(distanceX: number, distanceY: number): LngLat
  }

  // ==================== Pixel / Size ====================
  class Pixel_ {
    constructor(x: number, y: number)
    x: number
    y: number
  }

  // ==================== Map ====================
  interface MapOptions {
    view?: ViewMode
    center?: LngLatTuple | LngLat
    zoom?: number
    zooms?: [number, number]
    layers?: Layer[]
    mapStyle?: string
    /** 2D 模式: 'EPSG:3857' */
    crs?: string
    features?: Array<'bg' | 'point' | 'road' | 'building'>
    showLabel?: boolean
    rotateEnable?: boolean
    pitchEnable?: boolean
    jogEnable?: boolean
    dragEnable?: boolean
    zoomEnable?: boolean
    keyboardEnable?: boolean
    doubleClickZoom?: boolean
    scrollWheel?: boolean
    touchZoom?: boolean
    touchZoomCenter?: number
    container?: HTMLElement | string
    /** 地图 DOM 尺寸 */
    size?: Size
    /** 自动适应高度 */
    autoFitHeight?: boolean
  }

  class Map {
    constructor(container: HTMLElement | string, opts?: MapOptions)
    /** 设置地图中心 */
    setCenter(center: LngLatTuple | LngLat): void
    /** 获取地图中心 */
    getCenter(): LngLat
    /** 设置缩放级别 */
    setZoom(zoom: number): void
    getZoom(): number
    /** 缩放到指定范围(可带内边距像素) */
    setBounds(bounds: unknown, fitImmediately?: boolean, padding?: Pixel | Pixel[]): void
    /** 飞行到目标(带动画) */
    flyTo(target: { center?: LngLatTuple; zoom?: number; duration?: number }): void
    /** 销毁实例,释放资源 */
    destroy(): void
    /** 添加覆盖物 */
    add(overlays: OverlayLike | OverlayLike[]): void
    /** 移除覆盖物 */
    remove(overlays: OverlayLike | OverlayLike[]): void
    /** 清空指定类型覆盖物 */
    removeAllOverlays(type?: string): void
    /** 设置图层 */
    setLayers(layers: Layer[]): void
    getLayers(): Layer[]
    /** 像素 → 经纬度 */
    containerToLngLat(pixel: Pixel): LngLat
    /** 经纬度 → 像素 */
    lngLatToContainer(lngLat: LngLat): Pixel
    /** 注册事件 */
    on(eventName: string, handler: EventHandler): void
    off(eventName: string, handler: EventHandler): void
    /** DOM 元素 */
    getContainer(): HTMLElement
    /** 子地图模式 */
    getMapStyle(): string
    setMapStyle(style: string): void
  }

  // ==================== 图层 ====================
  interface LayerOptions {
    opacity?: number
    visible?: boolean
    zIndex?: number
  }

  class Layer {
    constructor(opts?: LayerOptions)
    getOpacity(): number
    setOpacity(opacity: number): void
    show(): void
    hide(): void
    getzIndex(): number
    setzIndex(zIndex: number): void
  }

  namespace TileLayer {
    class Satellite extends Layer {
      constructor(opts?: LayerOptions)
    }
    class Road extends Layer {
      constructor(opts?: LayerOptions)
    }
    class Traffic extends Layer {
      constructor(opts?: LayerOptions)
    }
  }

  // ==================== 覆盖物 ====================
  interface OverlayLike {
    setMap(map: Map | null): void
    getMap(): Map | null
    on?(event: string, handler: EventHandler): void
    off?(event: string, handler: EventHandler): void
  }

  // ---- Marker ----
  interface MarkerOptions {
    position?: LngLatTuple | LngLat
    icon?: string | unknown
    offset?: Pixel
    title?: string
    draggable?: boolean
    clickable?: boolean
    cursor?: string
    zIndex?: number
    /** 标签 */
    label?: { content: string; direction?: string; offset?: Pixel }
    /** 透明度 */
    opacity?: number
    /** 旋转角度(度) */
    angle?: number
    /** 是否可见 */
    visible?: boolean
  }

  class Marker implements OverlayLike {
    constructor(opts?: MarkerOptions)
    setPosition(position: LngLatTuple | LngLat): void
    getPosition(): LngLat
    setMap(map: Map | null): void
    getMap(): Map | null
    setIcon(icon: string | unknown): void
    on(event: string, handler: EventHandler): void
    off(event: string, handler: EventHandler): void
    setLabel(label: { content: string }): void
    setContent(content: HTMLElement | string): void
    setOffset(offset: Pixel): void
    show(): void
    hide(): void
  }

  // ---- InfoWindow ----
  interface InfoWindowOptions {
    isCustom?: boolean
    offset?: Pixel
    autoMove?: boolean
    closeWhenClickMap?: boolean
    content?: string | HTMLElement
  }

  class InfoWindow {
    constructor(opts?: InfoWindowOptions)
    open(map: Map, position: LngLatTuple | LngLat): void
    close(): void
    setContent(content: string | HTMLElement): void
    getIsOpen(): boolean
  }

  // ---- Polygon ----
  interface PolygonOptions {
    path?: LngLatTuple[] | LngLatTuple[][]
    strokeColor?: string
    strokeWeight?: number
    strokeOpacity?: number
    strokeStyle?: 'solid' | 'dashed'
    fillColor?: string
    fillOpacity?: number
    cursor?: string
    zIndex?: number
    bubble?: boolean
  }

  class Polygon implements OverlayLike {
    constructor(opts?: PolygonOptions)
    setMap(map: Map | null): void
    getMap(): Map | null
    setPath(path: LngLatTuple[] | LngLatTuple[][]): void
    getOptions(): PolygonOptions
    setOptions(opts: Partial<PolygonOptions>): void
    on(event: string, handler: EventHandler): void
    off(event: string, handler: EventHandler): void
    getBounds(): unknown
    contains(point: LngLat): boolean
  }

  // ---- Polyline ----
  interface PolylineOptions {
    path?: LngLatTuple[]
    strokeColor?: string
    strokeWeight?: number
    strokeOpacity?: number
    strokeStyle?: 'solid' | 'dashed'
    isOutline?: boolean
    outlineColor?: string
    showDir?: boolean
  }

  class Polyline implements OverlayLike {
    constructor(opts?: PolylineOptions)
    setMap(map: Map | null): void
    getMap(): Map | null
    setPath(path: LngLatTuple[]): void
    on(event: string, handler: EventHandler): void
    off(event: string, handler: EventHandler): void
  }

  // ---- HeatMap ----
  interface HeatMapOptions {
    radius?: number
    opacity?: number
    /** 渐变色 key-value */
    gradient?: Record<number, string>
    /** 0-1 缩放可见范围 */
    zooms?: [number, number]
    /** 权重上限 */
    max?: number
    /** 0-100,值越大越平滑 */
    valueBlock?: number
  }

  class HeatMap implements OverlayLike {
    constructor(map: Map, opts?: HeatMapOptions)
    setMap(map: Map | null): void
    getMap(): Map | null
    setDataSet(data: { data: Array<{ lng: number; lat: number; count: number }>; max?: number }): void
    getDataSet(): unknown
    setOptions(opts: Partial<HeatMapOptions>): void
    getOptions(): HeatMapOptions
    show(): void
    hide(): void
  }
}

// ==================== AMapLoader 全局对象 ====================
interface AMapLoaderConfig {
  key: string
  version?: string
  plugins?: string[]
}

interface AMapLoaderInstance {
  load(config: AMapLoaderConfig): Promise<unknown>
}

interface Window {
  /** 全局 loader,loader.js 加载完成后挂载 */
  AMapLoader?: AMapLoaderInstance
  /** 高德安全配置(由 main.ts 注入) */
  _AMapSecurityConfig?: { securityJsCode: string }
}
