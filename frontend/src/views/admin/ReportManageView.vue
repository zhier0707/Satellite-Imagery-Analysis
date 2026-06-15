<script setup lang="ts">
/**
 * ReportManageView - 全部用户的报表任务
 * ====================
 *
 * 视觉: PageHeader + LoadingSkeleton + 统一表格
 */
import { onMounted, ref } from 'vue'
import { Download, Refresh } from '@element-plus/icons-vue'
import * as api from '@/api'
import type { ReportJob } from '@/api'
import { usePageEnter } from '@/composables/usePageEnter'

const sectionRef = ref<HTMLElement | null>(null)
usePageEnter(sectionRef)

const items = ref<ReportJob[]>([])
const total = ref(0)
const loading = ref(false)

const refresh = async () => {
  loading.value = true
  try {
    const r = await api.adminListAllReports(1, 100)
    items.value = r.items
    total.value = r.total
  } finally { loading.value = false }
}

onMounted(refresh)

const statusType = (s: string) => {
  if (s === 'completed') return 'success'
  if (s === 'failed') return 'danger'
  if (s === 'running') return 'warning'
  return 'info'
}
</script>

<template>
  <section ref="sectionRef" class="report-manage-view">
    <PageHeader
      title="全部报表任务"
      subtitle="查看所有用户的报表导出记录,已完成的任务可下载。"
    >
      <template #actions>
        <el-button :icon="Refresh" :loading="loading" class="is-accent" @click="refresh">刷新</el-button>
      </template>
    </PageHeader>

    <el-card v-if="loading && !items.length" shadow="never">
      <LoadingSkeleton :rows="6" :avatar="false" />
    </el-card>

    <el-card v-else shadow="never">
      <el-table :data="items" border v-loading="loading" empty-text="无报表">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="user_id" label="用户" width="100" />
        <el-table-column prop="kind" label="格式" width="100" />
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="output_path" label="文件" min-width="280" />
        <el-table-column prop="created_at" label="创建时间" min-width="180" />
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.status === 'completed'" size="small" class="is-accent"
              tag="a" :href="`/api/reports/${row.id}/download`" target="_blank" :icon="Download">
              下载
            </el-button>
            <span v-if="row.error" class="err">错误: {{ row.error }}</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </section>
</template>

<style scoped>
.report-manage-view { max-width: 1280px; margin: 0 auto; }
.err { color: var(--color-danger); font-size: var(--text-small); }
</style>
