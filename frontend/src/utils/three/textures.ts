/**
 * 程序化地球纹理生成
 * ====================
 *
 * 设计动机:
 *   - 避免引入外部贴图资源(版权 / 包体 / 加载等待)
 *   - 用 Canvas 2D + value noise + 大陆 mask 生成多层纹理
 *   - 100% 离线 / 0 字节资源,首屏即用
 *
 * 三种纹理:
 *   - createEarthTexture: 海陆 + 山地 + 沙漠(主贴图)
 *   - createCloudTexture:  半透明白噪声云层(独立球壳)
 *   - createNightTexture:  夜光城市斑块(预留,目前未挂场景)
 *
 * 单一职责:本文件只负责出 THREE.CanvasTexture,不创建场景/材质
 */
import * as THREE from 'three'

// ==================== 内部工具:value noise + fbm ====================
//
// 简化版 value noise: 哈希梯度 + 双线性插值。
// 比 simplex 实现更短,对"远观"地球够用。

function hash2D(x: number, y: number, seed: number): number {
  const h = Math.sin(x * 127.1 + y * 311.7 + seed * 17.31) * 43758.5453
  return h - Math.floor(h)
}

function smoothstep(t: number): number {
  return t * t * (3 - 2 * t)
}

function valueNoise2D(x: number, y: number, seed: number): number {
  const xi = Math.floor(x)
  const yi = Math.floor(y)
  const xf = x - xi
  const yf = y - yi
  const a = hash2D(xi,     yi,     seed)
  const b = hash2D(xi + 1, yi,     seed)
  const c = hash2D(xi,     yi + 1, seed)
  const d = hash2D(xi + 1, yi + 1, seed)
  const u = smoothstep(xf)
  const v = smoothstep(yf)
  return a * (1 - u) * (1 - v) + b * u * (1 - v) + c * (1 - u) * v + d * u * v
}

/**
 * 分形布朗运动: 多层 value noise 叠加,得"大陆级"高度场
 * 返回值 [0, 1]
 */
function fbm(x: number, y: number, seed: number, octaves: number = 4): number {
  let value = 0
  let amplitude = 0.5
  let frequency = 1
  let max = 0
  for (let i = 0; i < octaves; i++) {
    value += amplitude * valueNoise2D(x * frequency, y * frequency, seed + i * 13)
    max += amplitude
    amplitude *= 0.5
    frequency *= 2
  }
  return value / max
}

// ==================== 内部工具:RGB 工具 ====================

function lerpRgb(
  a: [number, number, number],
  b: [number, number, number],
  t: number,
): [number, number, number] {
  return [
    Math.round(a[0] + (b[0] - a[0]) * t),
    Math.round(a[1] + (b[1] - a[1]) * t),
    Math.round(a[2] + (b[2] - a[2]) * t),
  ]
}

function applyDefaults(tex: THREE.CanvasTexture): THREE.CanvasTexture {
  tex.colorSpace = THREE.SRGBColorSpace
  tex.needsUpdate = true
  return tex
}

// ==================== 大陆 mask ====================
//
// equirectangular 投影坐标(以 1024×512 为基准);center 调整到任意尺寸时按比例缩放。
// 7 块:亚欧、非洲、北美、南美、澳洲、南极;另有"北极"由顶部低高度自然形成。

interface Continent {
  name: string
  cx: number // 1024 基准下的中心 x
  cy: number // 512 基准下的中心 y
  rx: number
  ry: number
}

const CONTINENTS_BASE: Continent[] = [
  { name: 'Eurasia',    cx: 640, cy: 210, rx: 180, ry: 120 },
  { name: 'Africa',     cx: 520, cy: 320, rx: 90,  ry: 110 },
  { name: 'NAmerica',   cx: 230, cy: 230, rx: 130, ry: 100 },
  { name: 'SAmerica',   cx: 305, cy: 380, rx: 55,  ry: 80  },
  { name: 'Australia',  cx: 800, cy: 370, rx: 65,  ry: 45  },
  { name: 'Antarctica', cx: 512, cy: 502, rx: 260, ry: 28  },
]

/** 把基准 1024×512 的大陆坐标缩放到当前纹理尺寸 */
function buildContinents(width: number, height: number): Continent[] {
  const sx = width / 1024
  const sy = height / 512
  return CONTINENTS_BASE.map((c) => ({
    name: c.name,
    cx: c.cx * sx,
    cy: c.cy * sy,
    rx: c.rx * sx,
    ry: c.ry * sy,
  }))
}

/** 单点高度:fbm + 大陆椭圆增强 + 极地降权 */
function heightAt(
  x: number, y: number, w: number, h: number, continents: Continent[],
): number {
  const u = (x / w) * 4
  const v = (y / h) * 2
  let h0 = fbm(u, v, 1, 4)
  for (const c of continents) {
    const dx = (x - c.cx) / c.rx
    const dy = (y - c.cy) / c.ry
    const d2 = dx * dx + dy * dy
    if (d2 < 1) h0 = Math.min(1, h0 + (1 - d2) * 0.45)
  }
  const lat = (y / h) * 2 - 1
  if (Math.abs(lat) > 0.85) h0 *= 0.7
  return Math.max(0, Math.min(1, h0))
}

// ==================== 高度 → 颜色 ====================

