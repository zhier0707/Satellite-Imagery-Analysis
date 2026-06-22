<script setup lang="ts">
/**
 * BigScreenView - 3D 大屏 / 数据驾驶舱
 * ====================
 *
 * 视觉目标（Phase B.3 - B.5）:
 *   - 3D 地球（Three.js）+ 卫星轨道 + 1000 颗星
 *   - 4 个 KPI 大字卡（衬线 + text-shadow 辉光）
 *   - 2 张 ECharts：分类分布环形图 + 30 天趋势折线图
 *   - AMap 2D 缩略图（zoom=3 全球视野，Top-50 蓝点）
 *   - 状态栏：数据源 / 实时刷新 30s / 最近同步 / 快捷键提示
 *   - 快捷键：F 全屏 / R 刷新 / Esc 退出
 *
 * 数据流:
 *   - onMounted: 创建 EarthScene → 加地球/大气/轨道/星空
 *   - 启动 1s 时钟 + 30s 数据刷新
 *   - loadDashboard: 拉 /api/stats/dashboard → 触发 KPI 滚动 / 点云更新 / ECharts 重绘
 *
 * 重要约束:
 *   - 后端 top_locations 不含 lng/lat 字段（schema 当前实现降级为 id/label/score）
 *     前端用「label → 预设坐标 + 抖动」策略派生经纬度，让点云有视觉
 *   - 全屏 API 在非 secure context 下不可用，做 try/catch 保护
 *   - prefers-reduced-motion 偏好下禁用数字滚动与入场
 */
