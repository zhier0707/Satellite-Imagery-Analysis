<script setup lang="ts">
/**
 * ClassificationHeatmapLayer - 分类结果热力图
 * ====================
 *
 * 数据流:
 *   - 父视图 MapView 传入 points (HeatPoint[]) 与 opacity
 *   - 用 useAMap() 拿 map 实例,创建 AMap.HeatMap 覆盖物
 *   - 监听 points 变化 → setDataSet 增量更新
 *   - 监听 opacity 变化 → setOption({ opacity }) 热更新
 *
 * 视觉:
 *   - 4 段渐变 0.2 绿 / 0.4 黄 / 0.6 橙 / 0.8 红(冷-热语义)
 *   - radius 25,适配 2D 城市级缩放
 */
import { ref, watch, onBeforeUnmount } from 'vue'
import { useAMap } from '@/composables/useAMap'
import type { HeatPoint } from '@/utils/amap'

interface Props {
  points: HeatPoint[]
  opacity?: number
}
const props = withDefaults(defineProps<Props>(), { opacity: 0.7 })

const { map, isReady } = useAMap()
const heatMap = ref<any>(null)

const GRADIENT: Record<number, string> = {
  0.2: '#10B981', // 绿
  0.4: '#FBBF24', // 黄
  0.6: '#F97316', // 橙
  0.8: '#DC2626', // 红
}

function buildDataSet(points: HeatPoint[]): { data: Array<{ lng: number; lat: number; count: number }>; max: number } {
  const data = points.map((p) => ({ lng: p.lng, lat: p.lat, count: p.weight }))
  const max = data.reduce((m, d) => Math.max(m, d.count), 1)
  return { data, max }
}

function ensureHeatMap() {
  if (!map.value || heatMap.value) return
  const AMap = (globalThis as any).AMap
  if (!AMap?.HeatMap) return
  heatMap.value = new AMap.HeatMap(map.value, {
    radius: 25,
    opacity: props.opacity,
    gradient: GRADIENT,
    zooms: [3, 18],
  })
}

watch(
  () => props.points,
  (pts) => {
    if (!isReady.value) return
    ensureHeatMap()
    if (!heatMap.value) return
    const ds = buildDataSet(pts)
    heatMap.value.setDataSet(ds)
  },
  { immediate: true, deep: true },
)

watch(
  () => props.opacity,
  (op) => {
    if (!heatMap.value) return
    heatMap.value.setOptions({ opacity: op })
  },
)

onBeforeUnmount(() => {
  if (map.value && heatMap.value) {
    try { map.value.remove([heatMap.value]) } catch { /* swallow */ }
  }
  heatMap.value = null
})
</script>

<template>
  <!-- 纯逻辑组件,无视觉输出 -->
  <div class="heatmap-layer" style="display: none" />
</template>

<style scoped>
.heatmap-layer { display: none; }
</style>
