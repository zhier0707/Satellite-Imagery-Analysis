<script setup lang="ts">
/**
 * AllRecordsView - 全量 classify_records（按 user_id 过滤）
 * ====================
 *
 * 视觉: PageHeader + LoadingSkeleton + 统一表格行高/hover
 */
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { useAdminStore } from '@/stores/admin'
import { usePageEnter } from '@/composables/usePageEnter'

const admin = useAdminStore()
const sectionRef = ref<HTMLElement | null>(null)
usePageEnter(sectionRef)

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
  <section ref="sectionRef" class="records-view">
    <PageHeader
      title="全量分类记录"
      subtitle="按用户 ID 过滤,查看所有用户的分类历史。"
    >
      <template #actions>
        <el-button :icon="Refresh" :loading="loading" class="is-accent" @click="refresh">刷新</el-button>
      </template>
    </PageHeader>

    <el-card shadow="never" class="filter-card">
      <el-form inline>
        <el-form-item label="用户 ID">
          <el-input-number v-model="filterUserId" :min="1" placeholder="全部" :controls="false" clearable />
        </el-form-item>
        <el-form-item>
          <el-button class="is-accent" :loading="loading" @click="refresh">查询</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card v-if="loading && !admin.records.length" shadow="never">
      <LoadingSkeleton :rows="6" :avatar="false" />
    </el-card>

    <el-card v-else shadow="never">
      <el-table
        :data="admin.records" border
        v-loading="loading"
        empty-text="无记录"
        :row-class-name="() => 'data-row'"
      >
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="user_id" label="用户" width="100" />
        <el-table-column prop="top1_label" label="Top-1" min-width="160">
          <template #default="{ row }">
            <el-tag class="is-accent" size="small">{{ row.top1_label }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="置信度" width="120">
          <template #default="{ row }">{{ (row.top1_score * 100).toFixed(2) }}%</template>
        </el-table-column>
        <el-table-column prop="image_path" label="图像" min-width="280" />
        <el-table-column prop="created_at" label="时间" min-width="180" />
      </el-table>
    </el-card>
  </section>
</template>

<style scoped>
.records-view { max-width: 1280px; margin: 0 auto; display: flex; flex-direction: column; gap: var(--space-2); }
.filter-card { padding: 0; }
:deep(.el-table) { font-family: var(--font-sans); }
</style>