import { ref, onMounted, onUnmounted, nextTick, shallowRef } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Compass, FullScreen, Refresh, SwitchButton, Clock, DataLine, Position } from '@element-plus/icons-vue'
import * as echarts from 'echarts/core'
import { PieChart, LineChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  GridComponent,
  LegendComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import AMapContainer from '@/components/map/AMapContainer.vue'
import { EarthScene, type EarthPointItem } from '@/utils/three/EarthScene'
import { createEarthTexture, createCloudTexture } from '@/utils/three/textures'
import { LABEL_COLORS } from '@/utils/three/colors'
import { getDashboardStats, type DashboardStats } from '@/api'
import { useAuthStore } from '@/stores/auth'
import { useCountUp } from '@/composables/useCountUp'
import { isAMapConfigured } from '@/utils/amap'

// ==================== ECharts 模块按需注册 ====================
echarts.use([
  PieChart,
  LineChart,
  TitleComponent,
  TooltipComponent,
  GridComponent,
  LegendComponent,
  CanvasRenderer,
])

// ==================== 路由与 Store ====================
const router = useRouter()
const auth = useAuthStore()

// ==================== 模板引用 ====================
const earthRef = ref<HTMLDivElement | null>(null)
const pieRef = ref<HTMLDivElement | null>(null)
const lineRef = ref<HTMLDivElement | null>(null)
const mapMiniRef = ref<InstanceType<typeof AMapContainer> | null>(null)
const aMapConfigured = isAMapConfigured()

// ==================== 状态 ====================
const data = shallowRef<DashboardStats | null>(null)
const currentTime = ref('--:--:--')
const lastSync = ref('--:--:--')
const loading = ref(false)
const isFullscreen = ref(false)

// KPI targets（ref 触发 useCountUp 内部动画）
const kpiTotalTarget = ref(0)
const kpiTodayTarget = ref(0)
const kpiActiveTarget = ref(0)
const kpiAccuracyTarget = ref(0)
const kpiTotal = useCountUp(kpiTotalTarget, 1.2)
const kpiToday = useCountUp(kpiTodayTarget, 1.2)
const kpiActive = useCountUp(kpiActiveTarget, 1.2)
const kpiAccuracy = useCountUp(kpiAccuracyTarget, 1.2)

// ==================== 内部资源 ====================
let earthScene: EarthScene | null = null
let pieChart: echarts.ECharts | null = null
let lineChart: echarts.ECharts | null = null
let clockTimer: number | null = null
let refreshTimer: number | null = null

// ==================== 10 类预设经纬度（伪坐标） ====================
/**
 * 后端当前 schema 不返回 lng/lat（降级实现）。
 * 前端为每条 top_location 派生一个"视觉经纬度"：
 *   lng = 预设中心经度 + 抖动(seed = id)
 *   lat = 预设中心纬度 + 抖动
 * 这样每个点都不同，又围绕 label 聚类，视觉上是 10 个分类热点。
 */
const LABEL_COORDS: Record<string, [number, number]> = {
  AnnualCrop:           [2.5, 49.5],     // 法国
  Forest:               [10.0, 61.0],    // 挪威
  HerbaceousVegetation: [12.5, 41.9],    // 罗马
  Highway:              [77.2, 28.6],    // 德里
  Industrial:           [4.4, 51.4],     // 鹿特丹
  Pasture:              [-58.4, -34.6],  // 布宜诺斯艾利斯
  PermanentCrop:        [-9.2, 38.7],    // 里斯本
  Residential:          [139.7, 35.7],   // 东京
  River:                [121.5, 31.2],   // 上海
  SeaLake:              [-122.4, 37.8],  // 旧金山湾
}

/** 简单确定性伪随机（基于 seed，避免每次刷新点乱跳） */
function seededRandom(seed: number): number {
  const x = Math.sin(seed * 12.9898) * 43758.5453
  return x - Math.floor(x)
}

function derivePoint(item: { id: number; label: string; score: number }): EarthPointItem {
  const base = LABEL_COORDS[item.label] ?? [0, 0]
  const jLng = (seededRandom(item.id * 1.3) - 0.5) * 8
  const jLat = (seededRandom(item.id * 2.7 + 11) - 0.5) * 6
  const color = LABEL_COLORS[item.label] ?? 0x6B7280
  return {
    lng: base[0] + jLng,
    lat: base[1] + jLat,
    label: item.label,
    offset: seededRandom(item.id * 3.1) * Math.PI * 2,
    color,
  }
}

// ==================== 时间格式化 ====================
function pad2(n: number): string {
  return n < 10 ? '0' + n : String(n)
}
function formatTime(d: Date): string {
  return `${pad2(d.getHours())}:${pad2(d.getMinutes())}:${pad2(d.getSeconds())}`
}

// ==================== 加载数据 ====================
async function loadDashboard(): Promise<void> {
  loading.value = true
  try {
    const r = await getDashboardStats()
    data.value = r

    // KPI 滚动（accuracy_avg 是 0-1 浮点 → 百分比）
    kpiTotalTarget.value = r.kpi.total_records
    kpiTodayTarget.value = r.kpi.today_new
    kpiActiveTarget.value = r.kpi.active_users
    kpiAccuracyTarget.value = Number((r.kpi.accuracy_avg * 100).toFixed(2))

    // 分类点云
    if (earthScene) {
      const points = r.top_locations.map(derivePoint)
      earthScene.addPointCloud(points)
    }

    // ECharts
    renderPie(r.classification_distribution)
    renderLine(r.time_series)

    // 地图缩略图
    if (mapMiniRef.value) {
      renderMapMini(r.top_locations)
    }

    // 状态栏最近同步
    lastSync.value = formatTime(new Date())
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e)
    ElMessage.error('加载大屏数据失败：' + msg)
  } finally {
    loading.value = false
  }
}

// ==================== 分类分布环形图 ====================
function renderPie(dist: Record<string, number>): void {
  if (!pieChart) return
  const data = Object.entries(dist)
    .filter(([, v]) => v > 0)
    .map(([k, v]) => ({
      name: k,
      value: v,
      itemStyle: { color: colorHex(LABEL_COLORS[k] ?? 0x6B7280) },
    }))
  pieChart.setOption({
    backgroundColor: 'transparent',
    tooltip: { trigger: 'item' },
    legend: {
      type: 'scroll',
      orient: 'vertical',
      right: 8,
      top: 'middle',
      textStyle: { color: '#E0E6F0', fontSize: 11 },
    },
    series: [
      {
        name: '分类分布',
        type: 'pie',
        radius: ['38%', '64%'],
        center: ['38%', '50%'],
        avoidLabelOverlap: true,
        itemStyle: {
          borderColor: 'rgba(10,14,26,0.9)',
          borderWidth: 2,
        },
        label: { color: '#E0E6F0', fontSize: 11 },
        data,
      },
    ],
  })
}

