<script setup lang="ts">
/**
 * LoadingSkeleton - 统一加载占位
 * ====================
 *
 * 简单组合 el-skeleton,提供 rows + avatar 两个常用变量。
 * 不做花哨:衬线白底主题下,纯灰块反而最克制。
 */
interface Props {
  /** 文本行数 */
  rows?: number
  /** 是否显示左侧圆形 avatar */
  avatar?: boolean
}
withDefaults(defineProps<Props>(), { rows: 3, avatar: false })
</script>

<template>
  <div class="loading-skeleton">
    <el-skeleton :rows="rows" animated :loading="true">
      <template #template>
        <div v-if="avatar" class="loading-skeleton__head">
          <el-skeleton-item variant="circle" style="width: 48px; height: 48px" />
          <div style="flex: 1">
            <el-skeleton-item variant="h3" style="width: 40%" />
            <el-skeleton-item variant="text" style="width: 60%; margin-top: 8px" />
          </div>
        </div>
        <el-skeleton-item
          v-for="i in rows"
          :key="i"
          variant="text"
          :style="{ width: 100 - (i - 1) * 12 + '%', marginTop: i === 1 ? '0' : '12px' }"
        />
      </template>
    </el-skeleton>
  </div>
</template>

<style scoped>
.loading-skeleton { padding: var(--space-2) 0; }
.loading-skeleton__head { display: flex; gap: var(--space-2); margin-bottom: var(--space-2); }
</style>
