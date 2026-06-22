<script setup lang="ts">
/**
 * StatsView - 分类统计饼图
 * ====================
 *
 * 视觉与动效:
 *   - PageHeader 替代 header
 *   - ECharts 配色与新主题对齐 (去掉饱和绿/黄/红)
 *   - countUp 数字
 */
import { onMounted, onUnmounted, ref, shallowRef, watch } from 'vue'
import * as echarts from 'echarts/core'
import { PieChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { gsap } from 'gsap'
import { getStats, getDashboardStats } from '@/api'
import { useCountUp } from '@/composables/useCountUp'
import { usePageEnter } from '@/composables/usePageEnter'

echarts.use([PieChart, TitleComponent, TooltipComponent, LegendComponent, CanvasRenderer])

// 主题色板: 与全局 token 对齐 (蓝主导 + 中性灰)
const THEME_PALETTE = [
  '#2563EB', '#1A1A1A', '#525252', '#A3A3A3', '#1D4FD8',
  '#7A7A7A', '#D4D4D8', '#DBE7FF', '#4A4A4A', '#E4E4E4',
]

const EUROSAT_CLASSES = [
  'AnnualCrop', 'Forest', 'HerbaceousVegetation', 'Highway', 'Industrial',
  'Pasture', 'PermanentCrop', 'Residential', 'River', 'SeaLake',
]

const sectionRef = ref<HTMLElement | null>(null)
usePageEnter(sectionRef)

const chartEl = ref<HTMLDivElement>()
const chart = shallowRef<echarts.ECharts | null>(null)
/**
 * summary:
 *   - total      用于触发 EmptyState 的关键字段
 *   - window     展示文案,如 "7d" / "本机"
 *   - kpi        大屏 KPI(总记录/今日新增/活跃用户/平均置信度)
 *   - distribution 后端分类分布(Record<string, number>)
 */
const summary = ref<{
  total: number
  window: string
  kpi: { total_records: number; today_new: number; active_users: number; accuracy_avg: number } | null
  distribution: Record<string, number> | null
}>({
  total: 0,
  window: '7d',
  kpi: null,
  distribution: null,
})
const totalTarget = ref(0)
const totalDisplay = useCountUp(totalTarget, 0.6)

/** time_series 全为 0 判定:用于 EmptyState 收窄触发 */
function isTimeSeriesAllZero(ts: Array<{ count: number }> | undefined | null): boolean {
  if (!ts || ts.length === 0) return true
  return ts.every((p) => !p.count)
}

let timer: number | null = null

function prefersReducedMotion(): boolean {
  return window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
}

const render = async () => {
  if (!chartEl.value || !chart.value) return
  const counts: Record<string, number> = {}
  for (const c of EUROSAT_CLASSES) counts[c] = 0
  let localTotal = 0
  try {
    const local = JSON.parse(localStorage.getItem('local_counts') ?? '{}')
    for (const [k, v] of Object.entries(local)) {
      counts[k] = (counts[k] ?? 0) + (v as number)
      localTotal += v as number
    }
  } catch {}

  // 主数据源: 大屏聚合(getDashboardStats → 数据库真实数据)
  // in-memory(getStats)仅作辅助
  let dashboardTotal = 0
  let dashboardKpi: typeof summary.value.kpi = null
  let dashboardDistribution: Record<string, number> = {}
  let timeSeriesAllZero = true
  let dashboardOk = false
  try {
    const d = await getDashboardStats()
    dashboardOk = true
    dashboardKpi = d.kpi
    dashboardDistribution = d.classification_distribution ?? {}
    dashboardTotal = d.kpi?.total_records ?? 0
    timeSeriesAllZero = isTimeSeriesAllZero(d.time_series)
    for (const [k, v] of Object.entries(dashboardDistribution)) {
      counts[k] = (counts[k] ?? 0) + v
    }
  } catch {
    // 大屏接口失败,继续尝试 in-memory
  }

  // 辅助: in-memory getStats(进程级环形缓冲)
  getStats()
    .then((s) => {
      for (const [k, v] of Object.entries(s.counts)) counts[k] = (counts[k] ?? 0) + v
      // 决策:大屏接口正常时优先用大屏;否则退回 in-memory
      const finalTotal = dashboardOk ? dashboardTotal + localTotal : s.total + localTotal
      const windowLabel = dashboardOk ? 'DB' : `${s.window_hours / 24}d`
      summary.value = {
        total: finalTotal,
        window: windowLabel,
        kpi: dashboardKpi,
        distribution: dashboardOk ? dashboardDistribution : null,
      }
      totalTarget.value = finalTotal
      update(counts, finalTotal === 0 && timeSeriesAllZero)
    })
    .catch(() => {
      const finalTotal = dashboardTotal + localTotal
      summary.value = {
        total: finalTotal,
        window: dashboardOk ? 'DB' : '本机',
        kpi: dashboardKpi,
        distribution: dashboardOk ? dashboardDistribution : null,
      }
      totalTarget.value = finalTotal
      update(counts, finalTotal === 0 && timeSeriesAllZero)
    })
}

const update = (counts: Record<string, number>, _isEmpty = false) => {
  // 空态条件由模板根据 summary.total 决定;此处仅负责更新图表
  void _isEmpty
  const data = Object.entries(counts)
    .filter(([, v]) => v > 0)
    .map(([k, v], i) => ({ name: k, value: v, itemStyle: { color: THEME_PALETTE[i % THEME_PALETTE.length] } }))

  chart.value?.setOption({
    tooltip: { trigger: 'item', formatter: '{b}<br/>{c} 次 ({d}%)' },
    legend: { type: 'scroll', orient: 'vertical', right: 0, top: 'middle',
      textStyle: { color: '#525252', fontFamily: 'Inter, Noto Sans SC, sans-serif', fontSize: 13 } },
    series: [{
      name: '分类统计',
      type: 'pie',
      radius: ['42%', '72%'],
      center: ['38%', '50%'],
      avoidLabelOverlap: true,
      itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
      label: {
        show: true,
        formatter: '{b}\n{d}%',
        color: '#1A1A1A',
        fontFamily: 'Inter, Noto Sans SC, sans-serif',
        fontSize: 12,
      },
      labelLine: { lineStyle: { color: '#A3A3A3' } },
      data,
      animationType: prefersReducedMotion() ? 'expansion' : 'scale',
      animationDuration: 700,
      animationEasing: 'cubicOut',
    }],
  })
}

watch(totalTarget, () => {
  if (chart.value && !prefersReducedMotion()) {
    gsap.fromTo('.stats-number', { scale: 0.85 }, { scale: 1, duration: 0.4, ease: 'back.out(2)' })
  }
})

const onLocalCount = (e: StorageEvent) => { if (e.key === 'local_counts') render() }

onMounted(() => {
  if (chartEl.value) chart.value = echarts.init(chartEl.value)
  render()
  timer = window.setInterval(render, 10000)
  window.addEventListener('storage', onLocalCount)
})
onUnmounted(() => {
  if (timer) clearInterval(timer)
  window.removeEventListener('storage', onLocalCount)
  chart.value?.dispose()
})
</script>

<template>
  <section ref="sectionRef" class="stats-view">
    <PageHeader
      title="分类统计"
      subtitle="用户上传图像后的累计分类分布,按 EuroSAT 10 类聚合。"
    >
      <template #actions>
        <span class="meta">
          窗口 {{ summary.window }} ·
          <span class="stats-number">{{ totalDisplay }}</span> 张
        </span>
      </template>
    </PageHeader>

    <el-card v-if="summary.total === 0" shadow="never" class="empty-card">
      <EmptyState
        icon="PieChart"
        title="暂无分类数据"
        description="上传图像后自动累积,每 10s 刷新一次。"
      />
    </el-card>

    <el-card v-else shadow="never">
      <div ref="chartEl" class="chart" />
    </el-card>
  </section>
</template>

<style scoped>
.stats-view { max-width: 1080px; margin: 0 auto; }
.meta {
  color: var(--color-fg-2);
  font-size: var(--text-body);
  font-family: var(--font-sans);
}
.stats-number {
  font-family: var(--font-serif);
  font-size: var(--text-h3);
  font-weight: var(--weight-semibold);
  color: var(--color-accent);
  font-variant-numeric: tabular-nums;
  display: inline-block;
  transform-origin: center;
  padding: 0 4px;
}
.chart { width: 100%; height: 480px; }
.empty-card :deep(.el-card__body) { padding: 0; }
</style>
