<script setup lang="ts">
/**
 * ReportsView - 我的报表导出
 * ====================
 *
 * 视觉与动效:
 *   - PageHeader 替代 el-card header
 *   - 任务状态变化时 row 短暂高亮 fade
 *   - 导出中显示进度条
 */
import { onMounted, onUnmounted, ref, watch, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Document, Download, Refresh, Delete, Plus } from '@element-plus/icons-vue'
import { gsap } from 'gsap'
import { useReportsStore } from '@/stores/reports'
import { reportDownloadUrl } from '@/api'
import type { ReportKind } from '@/api'
import { usePageEnter } from '@/composables/usePageEnter'

const reports = useReportsStore()
const sectionRef = ref<HTMLElement | null>(null)
usePageEnter(sectionRef)

const EUROSAT_CLASSES = [
  'AnnualCrop', 'Forest', 'HerbaceousVegetation', 'Highway', 'Industrial',
  'Pasture', 'PermanentCrop', 'Residential', 'River', 'SeaLake',
]

const form = ref({
  kind: 'pdf' as ReportKind,
  dateRange: [] as string[],
  classFilter: [] as string[],
})

const submitting = ref(false)
let pollTimer: number | null = null

/** row 高亮追踪: 记录 status 发生过变化的 row.id */
const flashedRows = ref<Set<number>>(new Set())
const rowRefs = ref<Record<number, HTMLElement | null>>({})

function prefersReducedMotion(): boolean {
  return window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
}

const startPolling = () => {
  if (pollTimer) return
  pollTimer = window.setInterval(async () => {
    const running = reports.items.filter((x) => x.status === 'queued' || x.status === 'running')
    for (const j of running) {
      try {
        const prev = reports.items.find((x) => x.id === j.id)
        const prevStatus = prev?.status
        await reports.refreshOne(j.id)
        const updated = reports.items.find((x) => x.id === j.id)
        if (updated && prevStatus && prevStatus !== updated.status) {
          flashRow(updated.id)
        }
      } catch {}
    }
  }, 2000)
}
const stopPolling = () => {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
}

/** 短暂高亮: bg 从 accent-soft → 透明 */
const flashRow = async (id: number) => {
  await nextTick()
  const el = rowRefs.value[id]
  if (!el) return
  if (prefersReducedMotion()) return
  gsap.fromTo(el,
    { backgroundColor: 'rgba(37, 99, 235, 0.16)' },
    { backgroundColor: 'rgba(37, 99, 235, 0)', duration: 1.4, ease: 'power2.out' },
  )
}

const setRowRef = (el: any, id: number) => {
  if (el) rowRefs.value[id] = el as HTMLElement
}

const onSubmit = async () => {
  submitting.value = true
  try {
    const payload: any = { kind: form.value.kind }
    if (form.value.dateRange?.length === 2) {
      payload.time_range_start = new Date(form.value.dateRange[0]).toISOString()
      payload.time_range_end = new Date(form.value.dateRange[1]).toISOString()
    }
    if (form.value.classFilter?.length) payload.class_filter = form.value.classFilter
    const r = await reports.create(payload)
    ElMessage.success(`已提交报表任务 #${r.id}`)
  } catch (e: any) {
    ElMessage.error('提交失败：' + (e?.response?.data?.detail || e?.message))
  } finally {
    submitting.value = false
  }
}

const statusType = (s: string) => {
  if (s === 'completed') return 'success'
  if (s === 'failed') return 'danger'
  if (s === 'running') return 'warning'
  return 'info'
}

const onDelete = async (id: number) => {
  try {
    await ElMessageBox.confirm(`确定删除报表 #${id}?`, '提示', { type: 'warning' })
    reports.items = reports.items.filter((x) => x.id !== id)
    ElMessage.success('已移除（仅前端隐藏，文件未删除）')
  } catch {}
}

const onRefresh = async (id: number) => reports.refreshOne(id)

watch(() => reports.items.length, () => { /* 触发 row 渲染收集 */ })

