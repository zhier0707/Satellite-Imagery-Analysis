<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useUploadStore } from '@/stores/upload'
import { heatmap } from '@/api'

type Mode = 'original' | 'cam' | 'overlay'
const mode = ref<Mode>('overlay')

const upload = useUploadStore()

const fetchHeatmap = async () => {
  if (!upload.imageFile) return
  const target = upload.classify?.top5.findIndex((x) => x.label === upload.classify?.top1.label) ?? 0
  try {
    upload.heatmap = await heatmap(upload.imageFile, Math.max(0, target))
  } catch (e: any) {
    ElMessage.error('热力图生成失败：' + (e?.message ?? e))
  }
}

watch(() => upload.imageFile, () => { if (upload.imageFile) fetchHeatmap() })

const camUrl = computed(() =>
  upload.heatmap?.png_base64 ? `data:image/png;base64,${upload.heatmap.png_base64}` : '',
)
</script>

<template>
  <el-card shadow="hover">
    <template #header>
      <span>Grad-CAM 热力图</span>
      <el-radio-group v-model="mode" size="small" style="margin-left: 24px">
        <el-radio-button value="original">原图</el-radio-button>
        <el-radio-button value="cam">热力图</el-radio-button>
        <el-radio-button value="overlay">叠加</el-radio-button>
      </el-radio-group>
    </template>
    <el-empty v-if="!upload.imageUrl" description="请先在「图像上传」页面上传图片" />
    <div v-else class="heatmap-stage">
      <el-image v-if="mode === 'original' || mode === 'overlay'" :src="upload.imageUrl" fit="contain" class="layer original" />
      <el-image v-if="mode === 'cam' || mode === 'overlay'" :src="camUrl" fit="contain" class="layer cam" :class="{ 'overlay-mode': mode === 'overlay' }" />
    </div>
    <p v-if="upload.heatmap?.mock" class="mock-tip">当前为 mock 数据（后端未加载模型权重）</p>
  </el-card>
</template>

<style scoped>
.heatmap-stage { position: relative; display: flex; justify-content: center; min-height: 320px;
  background: #f5f7fa; border-radius: 4px; overflow: hidden; }
.layer { max-width: 480px; max-height: 480px; }
.layer.original { z-index: 1; }
.layer.cam.overlay-mode { position: absolute; inset: 0; margin: auto; mix-blend-mode: screen; opacity: 0.85; z-index: 2; }
.mock-tip { color: #e6a23c; font-size: 12px; margin-top: 8px; }
</style>
