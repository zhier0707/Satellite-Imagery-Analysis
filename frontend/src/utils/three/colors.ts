/**
 * 3D 大屏 - 颜色与几何工具
 * ====================
 *
 * 职责:
 *   - LABEL_COLORS: EuroSAT 10 类土地利用 → 霓虹色
 *   - latLngToVec3: 经纬度 → 3D 球面坐标
 *
 * 设计原则:
 *   - 颜色与项目 DEFAULT_CATEGORY_COLORS 风格保持一致 (霓虹蓝/青绿主导)
 *   - latLngToVec3 公式来自 Three.js 官方示例,与 SphereGeometry 配合使用
 *   - 单一职责:本文件不依赖其它 three 工具,纯函数 + 常量
 */

/** 土地利用 10 类对应的霓虹色（与项目 colorMap 一致） */
export const LABEL_COLORS: Record<string, number> = {
  'AnnualCrop':           0x00E5FF,
  'Forest':               0x10F2C5,
  'HerbaceousVegetation': 0x84CC16,
  'Highway':              0xF59E0B,
  'Industrial':           0xEF4444,
  'Pasture':              0xFACC15,
  'PermanentCrop':        0xA3E635,
  'Residential':          0xEC4899,
  'River':                0x06B6D4,
  'SeaLake':              0x3B82F6,
}

/** 经纬度 → 3D 球面坐标（右手坐标系，与 Three.js SphereGeometry 保持一致）
 *
 * @param lng 经度 (-180 .. 180)
 * @param lat 纬度 (-90 .. 90)
 * @param radius 球面半径（地球主体为 50；点云应略大以避免 z-fighting）
 */
export function latLngToVec3(
  lng: number,
  lat: number,
  radius: number = 51,
): { x: number; y: number; z: number } {
  const phi = (90 - lat) * (Math.PI / 180)
  const theta = (lng + 180) * (Math.PI / 180)
  return {
    x: -(radius * Math.sin(phi) * Math.cos(theta)),
    y: radius * Math.cos(phi),
    z: radius * Math.sin(phi) * Math.sin(theta),
  }
}

/** 10 类的固定显示顺序（与 LABEL_COLORS 一一对应） */
export const EUROSAT_LABELS: string[] = [
  'AnnualCrop',
  'Forest',
  'HerbaceousVegetation',
  'Highway',
  'Industrial',
  'Pasture',
  'PermanentCrop',
  'Residential',
  'River',
  'SeaLake',
]
