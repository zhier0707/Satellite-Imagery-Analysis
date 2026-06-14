<script setup lang="ts">
/**
 * UploadView - 图像上传与识别（用户端）
 * 改用 pinia useUploadStore 替代原 @/store
 */
import { ElMessage } from 'element-plus'
import { Upload, Picture, DataAnalysis } from '@element-plus/icons-vue'
import { classify, recordStat } from '@/api'
import { useUploadStore } from '@/stores/upload'

const upload = useUploadStore()

const onChange = async (file: any) => {
  const raw = file.raw ?? file
  if (!raw) return
  upload.setImage(raw)
  await runClassify(raw)
}

const runClassify = async (file: File) => {
  upload.loading = true
  try {
    const r = await classify(file)
    upload.classify = r
    ElMessage.success(
      r.mock
        ? '后端处于 mock 模式（无模型权重）'
        : `识别完成：${r.top1.label} (${(r.top1.score * 100).toFixed(1)}%)`,
    )
    recordStat(r.top1.label, r.top1.score).catch(() => {})
  } catch (e: any) {
    ElMessage.error('分类失败：' + (e?.message ?? e))
  } finally {
    upload.loading = false
  }
}
</script>

<template>
  <div class="upload-view">
    <el-card shadow="hover">
      <template #header>
        <span><el-icon><Upload /></el-icon> 图像上传</span>
      </template>

      <el-upload
        drag :auto-upload="false" :show-file-list="false"
        accept="image/png,image/jpeg,image/jpg" :on-change="onChange"
      >
        <el-icon class="el-icon--upload"><Picture /></el-icon>
        <div class="el-upload__text">拖拽图像到此处，或<em>点击选择</em></div>
        <template #tip>
          <div class="el-upload__tip">支持 PNG / JPG；推荐 64×64 至 384×384 卫星图像</div>
        </template>
      </el-upload>

      <el-divider />

      <div v-if="upload.imageUrl" class="preview">
        <el-image :src="upload.imageUrl" fit="contain" style="max-width: 320px; max-height: 320px" />
        <div class="preview-meta">
          <el-descriptions :column="1" size="small" border>
            <el-descriptions-item label="文件名">{{ upload.imageFile?.name }}</el-descriptions-item>
            <el-descriptions-item label="大小">
              {{ ((upload.imageFile?.size ?? 0) / 1024).toFixed(1) }} KB
            </el-descriptions-item>
            <el-descriptions-item label="类型">{{ upload.imageFile?.type }}</el-descriptions-item>
            <el-descriptions-item v-if="upload.classify" label="Top-1">
              <el-tag type="success">{{ upload.classify.top1.label }}</el-tag>
              <span class="score">{{ (upload.classify.top1.score * 100).toFixed(2) }}%</span>
            </el-descriptions-item>
          </el-descriptions>
          <el-button
            v-if="!upload.classify" type="primary"
            :loading="upload.loading"
            @click="upload.imageFile && runClassify(upload.imageFile)"
          >
            <el-icon><DataAnalysis /></el-icon> 开始识别
          </el-button>
        </div>
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.upload-view { max-width: 800px; margin: 0 auto; }
.preview { display: flex; gap: 24px; align-items: flex-start; flex-wrap: wrap; }
.preview-meta { flex: 1; min-width: 260px; }
.score { margin-left: 8px; color: #909399; font-variant-numeric: tabular-nums; }
</style>