// ==================== 30 天趋势折线图 ====================
function renderLine(series: { date: string; count: number }[]): void {
  if (!lineChart) return
  const dates = series.map((s) => s.date.slice(5)) // 去掉年份
  const counts = series.map((s) => s.count)
  lineChart.setOption({
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis' },
    grid: { left: 36, right: 16, top: 28, bottom: 28 },
    xAxis: {
      type: 'category',
      data: dates,
      axisLine: { lineStyle: { color: '#4B5563' } },
      axisLabel: { color: '#A3A3A3', fontSize: 10 },
    },
    yAxis: {
      type: 'value',
      axisLine: { lineStyle: { color: '#4B5563' } },
      splitLine: { lineStyle: { color: 'rgba(75,85,99,0.4)' } },
      axisLabel: { color: '#A3A3A3', fontSize: 10 },
    },
    series: [
      {
        name: '新增记录',
        type: 'line',
        smooth: true,
        symbol: 'circle',
        symbolSize: 6,
        data: counts,
        lineStyle: { color: '#10F2C5', width: 2 },
        itemStyle: { color: '#10F2C5' },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(16,242,197,0.5)' },
              { offset: 1, color: 'rgba(16,242,197,0.05)' },
            ],
          },
        },
      },
    ],
  })
}

// ==================== 地图缩略图（高德 2D 全球视野） ====================
function renderMapMini(items: { id: number; label: string; score: number }[]): void {
  const map = mapMiniRef.value?.getMap?.() as
    | { add: (m: unknown) => void; setFitView?: () => void }
    | null
  if (!map) return
  const AMap = (globalThis as { AMap?: { Marker: unknown; LngLat: unknown } }).AMap
  if (!AMap) return
  for (const it of items) {
    const coord = LABEL_COORDS[it.label] ?? [0, 0]
    const marker = new (AMap.Marker as new (opts: { position: unknown; content: string; offset: unknown }) => unknown)({
      position: new (AMap.LngLat as new (lng: number, lat: number) => unknown)(coord[0], coord[1]),
      content: `<div style="width:10px;height:10px;border-radius:50%;background:#00E5FF;box-shadow:0 0 8px #00E5FF;"></div>`,
      offset: { x: -5, y: -5 },
    })
    map.add(marker)
  }
}

// ==================== 工具：0xRRGGBB → '#RRGGBB' ====================
function colorHex(n: number): string {
  return '#' + n.toString(16).padStart(6, '0')
}

// ==================== 全屏 ====================
function toggleFullscreen(): void {
  if (document.fullscreenElement) {
    exitFullscreen()
  } else {
    requestFullscreen()
  }
}
function requestFullscreen(): void {
  try {
    const el = document.documentElement
    const fn = el.requestFullscreen ?? (el as { webkitRequestFullscreen?: () => Promise<void> }).webkitRequestFullscreen
    if (fn) {
      const r = fn.call(el)
      if (r && typeof (r as Promise<void>).catch === 'function') {
        ;(r as Promise<void>).catch(() => {
          ElMessage.warning('当前环境不支持全屏 API（非 secure context）')
        })
      }
    } else {
      ElMessage.warning('当前浏览器不支持全屏 API')
    }
  } catch {
    ElMessage.warning('全屏切换失败')
  }
}
function exitFullscreen(): void {
  try {
    if (document.fullscreenElement) {
      void document.exitFullscreen()
    }
  } catch {
    // 静默
  }
}
function onFullscreenChange(): void {
  isFullscreen.value = !!document.fullscreenElement
}

