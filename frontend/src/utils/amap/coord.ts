/**
 * WGS84 ↔ GCJ02 坐标转换
 * ====================
 *
 * GCJ02（火星坐标系）是中国大陆使用的加密坐标系，
 * 高德地图、腾讯地图、谷歌中国均使用此坐标。
 * WGS84（地球坐标系）是 GPS 设备原始输出，国际通用。
 *
 * 注意：
 * - 这里使用公开的近似算法（误差约 0.5-1 米），不是加密算法的逆向。
 * - 仅适用于中国大陆境内坐标；境外坐标保持 WGS84 不变。
 * - 高精度需求请使用专业纠偏库（如 gcoord）。
 *
 * 算法参考: https://lbs.amap.com/api/jsapi-v2/guide/import/import
 */

import type { LngLat } from './types'

// ==================== 常量 ====================
const PI = Math.PI
const A = 6378245.0 // 长半轴
const EE = 0.00669342162296594323 // 偏心率平方

// 中国大陆大致经纬度边界
const CHINA_LNG_MIN = 72.004
const CHINA_LNG_MAX = 137.8347
const CHINA_LAT_MIN = 0.8293
const CHINA_LAT_MAX = 55.8271

// ==================== 内部工具 ====================
function outOfChina(lng: number, lat: number): boolean {
  return lng < CHINA_LNG_MIN || lng > CHINA_LNG_MAX || lat < CHINA_LAT_MIN || lat > CHINA_LAT_MAX
}

function transformLat(x: number, y: number): number {
  let ret = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * Math.sqrt(Math.abs(x))
  ret += ((20.0 * Math.sin(6.0 * x * PI) + 20.0 * Math.sin(2.0 * x * PI)) * 2.0) / 3.0
  ret += ((20.0 * Math.sin(y * PI) + 40.0 * Math.sin((y / 3.0) * PI)) * 2.0) / 3.0
  ret += ((160.0 * Math.sin((y / 12.0) * PI) + 320.0 * Math.sin((y * PI) / 30.0)) * 2.0) / 3.0
  return ret
}

function transformLng(x: number, y: number): number {
  let ret = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * Math.sqrt(Math.abs(x))
  ret += ((20.0 * Math.sin(6.0 * x * PI) + 20.0 * Math.sin(2.0 * x * PI)) * 2.0) / 3.0
  ret += ((20.0 * Math.sin(x * PI) + 40.0 * Math.sin((x / 3.0) * PI)) * 2.0) / 3.0
  ret += ((150.0 * Math.sin((x / 12.0) * PI) + 300.0 * Math.sin((x / 30.0) * PI)) * 2.0) / 3.0
  return ret
}

// ==================== 公开 API ====================
/**
 * WGS84 → GCJ02 转换(近似值)
 * @param lng WGS84 经度
 * @param lat WGS84 纬度
 * @returns GCJ02 坐标
 */
export function wgs84ToGcj02(lng: number, lat: number): LngLat {
  if (outOfChina(lng, lat)) return [lng, lat]
  let dLat = transformLat(lng - 105.0, lat - 35.0)
  let dLng = transformLng(lng - 105.0, lat - 35.0)
  const radLat = (lat / 180.0) * PI
  let magic = Math.sin(radLat)
  magic = 1 - EE * magic * magic
  const sqrtMagic = Math.sqrt(magic)
  dLat = (dLat * 180.0) / (((A * (1 - EE)) / (magic * sqrtMagic)) * PI)
  dLng = (dLng * 180.0) / ((A / sqrtMagic) * Math.cos(radLat) * PI)
  return [lng + dLng, lat + dLat]
}

/**
 * GCJ02 → WGS84 转换(近似值,通过迭代求逆)
 *
 * GCJ02 是单向加密,严格意义上不可逆;
 * 这里采用反复"前向转换 - 减去偏移"的迭代逼近,
 * 3 次迭代后误差 < 1e-7 度(约 1 厘米)。
 */
export function gcj02ToWgs84(lng: number, lat: number): LngLat {
  if (outOfChina(lng, lat)) return [lng, lat]
  // 初值:用反向偏移估计
  let wgsLng = lng * 2 - wgs84ToGcj02(lng, lat)[0]
  let wgsLat = lat * 2 - wgs84ToGcj02(lng, lat)[1]
  // 迭代精化
  for (let i = 0; i < 3; i++) {
    const [gLng, gLat] = wgs84ToGcj02(wgsLng, wgsLat)
    wgsLng = lng - (gLng - wgsLng)
    wgsLat = lat - (gLat - wgsLat)
  }
  return [wgsLng, wgsLat]
}

/** 简化的元组版本 */
export function convertCoord(
  point: LngLat,
  from: 'WGS84' | 'GCJ02',
  to: 'WGS84' | 'GCJ02',
): LngLat {
  if (from === to) return point
  if (from === 'WGS84' && to === 'GCJ02') return wgs84ToGcj02(point[0], point[1])
  return gcj02ToWgs84(point[0], point[1])
}
