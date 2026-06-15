<script setup lang="ts">
/**
 * UploadView - 图像上传与识别（用户端）
 * ====================
 *
 * 视觉与动效:
 *   - 用 PageHeader 替代 el-card header
 *   - 上传区用 SatelliteOrbitSvg 装饰 (未上传前的占位)
 *   - 分类成功后: 图片 gsap.fromTo() 从中心放大 + countUp 显示置信度
 */
import { ref, nextTick, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Picture, DataAnalysis } from '@element-plus/icons-vue'
import { gsap } from 'gsap'
import { classify, recordStat } from '@/api'
import { useUploadStore } from '@/stores/upload'
import { useCountUp } from '@/composables/useCountUp'
import { usePageEnter } from '@/composables/usePageEnter'
import SatelliteOrbitSvg from '@/components/decor/SatelliteOrbitSvg.vue'

const upload = useUploadStore()
const sectionRef = ref<HTMLElement | null>(null)
const previewRef = ref<HTMLElement | null>(null)
usePageEnter(sectionRef)

// 置信度数字滚动
const scoreTarget = ref(0)
const scoreDisplay = useCountUp(scoreTarget, 0.6)

function prefersReducedMotion(): boolean {
  return window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
}

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
    // countUp 触发 + 图片弹入
    scoreTarget.value = r.top1.score * 100
    await nextTick()
    if (!prefersReducedMotion() && previewRef.value) {
      gsap.fromTo(
        previewRef.value,
        { scale: 0.6, opacity: 0 },
        { scale: 1, opacity: 1, duration: 0.5, ease: 'back.out(1.7)' },
      )
    }
  } catch (e: any) {
    ElMessage.error('分类失败：' + (e?.message ?? e))
  } finally {
    upload.loading = false
  }
}

onMounted(() => {
  if (upload.classify) scoreTarget.value = upload.classify.top1.score * 100
})
</script>

<template>
  <section ref="sectionRef" class="upload-view">
    <PageHeader
      title="图像上传与识别"
      subtitle="拖拽或选择一张 64×64 ~ 384×384 的卫星图像,系统将给出 Top-1 类别与置信度。"
    />

    <!-- ============ 上传区 ============ -->
    <el-card v-if="!upload.imageUrl" class="upload-card" shadow="never">
      <el-upload
        drag :auto-upload="false" :show-file-list="false"
        accept="image/png,image/jpeg,image/jpg" :on-change="onChange"
        class="upload-drag"
      >
        <div class="upload-empty">
          <SatelliteOrbitSvg :height="220" />
          <el-icon class="upload-icon"><Picture /></el-icon>
          <div class="el-upload__text">拖拽图像到此处，或<em>点击选择</em></div>
          <p class="el-upload__tip">支持 PNG / JPG；推荐 64×64 至 384×384 卫星图像</p>
        </div>
      </el-upload>
    </el-card>

    <!-- ============ 预览 + 分类结果 ============ -->
    <div v-else ref="previewRef" class="preview-wrap">
      <el-card shadow="never" class="image-card">
        <template #header>
          <span class="card-head"><el-icon><Picture /></el-icon> 图像预览</span>
        </template>
        <el-image :src="upload.imageUrl" fit="contain" class="preview-image" />
      </el-card>

      <el-card shadow="never" class="meta-card">
        <template #header>
          <span class="card-head"><el-icon><DataAnalysis /></el-icon> 识别结果</span>
        </template>
        <el-descriptions :column="1" size="default" border>
          <el-descriptions-item label="文件名">{{ upload.imageFile?.name }}</el-descriptions-item>
          <el-descriptions-item label="大小">
            {{ ((upload.imageFile?.size ?? 0) / 1024).toFixed(1) }} KB
          </el-descriptions-item>
          <el-descriptions-item label="类型">{{ upload.imageFile?.type }}</el-descriptions-item>
          <el-descriptions-item v-if="upload.classify" label="Top-1 类别">
            <el-tag class="is-accent" effect="dark" round>{{ upload.classify.top1.label }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item v-if="upload.classify" label="置信度">
            <span class="score">{{ scoreDisplay.toFixed(2) }}%</span>
          </el-descriptions-item>
        </el-descriptions>
        <div class="actions">
          <el-button
            v-if="!upload.classify" class="is-accent"
            :loading="upload.loading"
            @click="upload.imageFile && runClassify(upload.imageFile)"
          >
            <el-icon><DataAnalysis /></el-icon> 开始识别
          </el-button>
          <el-button @click="upload.resetUpload()">重置</el-button>
        </div>
      </el-card>
    </div>
  </section>
</template>

<style scoped>
.upload-view { max-width: 1080px; margin: 0 auto; }

.upload-card {
  background: var(--color-bg-soft);
  border-style: dashed;
}
.upload-drag {
  width: 100%;
}
:deep(.upload-drag .el-upload-dragger) {
  background: var(--color-bg);
  border: 1.5px dashed var(--color-border-strong);
  padding: var(--space-3);
}
.upload-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-1);
  position: relative;
}
.upload-icon {
  position: absolute;
  top: 60%;
  left: 50%;
  transform: translate(-50%, -50%);
  font-size: 48px;
  color: var(--color-accent);
  opacity: 0.45;
  pointer-events: none;
}
.el-upload__text {
  font-family: var(--font-serif);
  font-size: var(--text-h3);
  color: var(--color-fg);
  font-weight: var(--weight-medium);
}
.el-upload__text em { color: var(--color-accent); font-style: normal; }
.el-upload__tip {
  color: var(--color-fg-3);
  font-size: var(--text-small);
  margin: 0;
}

.preview-wrap {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.4fr);
  gap: var(--space-3);
}
.image-card .preview-image {
  width: 100%;
  max-width: 480px;
  max-height: 480px;
  display: block;
  margin: 0 auto;
  background: var(--color-bg-soft);
  border-radius: var(--radius-sm);
}
.card-head {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-family: var(--font-serif);
  font-weight: var(--weight-semibold);
  font-size: var(--text-h3);
  color: var(--color-fg);
}
.actions {
  margin-top: var(--space-2);
  display: flex;
  gap: var(--space-1);
}
.score {
  font-family: var(--font-serif);
  font-size: var(--text-h2);
  font-weight: var(--weight-semibold);
  color: var(--color-accent);
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.01em;
}

@media (max-width: 900px) {
  .preview-wrap { grid-template-columns: 1fr; }
}
</style>