// ==================== 快捷键 ====================
function onKeydown(e: KeyboardEvent): void {
  // 避免在输入框中误触
  const tag = (e.target as HTMLElement | null)?.tagName
  if (tag === 'INPUT' || tag === 'TEXTAREA') return

  const key = e.key.toLowerCase()
  if (key === 'f') {
    e.preventDefault()
    toggleFullscreen()
  } else if (key === 'r') {
    e.preventDefault()
    void loadDashboard()
    ElMessage.info('刷新大屏数据')
  } else if (key === 'escape') {
    if (document.fullscreenElement) {
      // 浏览器原生处理
    } else {
      e.preventDefault()
      router.push('/app/home')
    }
  }
}

const exitScreen = (): void => {
  // 守卫:全屏下不应跳走,先退全屏;非全屏才真正路由
  if (document.fullscreenElement) {
    void document.exitFullscreen().catch(() => {
      // 静默
    })
    return
  }
  router.push('/app/home')
}

// ==================== 生命周期 ====================
onMounted(async () => {
  await nextTick()

  // 3D 地球
  if (earthRef.value) {
    earthScene = new EarthScene(earthRef.value)
    const tex = createEarthTexture()
    const cloudTex = createCloudTexture()
    earthScene.addEarth(tex)
    earthScene.addClouds(cloudTex)
    earthScene.addGlow()
    earthScene.addOrbit()
    earthScene.addStars(1000)
    earthScene.startRotation(0.05)
  }

  // ECharts
  if (pieRef.value) pieChart = echarts.init(pieRef.value)
  if (lineRef.value) lineChart = echarts.init(lineRef.value)

  // 时钟（每秒）
  clockTimer = window.setInterval(() => {
    currentTime.value = formatTime(new Date())
  }, 1000)

  // 数据
  await loadDashboard()

  // 30 秒自动刷新
  refreshTimer = window.setInterval(() => {
    void loadDashboard()
  }, 30_000)

  // 快捷键 + 全屏状态
  window.addEventListener('keydown', onKeydown)
  document.addEventListener('fullscreenchange', onFullscreenChange)
})

onUnmounted(() => {
  if (earthScene) earthScene.dispose()
  if (pieChart) pieChart.dispose()
  if (lineChart) lineChart.dispose()
  if (clockTimer !== null) window.clearInterval(clockTimer)
  if (refreshTimer !== null) window.clearInterval(refreshTimer)
  window.removeEventListener('keydown', onKeydown)
  document.removeEventListener('fullscreenchange', onFullscreenChange)
})
</script>

