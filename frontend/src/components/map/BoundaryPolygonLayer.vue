<script setup lang="ts">
/**
 * BoundaryPolygonLayer - 类别边界多边形
 * ====================
 *
 * 视觉:
 *   - 按 label 从 DEFAULT_CATEGORY_COLORS 选 fillColor 与 strokeColor
 *   - fillOpacity 0.35,strokeWeight 2(克制学术风)
 *   - click → emit('select', boundary) → 父组件显示 el-popover
 *
 * 行为:
 *   - 监听 polygons 数组的引用变化(整体重建,简单可靠)
 *   - 卸载时全部 remove
 */
import { ref, watch, onBeforeUnmount } from 'vue'
import { useAMap } from '@/composables/useAMap'
import { DEFAULT_CATEGORY_COLORS, type Boundary } from '@/utils/amap'

interface Props {
  polygons: Boundary[]
}
const props = defineProps<Props>()

const emit = defineEmits<{
  (e: 'select', boundary: Boundary): void
}>()

const { map, isReady } = useAMap()
const layers = ref<any[]>([])

function pickColor(label: string): { fill: string; stroke: string } {
  const color = DEFAULT_CATEGORY_COLORS[label] ?? DEFAULT_CATEGORY_COLORS['其他'] ?? '#525252'
  return { fill: color, stroke: color }
}

function build() {
  if (!map.value) return
  // 清旧
  for (const p of layers.value) {
    try { map.value.remove([p]) } catch { /* swallow */ }
  }
  layers.value = []

  const AMap = (globalThis as any).AMap
  if (!AMap?.Polygon) return

  for (const b of props.polygons) {
    if (!b.path || b.path.length < 3) continue
    const { fill, stroke } = pickColor(b.label)
    const poly = new AMap.Polygon({
      path: b.path,
      fillColor: fill,
      fillOpacity: 0.35,
      strokeColor: stroke,
      strokeWeight: 2,
      strokeOpacity: 0.9,
      cursor: 'pointer',
      bubble: true,
    })
    poly.on('click', () => emit('select', b))
    // AMap.Polygon 通过 setMap(map) 注册更兼容,这里走 add
    map.value.add([poly])
    layers.value.push(poly)
  }
}

watch(
  () => props.polygons,
  () => {
    if (isReady.value) build()
  },
  { immediate: true, deep: true },
)

onBeforeUnmount(() => {
  if (map.value) {
    for (const p of layers.value) {
      try { map.value.remove([p]) } catch { /* swallow */ }
    }
  }
  layers.value = []
})
</script>

<template>
  <div class="polygon-layer" style="display: none" />
</template>

<style scoped>
.polygon-layer { display: none; }
</style>
