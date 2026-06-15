/**
 * 高德地图相关业务类型定义
 * ====================
 *
 * 与 AMap SDK 命名空间类型(types.d.ts)解耦,
 * 仅暴露本项目实际使用的纯数据接口。
 */

// ==================== 基础地理类型 ====================
/** 经纬度坐标,统一用 [lng, lat] 元组表示(与 AMap 内部一致) */
export type LngLat = [number, number]

/** 地理点(WGS84 或 GCJ02,通过 coordSystem 字段标注) */
export interface GeoPoint {
  lng: number
  lat: number
  /** 坐标系标识,前端做转换时使用 */
  coordSystem?: 'WGS84' | 'GCJ02'
}

// ==================== POI / 搜索 ====================
/** POI 关键字搜索结果(后端 /api/lbs/place/text 响应精简) */
export interface POI {
  id: string
  name: string
  /** 分类,如 '餐饮服务;中餐厅' */
  type?: string
  /** 地址 */
  address?: string
  location: LngLat
  /** 距离(米),仅周边搜索时有意义 */
  distance?: number
  /** 行政区编码 */
  adcode?: string
}

// ==================== 地理编码 ====================
/** 正向地理编码结果(地址 → 经纬度) */
export interface GeocodeResult {
  formatted_address: string
  location: LngLat
  /** 匹配级别,如 '详细地址' / '区县' / '城市' */
  level?: string
  adcode?: string
}

/** 逆地理编码结果(经纬度 → 地址) */
export interface RegeocodeResult {
  formatted_address: string
  addressComponent: {
    province?: string
    city?: string
    district?: string
    township?: string
    street?: string
    streetNumber?: string
  }
  /** 兴趣点列表 */
  pois?: Array<{ id: string; name: string; type?: string; location: LngLat }>
}

// ==================== 热力图 / 边界 ====================
/** 单个热力点 */
export interface HeatPoint {
  lng: number
  lat: number
  /** 权重 0-100 */
  weight: number
}

/** 类别边界多边形(环) */
export interface Boundary {
  id: string | number
  /** 类别名称(用于 colorMap 配色) */
  label: string
  /** 多边形环(经纬度数组) */
  path: LngLat[]
  /** 中心点(可选,便于 flyTo) */
  center?: LngLat
  /** 置信度 0-1 */
  confidence?: number
}

// ==================== 配色 ====================
/** 类别配色表(10 类对应 10 个典型配色) */
export type ColorMap = Record<string, string>

/** 默认 10 类配色(参考方案 6.5) */
export const DEFAULT_CATEGORY_COLORS: ColorMap = {
  '飞机': '#2563EB',
  '船舶': '#0891B2',
  '车辆': '#7C3AED',
  '桥梁': '#DB2777',
  '建筑物': '#EA580C',
  '道路': '#CA8A04',
  '跑道': '#16A34A',
  '体育场': '#059669',
  '储油罐': '#DC2626',
  '其他': '#525252',
}