/** 把"高度 0~1"映射到 RGB;沙漠区域由调用方在 isDesertZone 内额外判定 */
function earthColor(h: number): [number, number, number] {
  if (h < 0.42) {
    // 深海
    return lerpRgb([11, 37, 69], [30, 58, 95], h / 0.42)
  } else if (h < 0.50) {
    // 浅海
    return lerpRgb([30, 58, 95], [61, 106, 143], (h - 0.42) / 0.08)
  } else if (h < 0.52) {
    // 沙滩
    return lerpRgb([194, 168, 120], [181, 160, 94], (h - 0.50) / 0.02)
  } else if (h < 0.62) {
    // 草原
    return lerpRgb([93, 138, 77], [61, 106, 77], (h - 0.52) / 0.10)
  } else if (h < 0.78) {
    // 森林
    return lerpRgb([61, 106, 77], [45, 90, 61], (h - 0.62) / 0.16)
  } else if (h < 0.90) {
    // 山地
    return lerpRgb([107, 90, 61], [138, 122, 93], (h - 0.78) / 0.12)
  }
  // 雪线
  return [240, 240, 250]
}

/** 沙漠区域(撒哈拉 + 澳洲中部)用经纬度硬编码矩形框定 */
function isDesertZone(x: number, y: number, w: number, h: number): boolean {
  const sx = x / w
  const sy = y / h
  // 撒哈拉: 非洲中北部,经度 ~ 0~30%(非洲 x ≈ 0.42~0.58, y ≈ 0.45~0.70)
  if (sx > 0.42 && sx < 0.58 && sy > 0.45 && sy < 0.70) return true
  // 澳洲中部
  if (sx > 0.74 && sx < 0.84 && sy > 0.66 && sy < 0.78) return true
  return false
}

// ==================== 主入口:海陆贴图 ====================

/**
 * 生成完整地球纹理(海陆 + 山地 + 沙漠)
 *
 * @param width  纹理宽(默认 1024)
 * @param height 纹理高(默认 512,即 2:1 equirectangular 比例)
 * @returns THREE.CanvasTexture
 */
export function createEarthTexture(
  width: number = 1024,
  height: number = 512,
): THREE.CanvasTexture {
  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height
  const ctx = canvas.getContext('2d')!
  const img = ctx.createImageData(width, height)
  const data = img.data
  const continents = buildContinents(width, height)

  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const h = heightAt(x, y, width, height, continents)
      let rgb = earthColor(h)
      // 沙漠覆盖(在草原/森林高度区间内)
      if (h >= 0.55 && h < 0.70 && isDesertZone(x, y, width, height)) {
        const t = (h - 0.55) / 0.15
        rgb = lerpRgb([194, 160, 80], [212, 184, 120], t)
      }
      const idx = (y * width + x) * 4
      data[idx]     = rgb[0]
      data[idx + 1] = rgb[1]
      data[idx + 2] = rgb[2]
      data[idx + 3] = 255
    }
  }
  ctx.putImageData(img, 0, 0)
  return applyDefaults(new THREE.CanvasTexture(canvas))
}

// ==================== 云层纹理 ====================

/**
 * 半透明白噪声云层
 *
 * @param width  纹理宽(默认 1024)
 * @param height 纹理高(默认 512)
 */
export function createCloudTexture(
  width: number = 1024,
  height: number = 512,
): THREE.CanvasTexture {
  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height
  const ctx = canvas.getContext('2d')!
  const img = ctx.createImageData(width, height)
  const data = img.data

  for (let y = 0; y < height; y++) {
    const lat = (y / height) * 2 - 1
    // 极地云量减半,赤道带状云量增强
    const latMask = 1 - Math.pow(Math.abs(lat), 3) * 0.6
    for (let x = 0; x < width; x++) {
      const u = (x / width) * 6
      const v = (y / height) * 3
      let n = fbm(u, v, 99, 4)
      // 阈值化 + 对比度
      n = Math.max(0, n - 0.45) / 0.55
      n = Math.min(1, n * 1.4)
      const a = Math.round(255 * n * latMask)
      const idx = (y * width + x) * 4
      data[idx]     = 255
      data[idx + 1] = 255
      data[idx + 2] = 255
      data[idx + 3] = a
    }
  }
  ctx.putImageData(img, 0, 0)
  return applyDefaults(new THREE.CanvasTexture(canvas))
}

// ==================== 夜光纹理 ====================

/**
 * 夜光城市斑块(预留): 在"陆地"区域按概率撒霓虹黄绿小点
 *
 * 算法: 用 3 像素步长遍历 + 同 heightAt 判陆 → 4% 概率放一颗光斑
 */
export function createNightTexture(
  width: number = 1024,
  height: number = 512,
): THREE.CanvasTexture {
  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height
  const ctx = canvas.getContext('2d')!
  ctx.fillStyle = '#000000'
  ctx.fillRect(0, 0, width, height)
  const continents = buildContinents(width, height)
  const step = 3

  for (let y = step; y < height - step; y += step) {
    for (let x = step; x < width - step; x += step) {
      const h = heightAt(x, y, width, height, continents)
      if (h < 0.55) continue
      if (Math.random() > 0.05) continue
      const r = 1.2 + Math.random() * 1.6
      // 霓虹黄绿主调,蓝紫小概率点缀
      const tint = Math.random()
      let cr: number, cg: number, cb: number
      if (tint < 0.7) { cr = 230; cg = 220; cb = 100 } // 暖黄
      else if (tint < 0.9) { cr = 120; cg = 255; cb = 180 } // 霓虹绿
      else { cr = 100; cg = 160; cb = 255 } // 冷蓝
      const grad = ctx.createRadialGradient(x, y, 0, x, y, r * 3.5)
      grad.addColorStop(0, `rgba(${cr},${cg},${cb},0.85)`)
      grad.addColorStop(0.5, `rgba(${cr},${cg},${cb},0.3)`)
      grad.addColorStop(1, 'rgba(0,0,0,0)')
      ctx.fillStyle = grad
      ctx.fillRect(x - r * 3.5, y - r * 3.5, r * 7, r * 7)
    }
  }

  return applyDefaults(new THREE.CanvasTexture(canvas))
}
