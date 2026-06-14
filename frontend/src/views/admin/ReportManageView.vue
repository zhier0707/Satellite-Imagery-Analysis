<script setup lang="ts">
/**
 * ReportManageView - 全部用户的报表任务
 */
import { onMounted, ref } from 'vue'
import * as api from '@/api'
import type { ReportJob } from '@/api'

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
  <el-card shadow="hover">
    <template #header>
      <span>全部报表任务（共 {{ total }} 条）</span>
      <el-button text @click="refresh" style="float: right">刷新</el-button>
    </template>
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
          <el-button v-if="row.status === 'completed'" size="small" type="primary" tag="a"
            :href="`/api/reports/${row.id}/download`" target="_blank">下载</el-button>
          <span v-if="row.error" class="err">错误: {{ row.error }}</span>
        </template>
      </el-table-column>
    </el-table>
  </el-card>
</template>

<style scoped>
.err { color: #f56c6c; font-size: 12px; }
</style>
