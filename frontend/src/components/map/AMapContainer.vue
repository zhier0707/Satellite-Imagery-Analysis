<script setup lang="ts">
/**
 * AMapContainer - 通用高德地图容器
 * ====================
 *
 * 设计原则:
 *   - 唯一职责:加载 AMap SDK,创建地图实例,通过 provideAMap 共享给子组件
 *   - 不直接渲染子组件(子组件由父视图 MapView 传入 default slot)
 *   - 不要把 layers/overlays 透传给 AMap.Map 构造器;
 *     子组件通过 useAMap() 拿到 map 后自己 add()/remove()
 *
 * 事件:
 *   - ready(map)   地图初始化完成
 *   - move(center) 地图中心变化(用户拖动/缩放)
 *   - click(point) 点击地图空白处
 *
 * 暴露:
 *   - getMap()     供父组件直接 flyTo / setCenter
 *   - flyTo(p)     便捷飞行方法
 */
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import { loadAMap, isAMapConfigured } from '@/utils/amap'
import { provideAMap } from '@/composables/useAMap'
import type { LngLat } from '@/utils/amap'

interface LayerSpec {
  /** 任意 AMap.Layer 子类,如 AMap.TileLayer.Satellite */
  type: 'satellite' | 'road' | 'traffic'
  opacity?: number
  visible?: boolean
}

interface OverlaySpec {
  /** 由父组件控制显隐,真正 add/remove 留给子组件 */
  type: 'heatmap' | 'polygon' | 'marker' | 'polyline' | 'info-window'
  visible: boolean
}

interface Props {
  center?: LngLat
  zoom?: number
  layers?: LayerSpec[]
  overlays?: OverlaySpec[]
}
const props = withDefaults(defineProps<Props>(), {
  center: () => [116.397428, 39.90923] as LngLat,
  zoom: 12,
  layers: () => [],
  overlays: () => [],
})

const emit = defineEmits<{
  (e: 'ready', map: unknown): void
  (e: 'move', center: LngLat): void
  (e: 'click', point: LngLat): void
}>()

// ==================== 模板引用 ====================
const divRef = ref<HTMLDivElement | null>(null)
const loading = ref(true)
const errorMsg = ref('')

// ==================== 地图实例(对外类型为 unknown,内部用 any 兜底 AMap.Map) ====================
let mapInstance: any = null
const ctx = provideAMap()

// ==================== 暴露给父组件 ====================
function getMap(): unknown {
  return mapInstance
}
function flyTo(point: LngLat, zoom?: number) {
  if (!mapInstance) return
  if (typeof mapInstance.flyTo === 'function') {
    mapInstance.flyTo({ center: point, zoom, duration: 0.6 })
  } else {
    mapInstance.setCenter(point)
    if (zoom !== undefined) mapInstance.setZoom(zoom)
  }
}
defineExpose({ getMap, flyTo })

// ==================== 生命周期 ====================
onMounted(async () => {
  if (!isAMapConfigured()) {
    errorMsg.value = 'VITE_AMAP_JS_KEY 未配置,无法加载高德地图。'
    loading.value = false
    return
  }
  if (!divRef.value) return
  try {
    const AMapNS = (await loadAMap({
      plugins: ['AMap.Scale', 'AMap.ToolBar', 'AMap.HeatMap', 'AMap.MoveAnimation'],
    })) as any
    // AMapLoader.load() 完成后,AMap 已被挂到 globalThis.AMap
    const AMap = (globalThis as any).AMap ?? AMapNS
    mapInstance = new AMap.Map(divRef.value, {
      viewMode: '2D',
      center: props.center,
      zoom: props.zoom,
      // 故意不传 layers,交给 setLayers 后续追加(也允许子组件用 setMap 加卫星底图)
    })
    // 比例尺 + 工具条(科研感)
    if (AMap.Scale) mapInstance.addControl(new AMap.Scale())
    if (AMap.ToolBar) mapInstance.addControl(new AMap.ToolBar({ position: 'RB' }))

    // 共享给 useAMap() 的子组件
    ctx.setMap(mapInstance)

    // 事件
    mapInstance.on('moveend', () => {
      const c = mapInstance.getCenter()
      emit('move', [c.getLng(), c.getLat()])
    })
    mapInstance.on('click', (e: any) => {
      const lng = e?.lnglat?.getLng?.() ?? e?.lnglat?.lng
      const lat = e?.lnglat?.getLat?.() ?? e?.lnglat?.lat
      if (typeof lng === 'number' && typeof lat === 'number') {
        emit('click', [lng, lat])
      }
    })

    loading.value = false
    emit('ready', mapInstance)
  } catch (e: any) {
    console.error('[AMapContainer] 加载失败:', e)
    errorMsg.value = e?.message ?? '高德地图加载失败'
    loading.value = false
  }
})

onBeforeUnmount(() => {
  if (mapInstance && typeof mapInstance.destroy === 'function') {
    mapInstance.destroy()
    mapInstance = null
  }
  ctx.setMap(null)
})

// ==================== 响应 props 变化 ====================
watch(
  () => props.center,
  (c) => {
    if (mapInstance && c) mapInstance.setCenter(c)
  },
)
watch(
  () => props.zoom,
  (z) => {
    if (mapInstance && typeof z === 'number') mapInstance.setZoom(z)
  },
)
</script>

<template>
  <div class="amap-container">
    <!-- 加载占位 -->
    <el-skeleton v-if="loading" :rows="3" animated class="amap-skeleton" />

    <!-- 错误提示(未配 Key / 加载失败) -->
    <el-empty
      v-else-if="errorMsg"
      :description="errorMsg"
      class="amap-error"
    >
      <template #image>
        <el-icon :size="48" color="#A3A3A3"><WarningFilled /></el-icon>
      </template>
    </el-empty>

    <!-- 地图主区(slot 留位置给子组件,子组件自身通过 useAMap() 拿到 map) -->
    <div v-show="!loading && !errorMsg" ref="divRef" class="amap-div">
      <slot />
    </div>
  </div>
</template>

<style scoped>
.amap-container {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 480px;
  background: var(--color-bg-soft);
  border-radius: var(--radius-md);
  overflow: hidden;
}
.amap-div {
  width: 100%;
  height: 100%;
  min-height: 480px;
}
.amap-skeleton {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-4);
}
.amap-error {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
