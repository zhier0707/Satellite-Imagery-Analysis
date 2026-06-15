/**
 * POI 关键字搜索 / 周边搜索 薄封装
 * ====================
 */

import { poiTextSearch as apiText, poiAroundSearch as apiAround } from '@/api'
import type { POI } from './types'

export interface TextSearchParams {
  keywords: string
  city?: string
  /** 单页返回数量,默认 20,上限 25(高德限制) */
  offset?: number
}

export interface AroundSearchParams {
  lng: number
  lat: number
  /** 半径,单位米,默认 1000,上限 50000 */
  radius?: number
  /** POI 分类码,如 '050000'(餐饮) / '080000'(生活服务) */
  types?: string
}

/** 关键字搜索 */
export async function textSearch(params: TextSearchParams): Promise<POI[]> {
  if (!params.keywords || !params.keywords.trim()) {
    throw new Error('poi.textSearch: keywords 不能为空')
  }
  return apiText({
    keywords: params.keywords.trim(),
    city: params.city,
    offset: params.offset,
  })
}

/** 周边搜索 */
export async function aroundSearch(params: AroundSearchParams): Promise<POI[]> {
  if (Number.isNaN(params.lng) || Number.isNaN(params.lat)) {
    throw new Error('poi.aroundSearch: 经纬度不合法')
  }
  return apiAround({
    lng: params.lng,
    lat: params.lat,
    radius: params.radius,
    types: params.types,
  })
}
