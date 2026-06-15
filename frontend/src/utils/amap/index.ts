/**
 * 高德地图工具层 - 统一入口
 * ====================
 *
 * 用法：
 *   import { loadAMap, isAMapConfigured, geocode, textSearch, wgs84ToGcj02 } from '@/utils/amap'
 */

// ==================== SDK 加载 ====================
export { loadAMap, isAMapConfigured } from './loader'
export type { LoadAMapOptions } from './loader'

// ==================== 业务封装 ====================
export { geocode, regeocode } from './geocode'
export { textSearch, aroundSearch } from './poi'
export type { TextSearchParams, AroundSearchParams } from './poi'

// ==================== 坐标转换 ====================
export { wgs84ToGcj02, gcj02ToWgs84, convertCoord } from './coord'

// ==================== 业务类型与默认配色 ====================
export type {
  LngLat,
  GeoPoint,
  POI,
  GeocodeResult,
  RegeocodeResult,
  HeatPoint,
  Boundary,
  ColorMap,
} from './types'
export { DEFAULT_CATEGORY_COLORS } from './types'
