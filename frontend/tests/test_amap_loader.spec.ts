/**
 * 高德 amap 工具层单测
 * ====================
 * 覆盖：
 * 1. isAMapConfigured() - Key 存在/缺失
 * 2. loadAMap() 拒绝未配置 Key
 * 3. geocode() 业务封装参数校验
 * 4. coord.ts - WGS84→GCJ02 转换结果在合理范围
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

// ==================== loader ====================
describe('amap/loader', () => {
  // 每次用例结束清理 import.meta.env 改动
  const originalKey = import.meta.env.VITE_AMAP_JS_KEY

  afterEach(() => {
    if (originalKey === undefined) {
      delete import.meta.env.VITE_AMAP_JS_KEY
    } else {
      import.meta.env.VITE_AMAP_JS_KEY = originalKey
    }
    vi.resetModules()
  })

  it('isAMapConfigured() returns true when key exists', async () => {
    import.meta.env.VITE_AMAP_JS_KEY = 'fake_key_for_test'
    const mod = await import('@/utils/amap/loader')
    expect(mod.isAMapConfigured()).toBe(true)
  })

  it('isAMapConfigured() returns false when key missing', async () => {
    delete import.meta.env.VITE_AMAP_JS_KEY
    const mod = await import('@/utils/amap/loader')
    expect(mod.isAMapConfigured()).toBe(false)
  })

  it('loadAMap() rejects with clear error when key missing', async () => {
    delete import.meta.env.VITE_AMAP_JS_KEY
    const mod = await import('@/utils/amap/loader')
    await expect(mod.loadAMap()).rejects.toThrow(/VITE_AMAP_JS_KEY 未配置/)
  })
})

// ==================== geocode 业务封装 ====================
describe('amap/geocode wrapper', () => {
  beforeEach(() => {
    vi.resetModules()
  })

  it('geocode() throws on empty address', async () => {
    // mock @/api 防止真实请求
    vi.doMock('@/api', () => ({
      geocode: vi.fn(),
      regeocode: vi.fn(),
    }))
    const mod = await import('@/utils/amap/geocode')
    await expect(mod.geocode('')).rejects.toThrow(/地址不能为空/)
    await expect(mod.geocode('   ')).rejects.toThrow(/地址不能为空/)
  })

  it('regeocode() throws on invalid coordinates', async () => {
    vi.doMock('@/api', () => ({
      geocode: vi.fn(),
      regeocode: vi.fn(),
    }))
    const mod = await import('@/utils/amap/geocode')
    await expect(mod.regeocode(Number.NaN, 39)).rejects.toThrow(/经纬度不合法/)
    await expect(mod.regeocode(200, 39)).rejects.toThrow(/经纬度超出范围/)
    await expect(mod.regeocode(116, 100)).rejects.toThrow(/经纬度超出范围/)
  })

  it('geocode() delegates to api layer on valid input', async () => {
    const apiGeocode = vi.fn().mockResolvedValue({
      formatted_address: '北京市海淀区中关村',
      location: [116.31, 39.99],
    })
    vi.doMock('@/api', () => ({
      geocode: apiGeocode,
      regeocode: vi.fn(),
    }))
    const mod = await import('@/utils/amap/geocode')
    const r = await mod.geocode('  北京市海淀区中关村  ')
    expect(apiGeocode).toHaveBeenCalledWith('北京市海淀区中关村')
    expect(r.formatted_address).toBe('北京市海淀区中关村')
  })
})

// ==================== coord 转换 ====================
describe('amap/coord - WGS84 <-> GCJ02', () => {
  it('天安门 WGS84 → GCJ02 偏移在 0.001-0.01 度范围内', async () => {
    const { wgs84ToGcj02 } = await import('@/utils/amap/coord')
    // 天安门 WGS84: 116.397428, 39.90923
    const [gLng, gLat] = wgs84ToGcj02(116.397428, 39.90923)
    const dLng = Math.abs(gLng - 116.397428)
    const dLat = Math.abs(gLat - 39.90923)
    // 火星坐标偏移典型 0.001-0.01 度
    expect(dLng).toBeGreaterThan(0.0005)
    expect(dLng).toBeLessThan(0.02)
    expect(dLat).toBeGreaterThan(0.0005)
    expect(dLat).toBeLessThan(0.02)
  })

  it('境外坐标保持不变', async () => {
    const { wgs84ToGcj02 } = await import('@/utils/amap/coord')
    // 纽约: 超出中国大陆范围
    const [gLng, gLat] = wgs84ToGcj02(-74.006, 40.7128)
    expect(gLng).toBe(-74.006)
    expect(gLat).toBe(40.7128)
  })

  it('GCJ02 → WGS84 迭代逆转换误差 < 1e-6', async () => {
    const { gcj02ToWgs84, wgs84ToGcj02 } = await import('@/utils/amap/coord')
    const original = [116.397428, 39.90923] as const
    const gcj = wgs84ToGcj02(original[0], original[1])
    const back = gcj02ToWgs84(gcj[0], gcj[1])
    expect(Math.abs(back[0] - original[0])).toBeLessThan(1e-6)
    expect(Math.abs(back[1] - original[1])).toBeLessThan(1e-6)
  })

  it('convertCoord 同坐标系直接返回', async () => {
    const { convertCoord } = await import('@/utils/amap/coord')
    const p: [number, number] = [116, 39]
    expect(convertCoord(p, 'WGS84', 'WGS84')).toEqual(p)
    expect(convertCoord(p, 'GCJ02', 'GCJ02')).toEqual(p)
  })
})
