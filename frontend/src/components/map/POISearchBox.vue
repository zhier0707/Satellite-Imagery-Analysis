<script setup lang="ts">
/**
 * POISearchBox - POI 关键字搜索
 * ====================
 *
 * 数据流(单向):
 *   1. 用户输入 keyword → 点「搜索」/回车 → emit('search', keyword)
 *   2. 父组件调 textSearch,再把结果通过 :results 传回
 *   3. 行点击 → emit('select', poi) → 父组件 flyTo
 *
 * 设计选择:
 *   - 父组件持有 loading 状态,本组件无网络请求(职责单一)
 *   - city 可选;默认空字符串(全国搜索)
 *   - 表格列:名称 / 类型 / 地址 / 距离(可选)
 */
import { ref } from 'vue'
import { Search } from '@element-plus/icons-vue'
import type { POI } from '@/utils/amap'

interface Props {
  city?: string
  results?: POI[]
  loading?: boolean
}
withDefaults(defineProps<Props>(), { city: '', results: () => [], loading: false })

const emit = defineEmits<{
  (e: 'search', keyword: string): void
  (e: 'select', poi: POI): void
}>()

const keyword = ref('')

function onSearch() {
  const kw = keyword.value.trim()
  if (!kw) return
  emit('search', kw)
}

function onRowClick(row: POI) {
  emit('select', row)
}
</script>

<template>
  <div class="poi-search-box">
    <div class="poi-search-box__input">
      <el-input
        v-model="keyword"
        placeholder="输入 POI 关键字(例如:北京故宫)"
        clearable
        @keyup.enter="onSearch"
      >
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
      </el-input>
      <el-button type="primary" :loading="loading" @click="onSearch">搜索</el-button>
    </div>

    <el-table
      :data="results"
      height="220"
      size="small"
      empty-text="暂无结果"
      stripe
      @row-click="onRowClick"
    >
      <el-table-column prop="name" label="名称" min-width="120" show-overflow-tooltip />
      <el-table-column prop="type" label="类型" min-width="120" show-overflow-tooltip />
      <el-table-column prop="address" label="地址" min-width="160" show-overflow-tooltip />
      <el-table-column prop="distance" label="距离(米)" width="100" align="right">
        <template #default="{ row }">
          <span v-if="row.distance != null">{{ row.distance }}</span>
          <span v-else class="text-fg-3">—</span>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<style scoped>
.poi-search-box {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}
.poi-search-box__input {
  display: flex;
  gap: var(--space-1);
}
.poi-search-box__input .el-input { flex: 1; }
:deep(.el-table .el-table__row) { cursor: pointer; }
</style>
