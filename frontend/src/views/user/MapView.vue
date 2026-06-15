<script setup lang="ts">
/**
 * MapView - 用户端第 7 菜单(高德地图视图)
 * ====================
 *
 * 布局(自顶向下 / 自左向右):
 *   顶部 64px:由 AppLayout 提供,本视图只占主区
 *   主区(el-container):
 *     - 左 el-aside 320px 抽屉: 4 个折叠面板
 *       1. 地理编码 / 逆地理  (GeocoderPanel)
 *       2. POI 搜索          (POISearchBox)
 *       3. 图层切换 + 透明度  (原生 el-checkbox-group + el-slider)
 *       4. 周边搜索          (原生表单)
 *     - 右 el-main padding:0: 满屏地图
 *   右下角浮卡: <ShareMiniMapCard />
 *
 * 数据:
 *   - 拉当前用户最近 50 条 classify_records
 *   - 类别 → 默认坐标映射(10 类 → 全球 10 个典型位置)
 *   - 派生 HeatPoint[] / Boundary[] 喂给子组件
 *
 * 状态管理(本视图独立,不入 store):
 *   - layer 可见性 / 透明度 / 中心 / 选区 / POI 结果 / 搜索
 *   - 这样 5 个面板互不污染,父 store 也不知道地图存在
 */
