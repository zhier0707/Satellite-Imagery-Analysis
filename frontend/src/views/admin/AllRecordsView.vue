<script setup lang="ts">
/**
 * AllRecordsView - 全量 classify_records（按 user_id 过滤）
 */
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useAdminStore } from '@/stores/admin'

const admin = useAdminStore()
const filterUserId = ref<number | undefined>(undefined)
const loading = ref(false)

const refresh = async () => {
  loading.value = true
  try { await admin.fetchRecords(filterUserId.value, 1, 100) }
  finally { loading.value = false }
}

onMounted(refresh)
</script>

<template>
  <el-card shadow="hover">
    <template #header>
      <span>全量分类记录（共 {{ admin.recordsTotal }} 条）</span>
    </template>
    <el-form inline style="margin-bottom: 12px">
      <el-form-item label="用户 ID">
        <el-input-number v-model="filterUserId" :min="1" placeholder="全部" :controls="false" clearable />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="refresh" :loading="loading">查询</el-button>
      </el-form-item>
    </el-form>
    <el-table :data="admin.records" border v-loading="loading" empty-text="无记录">
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="user_id" label="用户" width="100" />
      <el-table-column prop="top1_label" label="Top-1" width="160" />
      <el-table-column label="置信度" width="120">
        <template #default="{ row }">{{ (row.top1_score * 100).toFixed(2) }}%</template>
      </el-table-column>
      <el-table-column prop="image_path" label="图像" min-width="280" />
      <el-table-column prop="created_at" label="时间" min-width="180" />
    </el-table>
  </el-card>
</template>