<template>
  <div class="big-screen">
    <!-- ==================== 顶部 Header ==================== -->
    <header class="header">
      <div class="header__left">
        <el-icon class="header__logo"><Compass /></el-icon>
        <div class="header__title-wrap">
          <h1 class="header__title">卫星图像分析 · 数据驾驶舱</h1>
          <p class="header__subtitle">SATELLITE IMAGERY · DATA COCKPIT</p>
        </div>
      </div>
      <div class="header__right">
        <div class="header__time">
          <el-icon><Clock /></el-icon>
          <span class="header__time-text">{{ currentTime }}</span>
        </div>
        <el-tag v-if="auth.isAdmin" type="danger" size="small" effect="dark">ADMIN</el-tag>
        <el-tag v-else type="info" size="small" effect="dark">USER</el-tag>
        <el-button text bg class="header__btn" @click="toggleFullscreen">
          <el-icon><FullScreen /></el-icon>
          <span>{{ isFullscreen ? '退出全屏' : '全屏' }}</span>
        </el-button>
        <el-button text bg class="header__btn header__btn--exit" @click="exitScreen">
          <el-icon><SwitchButton /></el-icon>
          <span>退出大屏</span>
        </el-button>
      </div>
    </header>

    <!-- ==================== 主体 3 列 ==================== -->
    <main class="body">
      <!-- ============ 左：3D 地球 ============ -->
      <section class="col col--earth">
        <div ref="earthRef" class="earth" />
        <div class="earth__overlay">
          <el-icon class="earth__hint"><Position /></el-icon>
          <span>3D 地球 · 1000 颗星 · 实时分类点云</span>
        </div>
      </section>

      <!-- ============ 中：KPI + 2 张 ECharts ============ -->
      <section class="col col--data">
        <!-- 4 个 KPI 大字卡 -->
        <div class="kpi-grid">
          <div class="kpi kpi--blue">
            <p class="kpi__label">总记录数</p>
            <p class="kpi__value">
              <span class="kpi__num">{{ Math.round(kpiTotal).toLocaleString() }}</span>
              <span class="kpi__unit">条</span>
            </p>
          </div>
          <div class="kpi kpi--green">
            <p class="kpi__label">今日新增</p>
            <p class="kpi__value">
              <span class="kpi__num">{{ Math.round(kpiToday).toLocaleString() }}</span>
              <span class="kpi__unit">条</span>
            </p>
          </div>
          <div class="kpi kpi--purple">
            <p class="kpi__label">活跃用户</p>
            <p class="kpi__value">
              <span class="kpi__num">{{ Math.round(kpiActive).toLocaleString() }}</span>
              <span class="kpi__unit">人</span>
            </p>
          </div>
          <div class="kpi kpi--orange">
            <p class="kpi__label">平均准确率</p>
            <p class="kpi__value">
              <span class="kpi__num">{{ kpiAccuracy.toFixed(2) }}</span>
              <span class="kpi__unit">%</span>
            </p>
          </div>
        </div>

        <!-- 2 张图表 -->
        <div class="charts">
          <div class="chart-card">
            <div class="chart-card__title">
              <el-icon><DataLine /></el-icon>
              <span>分类分布</span>
            </div>
            <div ref="pieRef" class="chart-canvas" />
          </div>
          <div class="chart-card">
            <div class="chart-card__title">
              <el-icon><DataLine /></el-icon>
              <span>30 天趋势</span>
            </div>
            <div ref="lineRef" class="chart-canvas" />
          </div>
        </div>
      </section>

      <!-- ============ 右：AMap 缩略图 ============ -->
      <section class="col col--map">
        <div class="map-card">
          <div class="map-card__title">
            <span>全球分布缩略图</span>
            <span v-if="!aMapConfigured" class="map-card__warn">AMap 未配置</span>
          </div>
          <div class="map-card__body">
            <AMapContainer
              v-if="aMapConfigured"
              ref="mapMiniRef"
              :center="[10, 20]"
              :zoom="3"
              class="map-mini"
            />
            <div v-else class="map-card__placeholder">
              <el-icon :size="32"><Position /></el-icon>
              <p>高德地图未配置（VITE_AMAP_JS_KEY）</p>
            </div>
          </div>
        </div>
      </section>
    </main>

    <!-- ==================== 底部状态栏 ==================== -->
    <footer class="statusbar">
      <span class="statusbar__item">
        <span class="statusbar__dot" />
        数据源：MySQL · 实时刷新 30s
      </span>
      <span class="statusbar__item">最近同步：{{ lastSync }}</span>
      <span class="statusbar__item statusbar__item--keys">
        <el-icon><Refresh /></el-icon>
        快捷键：<kbd>F</kbd> 全屏 · <kbd>R</kbd> 刷新 · <kbd>Esc</kbd> 退出
      </span>
      <span v-if="loading" class="statusbar__loading">
        <span class="statusbar__loading-dot" />
        加载中…
      </span>
    </footer>
  </div>
</template>

