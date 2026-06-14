<script setup lang="ts">
/**
 * ReportsView - 我的报表导出
 *
 * - 表单 (kind, time_range, class_filter)
 * - 任务列表 + 轮询 status
 */
import { onMounted, onUnmounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Document, Download, Refresh, Delete } from '@element-plus/icons-vue'
import { useReportsStore } from '@/stores/reports'
import { reportDownloadUrl } from '@/api'
import type { ReportKind } from '@/api'

const reports = useReportsStore()
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

const startPolling = () => {
  if (pollTimer) return
  pollTimer = window.setInterval(async () => {
    const running = reports.items.filter((x) => x.status === 'queued' || x.status === 'running')
    for (const j of running) {
      try { await reports.refreshOne(j.id) } catch {}
    }
  }, 2000)
}
const stopPolling = () => {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
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
    // 后端暂未提供 delete 接口；这里仅从 UI 列表移除
    reports.items = reports.items.filter((x) => x.id !== id)
    ElMessage.success('已移除（仅前端隐藏，文件未删除）')
  } catch {}
}

const onRefresh = async (id: number) => reports.refreshOne(id)

onMounted(async () => {
  await reports.fetch()
  startPolling()
})
onUnmounted(stopPolling)
</script>

<template>
  <div class="reports-view">
    <el-card shadow="hover">
      <template #header><span><el-icon><Document /></el-icon> 报表导出</span></template>
      <el-form :model="form" label-width="100px">
        <el-form-item label="格式">
          <el-radio-group v-model="form.kind">
            <el-radio-button value="pdf">PDF</el-radio-button>
            <el-radio-button value="excel">Excel</el-radio-button>
            <el-radio-button value="csv">CSV</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="时间范围">
          <el-date-picker v-model="form.dateRange" type="datetimerange" range-separator="至"
            start-placeholder="开始" end-placeholder="结束" />
        </el-form-item>
        <el-form-item label="类别过滤">
          <el-select v-model="form.classFilter" multiple collapse-tags collapse-tags-tooltip
            placeholder="全部类别" style="width: 100%">
            <el-option v-for="c in EUROSAT_CLASSES" :key="c" :label="c" :value="c" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="submitting" @click="onSubmit">导出</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="hover" style="margin-top: 16px">
      <template #header>
        <span>历史任务 ({{ reports.items.length }})</span>
        <el-button text @click="reports.fetch()" style="float: right">
          <el-icon><Refresh /></el-icon> 刷新
        </el-button>
      </template>
      <el-table :data="reports.items" border size="small" v-loading="reports.loading">
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
            <el-button v-if="row.status === 'completed'" size="small" type="primary" tag="a"
              :href="reportDownloadUrl(row.id)" target="_blank">
              <el-icon><Download /></el-icon> 下载
            </el-button>
            <el-button size="small" @click="onRefresh(row.id)">
              <el-icon><Refresh /></el-icon> 刷新
            </el-button>
            <el-button size="small" type="danger" @click="onDelete(row.id)">
              <el-icon><Delete /></el-icon> 删除
            </el-button>
            <span v-if="row.error" class="err">错误: {{ row.error }}</span>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-model:current-page="reports.$state.items.length" background layout="prev, pager, next"
        :total="reports.total" style="margin-top: 12px; text-align: right" />
    </el-card>
  </div>
</template>

<style scoped>
.dim { color: #c0c4cc; }
.err { color: #f56c6c; font-size: 12px; margin-left: 8px; }
</style>
