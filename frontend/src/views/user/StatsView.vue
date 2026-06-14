<script setup lang="ts">
import { onMounted, onUnmounted, ref, shallowRef } from 'vue'
import * as echarts from 'echarts/core'
import { PieChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { getStats } from '@/api'

echarts.use([PieChart, TitleComponent, TooltipComponent, LegendComponent, CanvasRenderer])

const EUROSAT_CLASSES = [
  'AnnualCrop', 'Forest', 'HerbaceousVegetation', 'Highway', 'Industrial',
  'Pasture', 'PermanentCrop', 'Residential', 'River', 'SeaLake',
]

const chartEl = ref<HTMLDivElement>()
const chart = shallowRef<echarts.ECharts | null>(null)
const summary = ref({ total: 0, window: '7d' })
let timer: number | null = null

const render = () => {
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
  getStats()
    .then((s) => {
      for (const [k, v] of Object.entries(s.counts)) counts[k] = (counts[k] ?? 0) + v
      summary.value = { total: s.total + localTotal, window: `${s.window_hours / 24}d` }
      update(counts)
    })
    .catch(() => {
      summary.value = { total: localTotal, window: '本机' }
      update(counts)
    })
}

const update = (counts: Record<string, number>) => {
  const data = Object.entries(counts).filter(([, v]) => v > 0).map(([k, v]) => ({ name: k, value: v }))
  chart.value?.setOption({
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: { type: 'scroll', orient: 'vertical', right: 0, top: 'middle' },
    series: [{
      name: '分类统计', type: 'pie', radius: ['35%', '70%'], center: ['38%', '50%'],
      avoidLabelOverlap: true, itemStyle: { borderRadius: 4, borderColor: '#fff', borderWidth: 2 },
      label: { show: true, formatter: '{b}\n{d}%' }, data,
    }],
  })
}

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
  <el-card shadow="hover">
    <template #header>
      <span>分类统计</span>
      <span class="meta">窗口：{{ summary.window }} | 累计：{{ summary.total }}</span>
    </template>
    <div ref="chartEl" class="chart" />
    <p v-if="summary.total === 0" class="empty-tip">暂无分类数据，上传图像后自动累积</p>
  </el-card>
</template>

<style scoped>
.chart { width: 100%; height: 480px; }
.meta { margin-left: 16px; color: #909399; font-size: 12px; }
.empty-tip { color: #909399; font-size: 12px; margin-top: 8px; }
</style>