import { ref, computed, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import AMapContainer from '@/components/map/AMapContainer.vue'
import ClassificationHeatmapLayer from '@/components/map/ClassificationHeatmapLayer.vue'
import BoundaryPolygonLayer from '@/components/map/BoundaryPolygonLayer.vue'
import POISearchBox from '@/components/map/POISearchBox.vue'
import GeocoderPanel from '@/components/map/GeocoderPanel.vue'
import ShareMiniMapCard, { type SharePayload, type ShareResult } from '@/components/map/ShareMiniMapCard.vue'
import { listMyRecords, geocode as apiGeocode, regeocode as apiRegeocode, poiTextSearch, poiAroundSearch, shareMap } from '@/api'
import type { POI, HeatPoint, Boundary, LngLat } from '@/utils/amap'
import { isAMapConfigured } from '@/utils/amap'

// ==================== 10 类 → 全球 10 个典型坐标 ====================
/**
 * 与 DEFAULT_CATEGORY_COLORS 一一对应;
 * 选点逻辑:同类目标的常见出现地(机场靠机场,船舶靠港口,桥梁靠湾区...)
 * 顺序与 utils/amap/types.ts 的 DEFAULT_CATEGORY_COLORS 保持一致。
 */
const CLASS_COORDS: Record<string, LngLat> = {
  '飞机':   [113.304136, 23.103048],   // 广州白云机场
  '船舶':   [121.492668, 31.238856],   // 上海外港
  '车辆':   [116.480151, 39.988624],   // 北京环路某处
  '桥梁':   [121.498474, 31.239058],   // 上海杨浦大桥
  '建筑物': [116.397428, 39.90923],    // 北京天安门
  '道路':   [116.310316, 39.992706],   // 北京西直门外
  '跑道':   [121.808, 31.142],         // 上海浦东机场跑道
  '体育场': [116.391, 39.986],         // 北京工人体育场
  '储油罐': [117.215, 39.143],         // 天津南港工业区
  '其他':   [116.397428, 39.90923],
}

function coordOf(label: string): LngLat {
  return CLASS_COORDS[label] ?? CLASS_COORDS['其他']
}

// ==================== 抽屉默认展开项 ====================
const activeCollapse = ref<string[]>(['geocode', 'layer'])
// popover 触发方式:用 click,手动显隐由 v-model:visible 控制
// 工具提示触发类型(Element Plus)只接受 click/hover/focus;不用 manual
type PopoverTrigger = 'click' | 'hover' | 'focus'
const popoverTriggerValue = ref<PopoverTrigger>('click')

// ==================== 视图状态 ====================
const mapRef = ref<InstanceType<typeof AMapContainer> | null>(null)
const center = ref<LngLat>([116.397428, 39.90923])
const zoom = ref(5)

// 数据
const records = ref<Array<{ id: number; top1_label: string; top1_score: number }>>([])
const heatPoints = ref<HeatPoint[]>([])
const boundaries = ref<Boundary[]>([])
const pois = ref<POI[]>([])
const loadingRecords = ref(false)

// 图层控制
const showHeatmap = ref(true)
const showBoundary = ref(true)
const heatmapOpacity = ref(0.7)

// 周边搜索结果
const aroundPois = ref<POI[]>([])
const aroundLoading = ref(false)
const aroundInput = ref({ lng: 116.397428, lat: 39.90923, radius: 1000, types: '050000' })

// Geocode / Regeocode
const forwardPoint = ref<LngLat | null>(null)
const forwardAddr = ref('')
const reverseAddr = ref('')
const geocodeLoading = ref(false)
const geocoderRef = ref<InstanceType<typeof GeocoderPanel> | null>(null)

// POI 搜索
const poiLoading = ref(false)
const selectedPoi = ref<POI | null>(null)

// 分享
const shareLoading = ref(false)
const shareResult = ref<ShareResult | null>(null)

// 选中多边形(用于 popover)
const selectedBoundary = ref<Boundary | null>(null)
const popoverVisible = ref(false)

// ==================== 派生数据:records → HeatPoint / Boundary ====================
function buildOverlaysFromRecords() {
  const points: HeatPoint[] = []
  const polys: Boundary[] = []
  records.value.forEach((r, idx) => {
    const c = coordOf(r.top1_label)
    const weight = Math.round((r.top1_score ?? 0.5) * 100)
    points.push({ lng: c[0], lat: c[1], weight })
    // 围绕 c 画一个 0.4 度方框当占位 boundary,围绕同一类合并
    // 为了避免大量重叠,每个类只保留前 3 条做 boundary
    if (idx < 10) {
      const offset = 0.05
      polys.push({
        id: r.id,
        label: r.top1_label,
        center: c,
        confidence: r.top1_score,
        path: [
          [c[0] - offset, c[1] - offset],
          [c[0] + offset, c[1] - offset],
          [c[0] + offset, c[1] + offset],
          [c[0] - offset, c[1] + offset],
        ],
      })
    }
  })
  heatPoints.value = points
  boundaries.value = polys
}

// ==================== 拉数据 ====================
async function loadRecords() {
  loadingRecords.value = true
  try {
    const r = await listMyRecords(1, 50)
    records.value = r.items ?? []
    buildOverlaysFromRecords()
  } catch (e: any) {
    ElMessage.error('加载分类记录失败:' + (e?.message ?? e))
  } finally {
    loadingRecords.value = false
  }
}

onMounted(() => {
  loadRecords()
})

// ==================== 地图事件 ====================
function onMapReady(_map: unknown) {
  // 容器已提供 map,本视图暂无需更多操作
}
function onMapMove(c: LngLat) {
  // 仅记录,不写回 center(避免循环)
  // 用户可读此值做"当前中心"展示
  void c
}
function onMapClick(point: LngLat) {
  // 点击地图空白处 → 切换到逆地理 Tab,自动填经纬度
  geocoderRef.value?.setReverseCoord(point[0], point[1])
  // 顺手做一次逆地理查询
  handleRegeocode(point[0], point[1])
}

// ==================== Geocode ====================
async function handleGeocode(address: string) {
  geocodeLoading.value = true
  try {
    const r = await apiGeocode(address)
    forwardPoint.value = r.location
    forwardAddr.value = r.formatted_address ?? address
    // 飞到该点
    mapRef.value?.flyTo(r.location, 14)
  } catch (e: any) {
    ElMessage.error('地理编码失败:' + (e?.message ?? e))
  } finally {
    geocodeLoading.value = false
  }
}

async function handleRegeocode(lng: number, lat: number) {
  geocodeLoading.value = true
  try {
    const r = await apiRegeocode(lng, lat)
    reverseAddr.value = r.formatted_address ?? ''
  } catch (e: any) {
    ElMessage.error('逆地理失败:' + (e?.message ?? e))
  } finally {
    geocodeLoading.value = false
  }
}

// ==================== POI 搜索 ====================
async function handlePoiSearch(keyword: string) {
  poiLoading.value = true
  try {
    const list = await poiTextSearch({ keywords: keyword, offset: 20 })
    pois.value = list
  } catch (e: any) {
    ElMessage.error('POI 搜索失败:' + (e?.message ?? e))
    pois.value = []
  } finally {
    poiLoading.value = false
  }
}

function handlePoiSelect(poi: POI) {
  selectedPoi.value = poi
  mapRef.value?.flyTo(poi.location, 15)
}

// ==================== 周边搜索 ====================
async function handleAroundSearch() {
  aroundLoading.value = true
  try {
    aroundPois.value = await poiAroundSearch({
      lng: aroundInput.value.lng,
      lat: aroundInput.value.lat,
      radius: aroundInput.value.radius,
      types: aroundInput.value.types,
    })
    if (aroundPois.value.length === 0) {
      ElMessage.info('该范围内未找到 POI')
    } else {
      const first = aroundPois.value[0]
      mapRef.value?.flyTo(first.location, 15)
    }
  } catch (e: any) {
    ElMessage.error('周边搜索失败:' + (e?.message ?? e))
  } finally {
    aroundLoading.value = false
  }
}

// ==================== 分享 ====================
async function handleShare(_payload: SharePayload) {
  shareLoading.value = true
  try {
    // 取 heatPoints 作为 markers 喂给后端
    const markers = heatPoints.value.slice(0, 20).map((p) => ({
      lng: p.lng,
      lat: p.lat,
      name: '记录 #' + p.lng.toFixed(2) + ',' + p.lat.toFixed(2),
    }))
    const r = await shareMap({ title: _payload.title, markers })
    shareResult.value = r
  } catch (e: any) {
    ElMessage.error('生成分享卡失败:' + (e?.message ?? e))
  } finally {
    shareLoading.value = false
  }
}

watch(shareResult, (r) => {
  if (r) {
    // 触发 ShareMiniMapCard 的 dialog 显式打开
    // 由于 ShareMiniMapCard 内部 v-model + props 联动,这里通过 :shareResult 传值即可
  }
})

// ==================== 边界点击 ====================
function onBoundarySelect(b: Boundary) {
  selectedBoundary.value = b
  popoverVisible.value = true
  mapRef.value?.flyTo(b.center ?? coordOf(b.label), 14)
}

// ==================== 类型清单(周边搜索的 types 下拉) ====================
const POI_TYPES: Array<{ value: string; label: string }> = [
  { value: '050000', label: '餐饮服务' },
  { value: '060000', label: '购物消费' },
  { value: '080000', label: '生活服务' },
  { value: '090000', label: '医疗保健' },
  { value: '100000', label: '住宿服务' },
  { value: '110000', label: '风景名胜' },
  { value: '150000', label: '交通设施' },
]

const configured = computed(() => isAMapConfigured())
</script>

<template>
  <div class="map-view">
    <!-- ==================== 未配 Key 提示 ==================== -->
    <EmptyState
      v-if="!configured"
      icon="MapLocation"
      title="高德地图 Key 未配置"
      description="请在 frontend/.env 中配置 VITE_AMAP_JS_KEY 后刷新页面;当前页面功能被禁用。"
    >
      <el-button type="primary" @click="loadRecords">重试</el-button>
    </EmptyState>

    <!-- ==================== 主布局 ==================== -->
    <el-container v-else class="map-view__body">
      <!-- 左 320px 抽屉式工具栏 -->
      <el-aside width="320px" class="map-view__aside">
        <PageHeader
          title="地图视图"
          subtitle="分类点热力 · 类别边界 · POI 搜索 · 周边搜索"
        />

        <el-collapse v-model="activeCollapse" class="map-view__collapse">
          <!-- ========== 1. 地理编码 ========== -->
          <el-collapse-item title="地理 / 逆地理" name="geocode">
            <GeocoderPanel
              ref="geocoderRef"
              :point="forwardPoint"
              :formatted-address="forwardAddr"
              :address="reverseAddr"
              :loading="geocodeLoading"
              @geocode="handleGeocode"
              @regeocode="handleRegeocode"
            />
          </el-collapse-item>

          <!-- ========== 2. POI 搜索 ========== -->
          <el-collapse-item title="POI 关键字搜索" name="poi">
            <POISearchBox
              :results="pois"
              :loading="poiLoading"
              @search="handlePoiSearch"
              @select="handlePoiSelect"
            />
          </el-collapse-item>

          <!-- ========== 3. 图层切换 ========== -->
          <el-collapse-item title="图层与透明度" name="layer">
            <div class="map-view__layer-row">
              <el-checkbox v-model="showHeatmap">分类热力图</el-checkbox>
            </div>
            <div class="map-view__layer-row">
              <el-checkbox v-model="showBoundary">类别边界</el-checkbox>
            </div>
            <div class="map-view__layer-row map-view__layer-row--slider">
              <span class="text-fg-2">热力图透明度</span>
              <el-slider v-model="heatmapOpacity" :min="0" :max="1" :step="0.05" style="flex: 1" />
              <span class="text-mono text-fg-2">{{ heatmapOpacity.toFixed(2) }}</span>
            </div>
            <p class="map-view__hint">
              数据来源: 当前用户最近 {{ records.length }} 条分类记录
            </p>
          </el-collapse-item>

          <!-- ========== 4. 周边搜索 ========== -->
          <el-collapse-item title="周边搜索" name="around">
            <div class="map-view__form-row">
              <el-input v-model.number="aroundInput.lng" type="number" placeholder="经度" />
              <el-input v-model.number="aroundInput.lat" type="number" placeholder="纬度" />
            </div>
            <div class="map-view__form-row">
              <el-select v-model="aroundInput.types" placeholder="类型" style="flex: 1">
                <el-option
                  v-for="t in POI_TYPES"
                  :key="t.value"
                  :label="t.label"
                  :value="t.value"
                />
              </el-select>
              <el-input-number
                v-model="aroundInput.radius"
                :min="100"
                :max="50000"
                :step="100"
                style="width: 140px"
                placeholder="半径"
              />
            </div>
            <el-button
              type="primary"
              :loading="aroundLoading"
              style="width: 100%; margin-top: var(--space-1)"
              @click="handleAroundSearch"
            >
              搜周边
            </el-button>
            <p v-if="aroundPois.length" class="map-view__hint">
              找到 {{ aroundPois.length }} 个 POI
            </p>
          </el-collapse-item>
        </el-collapse>
      </el-aside>

      <!-- 主区: 地图 + 浮卡 + popover -->
      <el-main class="map-view__main">
        <AMapContainer
          ref="mapRef"
          :center="center"
          :zoom="zoom"
          @ready="onMapReady"
          @move="onMapMove"
          @click="onMapClick"
        >
          <ClassificationHeatmapLayer
            v-if="showHeatmap && heatPoints.length"
            :points="heatPoints"
            :opacity="heatmapOpacity"
          />
          <BoundaryPolygonLayer
            v-if="showBoundary && boundaries.length"
            :polygons="boundaries"
            @select="onBoundarySelect"
          />
        </AMapContainer>

        <!-- 选中多边形的 popover -->
        <el-popover
          v-model:visible="popoverVisible"
          placement="top"
          :width="240"
          :trigger="popoverTriggerValue"
        >
          <template #reference>
            <span class="map-view__popover-anchor" />
          </template>
          <div v-if="selectedBoundary" class="map-view__popover">
            <h4 class="map-view__popover-title">{{ selectedBoundary.label }}</h4>
            <p class="text-fg-2 text-mono">
              置信度:{{ ((selectedBoundary.confidence ?? 0) * 100).toFixed(1) }}%
            </p>
            <p v-if="selectedBoundary.center" class="text-fg-3 text-mono" style="font-size: 12px">
              {{ selectedBoundary.center[0].toFixed(4) }}, {{ selectedBoundary.center[1].toFixed(4) }}
            </p>
          </div>
        </el-popover>

        <!-- 分享浮卡 -->
        <ShareMiniMapCard
          :share-result="shareResult"
          :loading="shareLoading"
          @share="handleShare"
        />
      </el-main>
    </el-container>
  </div>
</template>

<style scoped>
.map-view {
  height: calc(100vh - 64px);
  display: flex;
  flex-direction: column;
  background: var(--color-bg);
}
.map-view__body {
  flex: 1;
  min-height: 0;
}
.map-view__aside {
  background: var(--color-bg);
  border-right: 1px solid var(--color-border);
  overflow-y: auto;
  padding: 0 var(--space-2) var(--space-2);
}
.map-view__aside :deep(.page-header) {
  padding: var(--space-2) 0;
  margin-bottom: var(--space-1);
}
.map-view__collapse {
  border-top: none;
}
.map-view__collapse :deep(.el-collapse-item__header) {
  font-family: var(--font-sans);
  font-size: var(--text-body);
  font-weight: var(--weight-medium);
  color: var(--color-fg);
  padding-left: var(--space-1);
}
.map-view__collapse :deep(.el-collapse-item__content) {
  padding-bottom: var(--space-2);
}
.map-view__layer-row {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  margin-bottom: var(--space-1);
}
.map-view__layer-row--slider { gap: var(--space-1); }
.map-view__hint {
  margin: var(--space-1) 0 0 0;
  font-size: var(--text-small);
  color: var(--color-fg-3);
}
.map-view__form-row {
  display: flex;
  gap: var(--space-1);
  margin-bottom: var(--space-1);
}
.map-view__form-row > * { flex: 1; }
.map-view__main {
  position: relative;
  padding: 0;
  background: var(--color-bg-soft);
}
.map-view__popover-anchor {
  position: absolute;
  right: 0;
  top: 0;
  width: 1px;
  height: 1px;
  pointer-events: none;
}
.map-view__popover-title {
  font-family: var(--font-serif);
  font-size: var(--text-h3);
  margin: 0 0 var(--space-1) 0;
  color: var(--color-fg);
}

@media (max-width: 900px) {
  .map-view__aside { width: 280px !important; }
}
@media (max-width: 720px) {
  .map-view__body { flex-direction: column; }
  .map-view__aside { width: 100% !important; max-height: 40%; }
  .map-view__main { flex: 1; min-height: 320px; }
}
</style>