<style scoped>
/* ==================== 容器 ==================== */
.big-screen {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 64px);
  background: var(--color-screen-bg, #0A0E1A);
  color: var(--color-screen-text, #E0E6F0);
  font-family: var(--font-sans);
  overflow: hidden;
}

/* ==================== 顶部 Header ==================== */
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 64px;
  padding: 0 var(--space-3);
  background: linear-gradient(180deg, rgba(0, 229, 255, 0.08) 0%, transparent 100%);
  border-bottom: 1px solid rgba(0, 229, 255, 0.18);
  flex-shrink: 0;
}
.header__left { display: flex; align-items: center; gap: var(--space-2); }
.header__logo {
  font-size: 28px;
  color: var(--color-screen-accent, #00E5FF);
  filter: drop-shadow(0 0 8px rgba(0, 229, 255, 0.6));
}
.header__title-wrap { display: flex; flex-direction: column; line-height: 1.1; }
.header__title {
  margin: 0;
  font-family: var(--font-serif);
  font-size: 22px;
  font-weight: var(--weight-semibold);
  color: var(--color-screen-text, #E0E6F0);
  letter-spacing: 0.04em;
  text-shadow: 0 0 12px rgba(0, 229, 255, 0.3);
}
.header__subtitle {
  margin: 4px 0 0 0;
  font-size: 11px;
  letter-spacing: 0.18em;
  color: var(--color-screen-muted, #6B7280);
  text-transform: uppercase;
}
.header__right { display: flex; align-items: center; gap: var(--space-1); }
.header__time {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border: 1px solid rgba(0, 229, 255, 0.3);
  border-radius: var(--radius-sm);
  background: rgba(0, 229, 255, 0.06);
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
}
.header__time-text {
  color: var(--color-screen-accent, #00E5FF);
  font-size: 14px;
  font-weight: var(--weight-medium);
}
.header__btn {
  color: var(--color-screen-text, #E0E6F0) !important;
  border: 1px solid rgba(0, 229, 255, 0.3) !important;
  background: rgba(0, 229, 255, 0.06) !important;
}
.header__btn--exit {
  color: #FCA5A5 !important;
  border-color: rgba(239, 68, 68, 0.3) !important;
  background: rgba(239, 68, 68, 0.06) !important;
}

/* ==================== 主体 3 列 Grid ==================== */
.body {
  flex: 1;
  display: grid;
  grid-template-columns: 1.4fr 1fr 0.9fr;
  gap: var(--space-2);
  padding: var(--space-2);
  min-height: 0;
  overflow: hidden;
}
.col { position: relative; min-width: 0; min-height: 0; display: flex; flex-direction: column; }
.col--earth { background: rgba(0, 0, 0, 0.4); border-radius: var(--radius-md); overflow: hidden; border: 1px solid rgba(0, 229, 255, 0.2); }
.col--data { display: grid; grid-template-rows: auto 1fr; gap: var(--space-2); min-height: 0; }
.col--map { display: flex; }

/* ==================== 3D 地球 ==================== */
.earth {
  position: absolute;
  inset: 0;
  background: radial-gradient(ellipse at center, #0d1530 0%, #050810 100%);
}
.earth__overlay {
  position: absolute;
  left: 16px;
  bottom: 16px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  background: rgba(10, 14, 26, 0.6);
  border: 1px solid rgba(0, 229, 255, 0.3);
  border-radius: var(--radius-sm);
  font-size: 12px;
  color: var(--color-screen-muted, #6B7280);
  pointer-events: none;
}
.earth__hint { color: var(--color-screen-accent, #00E5FF); }

/* ==================== KPI Grid ==================== */
.kpi-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-1);
}
.kpi {
  position: relative;
  padding: var(--space-2) var(--space-2);
  background: linear-gradient(135deg, rgba(10, 14, 26, 0.7) 0%, rgba(10, 14, 26, 0.4) 100%);
  border: 1px solid rgba(0, 229, 255, 0.18);
  border-radius: var(--radius-md);
  overflow: hidden;
}
.kpi::before {
  content: '';
  position: absolute;
  left: 0; top: 0; bottom: 0;
  width: 3px;
}
.kpi--blue::before { background: #3B82F6; }
.kpi--green::before { background: #10F2C5; }
.kpi--purple::before { background: #A78BFA; }
.kpi--orange::before { background: #F59E0B; }

.kpi__label {
  margin: 0 0 4px 0;
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--color-screen-muted, #6B7280);
}
.kpi__value {
  margin: 0;
  display: flex;
  align-items: baseline;
  gap: 4px;
  line-height: 1;
}
.kpi__num {
  font-family: var(--font-serif);
  font-size: 48px;
  font-weight: var(--weight-semibold);
  font-variant-numeric: tabular-nums;
  color: var(--color-screen-text, #E0E6F0);
}
.kpi--blue .kpi__num { color: #93C5FD; text-shadow: 0 0 20px rgba(59, 130, 246, 0.6); }
.kpi--green .kpi__num { color: #6EE7B7; text-shadow: 0 0 20px rgba(16, 242, 197, 0.6); }
.kpi--purple .kpi__num { color: #C4B5FD; text-shadow: 0 0 20px rgba(167, 139, 250, 0.6); }
.kpi--orange .kpi__num { color: #FCD34D; text-shadow: 0 0 20px rgba(245, 158, 11, 0.6); }
.kpi__unit {
  font-size: 12px;
  color: var(--color-screen-muted, #6B7280);
  margin-left: 4px;
}

/* ==================== 2 张 ECharts ==================== */
.charts {
  display: grid;
  grid-template-rows: 1fr 1fr;
  gap: var(--space-1);
  min-height: 0;
}
.chart-card {
  background: rgba(10, 14, 26, 0.7);
  border: 1px solid rgba(16, 242, 197, 0.25);
  border-radius: var(--radius-md);
  padding: var(--space-1);
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.chart-card__title {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--color-screen-success, #10F2C5);
  margin: 0 0 4px 0;
  letter-spacing: 0.05em;
}
.chart-canvas { flex: 1; min-height: 0; }

/* ==================== 地图缩略图 ==================== */
.map-card {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: rgba(10, 14, 26, 0.7);
  border: 1px solid rgba(0, 229, 255, 0.2);
  border-radius: var(--radius-md);
  min-height: 0;
  overflow: hidden;
}
.map-card__title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-1) var(--space-2);
  font-size: 13px;
  color: var(--color-screen-accent, #00E5FF);
  border-bottom: 1px solid rgba(0, 229, 255, 0.15);
}
.map-card__warn { font-size: 11px; color: #F59E0B; }
.map-card__body { flex: 1; min-height: 0; position: relative; }
.map-mini { width: 100%; height: 100%; }
.map-card__placeholder {
  position: absolute; inset: 0;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: var(--space-1);
  color: var(--color-screen-muted, #6B7280);
  font-size: 12px;
}

/* ==================== 底部状态栏 ==================== */
.statusbar {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  height: 36px;
  padding: 0 var(--space-3);
  background: rgba(0, 0, 0, 0.5);
  border-top: 1px solid rgba(0, 229, 255, 0.15);
  font-size: 12px;
  color: var(--color-screen-muted, #6B7280);
  flex-shrink: 0;
}
.statusbar__item { display: inline-flex; align-items: center; gap: 6px; }
.statusbar__item--keys { margin-left: auto; }
.statusbar__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-screen-success, #10F2C5);
  box-shadow: 0 0 8px var(--color-screen-success, #10F2C5);
  animation: pulse 2s ease-in-out infinite;
}
.statusbar__loading {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--color-screen-accent, #00E5FF);
}
.statusbar__loading-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-screen-accent, #00E5FF);
  box-shadow: 0 0 8px var(--color-screen-accent, #00E5FF);
  animation: loading-pulse 1s ease-in-out infinite;
}

kbd {
  display: inline-block;
  padding: 1px 6px;
  margin: 0 2px;
  background: rgba(0, 229, 255, 0.12);
  border: 1px solid rgba(0, 229, 255, 0.3);
  border-radius: 3px;
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--color-screen-accent, #00E5FF);
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
@keyframes loading-pulse {
  0%, 100% { opacity: 0.3; transform: scale(0.8); }
  50%      { opacity: 1;   transform: scale(1.2); }
}

/* ==================== 响应式 ==================== */
@media (max-width: 1280px) {
  .kpi__num { font-size: 36px; }
  .body { grid-template-columns: 1.2fr 1fr 0.8fr; }
}
@media (max-width: 960px) {
  .body { grid-template-columns: 1fr; grid-template-rows: 1fr 1fr 1fr; }
  .kpi__num { font-size: 32px; }
}
</style>
