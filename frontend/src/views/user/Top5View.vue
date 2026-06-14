<script setup lang="ts">
import { computed } from 'vue'
import { useUploadStore } from '@/stores/upload'

const upload = useUploadStore()
const items = computed(() => upload.classify?.top5 ?? [])

const colorOf = (i: number) => {
  const palette = ['#67c23a', '#409eff', '#e6a23c', '#f56c6c', '#909399']
  return palette[i] ?? '#909399'
}
</script>

<template>
  <el-card shadow="hover">
    <template #header>Top-5 概率条</template>
    <el-empty v-if="!items.length" description="请先在「图像上传」页面上传图片" />
    <div v-else class="bar-list">
      <div v-for="(it, i) in items" :key="it.label" class="bar-row">
        <div class="bar-label">
          <el-tag :color="colorOf(i)" effect="dark" style="color: #fff; border: none">#{{ i + 1 }}</el-tag>
          <span class="name">{{ it.label }}</span>
        </div>
        <el-progress
          :percentage="Math.round(it.score * 10000) / 100"
          :color="colorOf(i)" :stroke-width="18"
          :format="(p: number) => p.toFixed(2) + '%'"
        />
      </div>
    </div>
  </el-card>
</template>

<style scoped>
.bar-list { display: flex; flex-direction: column; gap: 14px; }
.bar-row { display: flex; flex-direction: column; gap: 4px; }
.bar-label { display: flex; align-items: center; gap: 10px; }
.name { font-weight: 500; }
</style>
