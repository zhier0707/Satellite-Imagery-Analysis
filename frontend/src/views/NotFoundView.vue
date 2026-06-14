<script setup lang="ts">
import { useRouter } from 'vue-router'
const router = useRouter()
</script>

<template>
  <div class="nf">
    <h1>404</h1>
    <p>您访问的页面不存在。</p>
    <el-button type="primary" @click="router.push('/app')">回到首页</el-button>
  </div>
</template>

<style scoped>
.nf { min-height: 100vh; display: flex; flex-direction: column; align-items: center; justify-content: center;
  background: #f5f7fa; gap: 16px; }
.nf h1 { font-size: 96px; margin: 0; color: #909399; }
.nf p { color: #606266; }
</style>