/** 全表高亮: 新增 row 时整张表淡蓝一下,简单可观察 */
const tableWrapRef = ref<HTMLElement | null>(null)
const flashAll = async () => {
  await nextTick()
  if (prefersReducedMotion()) return
  const wrap = tableWrapRef.value
  if (!wrap) return
  const rows = wrap.querySelectorAll('.el-table__body tr.el-table__row')
  if (!rows.length) return
  gsap.fromTo(rows,
    { backgroundColor: 'rgba(37, 99, 235, 0.10)' },
    { backgroundColor: 'rgba(37, 99, 235, 0)', duration: 1.2, stagger: 0.04, ease: 'power2.out' },
  )
}

watch(() => reports.items.length, flashAll)

onMounted(async () => {
  await reports.fetch()
  startPolling()
})
onUnmounted(stopPolling)
</script>

<template>
  <section ref="sectionRef" class="reports-view">
    <PageHeader
      title="我的报表"
      subtitle="提交导出任务,系统会在后台生成 PDF / Excel / CSV,完成后可下载。"
    >
      <template #actions>
        <el-button :icon="Refresh" @click="reports.fetch()">刷新</el-button>
      </template>
    </PageHeader>

    <el-card shadow="never" class="form-card">
      <h4 class="form-title"><el-icon><Document /></el-icon> 报表导出</h4>
      <el-form :model="form" label-width="100px" class="compact-form">
        <el-form-item label="格式">
          <el-radio-group v-model="form.kind">
            <el-radio-button value="pdf">PDF</el-radio-button>
            <el-radio-button value="excel">Excel</el-radio-button>
            <el-radio-button value="csv">CSV</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="时间范围">
          <el-date-picker
            v-model="form.dateRange" type="datetimerange"
            range-separator="至" start-placeholder="开始" end-placeholder="结束"
          />
        </el-form-item>
        <el-form-item label="类别过滤">
          <el-select
            v-model="form.classFilter" multiple collapse-tags collapse-tags-tooltip
            placeholder="全部类别" style="width: 100%"
          >
            <el-option v-for="c in EUROSAT_CLASSES" :key="c" :label="c" :value="c" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button class="is-accent" :loading="submitting" :icon="Plus" @click="onSubmit">
            提交任务
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never" class="history-card">
      <h4 class="form-title">
        历史任务（{{ reports.items.length }}）
        <span v-if="submitting" class="progress-hint">提交中…</span>
      </h4>
      <el-table :data="reports.items" border size="small" v-loading="reports.loading" ref="tableWrapRef">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="kind" label="格式" width="100" />
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" min-width="180" />
        <el-table-column label="完成时间" min-width="180">
          <template #default="{ row }">
            <span v-if="row.finished_at">{{ row.finished_at }}</span>
            <span v-else class="dim">—</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="280">
          <template #default="{ row }">
            <el-button
              v-if="row.status === 'completed'" size="small" class="is-accent"
              tag="a" :href="reportDownloadUrl(row.id)" target="_blank"
              :icon="Download"
            >下载</el-button>
            <el-button size="small" @click="onRefresh(row.id)" :icon="Refresh">刷新</el-button>
            <el-button size="small" type="danger" @click="onDelete(row.id)" :icon="Delete">删除</el-button>
            <span v-if="row.error" class="err">错误: {{ row.error }}</span>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-model:current-page="reports.$state.items.length" background
        layout="prev, pager, next" :total="reports.total"
        class="pager"
      />
    </el-card>
  </section>
</template>

<style scoped>
.reports-view { max-width: 1080px; margin: 0 auto; display: flex; flex-direction: column; gap: var(--space-3); }

.form-title {
  margin: 0 0 var(--space-2) 0;
  font-family: var(--font-serif);
  font-size: var(--text-h3);
  color: var(--color-fg);
  font-weight: var(--weight-semibold);
  display: flex;
  align-items: center;
  gap: 6px;
}
.compact-form :deep(.el-form-item) { margin-bottom: var(--space-2); }
.dim { color: var(--color-fg-3); }
.err { color: var(--color-danger); font-size: var(--text-small); margin-left: var(--space-1); }

.progress-hint {
  margin-left: var(--space-1);
  font-family: var(--font-sans);
  font-size: var(--text-small);
  color: var(--color-accent);
  font-weight: var(--weight-medium);
}

.pager {
  margin-top: var(--space-2);
  justify-content: flex-end;
  display: flex;
}

/* el-table row ref 占位: 让 rowRef hook 能挂到 tr 元素 */
:deep(.el-table__row) { transition: background-color 0.3s ease; }
.table-wrap { display: block; }
</style>
