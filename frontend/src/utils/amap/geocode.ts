/**
 * 地理编码 / 逆地理编码 薄封装
 * ====================
 *
 * 业务层推荐用这层(类型与项目 types 对齐);
 * 直接调 api/index.ts 也行,这里只是把"lbs 命名空间"语义化封装。
 */

import { geocode as apiGeocode, regeocode as apiRegeocode } from '@/api'
import type { GeocodeResult, RegeocodeResult } from './types'

/**
 * 地址 → 经纬度
 * @throws 网络/业务异常时抛出,UI 层应捕获并显示 EmptyState
 */
export async function geocode(address: string): Promise<GeocodeResult> {
  if (!address || !address.trim()) {
    throw new Error('geocode: 地址不能为空')
  }
  return apiGeocode(address.trim())
}

/**
 * 经纬度 → 地址
 */
export async function regeocode(lng: number, lat: number): Promise<RegeocodeResult> {
  if (Number.isNaN(lng) || Number.isNaN(lat)) {
    throw new Error('regeocode: 经纬度不合法')
  }
  if (Math.abs(lng) > 180 || Math.abs(lat) > 90) {
    throw new Error('regeocode: 经纬度超出范围')
  }
  return apiRegeocode(lng, lat)
}
