<script setup lang="ts">
/**
 * HeatmapView - Grad-CAM 热力图
 * ====================
 *
 * 视觉与动效:
 *   - PageHeader 替代 header
 *   - 3 种模式切换: original / cam / overlay;用 gsap.timeline() 透明度淡入淡出
 *   - 下载按钮触发动画反馈
 */
import { computed, ref, watch, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { gsap } from 'gsap'
import { Download } from '@element-plus/icons-vue'
import { useUploadStore } from '@/stores/upload'
import { heatmap } from '@/api'
import { usePageEnter } from '@/composables/usePageEnter'

type Mode = 'original' | 'cam' | 'overlay'
const mode = ref<Mode>('overlay')

const upload = useUploadStore()
const sectionRef = ref<HTMLElement | null>(null)
usePageEnter(sectionRef)

const stageRef = ref<HTMLElement | null>(null)
const originalRef = ref<HTMLElement | null>(null)
const camRef = ref<HTMLElement | null>(null)

function prefersReducedMotion(): boolean {
  return window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
}

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

/** 模式切换: gsap.timeline() 透明度淡入淡出 */
async function applyMode(newMode: Mode) {
  await nextTick()
  if (prefersReducedMotion()) {
    // 直接显示终态
    if (originalRef.value) gsap.set(originalRef.value, { opacity: (newMode === 'original' || newMode === 'overlay') ? 1 : 0 })
    if (camRef.value) gsap.set(camRef.value, { opacity: (newMode === 'cam' || newMode === 'overlay') ? (newMode === 'overlay' ? 0.85 : 1) : 0 })
    return
  }
  const tl = gsap.timeline()
  // 淡出当前可见
  tl.to([originalRef.value, camRef.value].filter(Boolean) as Element[], {
    opacity: 0,
    duration: 0.12,
    ease: 'power1.out',
  })
  // 淡入新目标
  tl.add(() => {
    if (newMode === 'original' && originalRef.value) {
      gsap.to(originalRef.value, { opacity: 1, duration: 0.13, ease: 'power1.out' })
    } else if (newMode === 'cam' && camRef.value) {
      gsap.to(camRef.value, { opacity: 1, duration: 0.13, ease: 'power1.out' })
    } else if (newMode === 'overlay') {
      if (originalRef.value) gsap.to(originalRef.value, { opacity: 1, duration: 0.13 })
      if (camRef.value) gsap.to(camRef.value, { opacity: 0.85, duration: 0.13 })
    }
  })
}

watch(mode, applyMode)
watch(() => upload.heatmap, () => { if (upload.heatmap) applyMode(mode.value) })

/** 下载 PNG: 先做反馈动画,再触发浏览器下载 */
const downloading = ref(false)
async function onDownload() {
  if (!camUrl.value) {
    ElMessage.warning('暂无可下载的热力图')
    return
  }
  downloading.value = true
  if (stageRef.value && !prefersReducedMotion()) {
    gsap.fromTo(stageRef.value, { scale: 1 }, { scale: 0.96, duration: 0.12, yoyo: true, repeat: 1, ease: 'power1.inOut' })
  }
  try {
    const a = document.createElement('a')
    a.href = camUrl.value
    a.download = `heatmap-${Date.now()}.png`
    a.click()
  } finally {
    setTimeout(() => { downloading.value = false }, 300)
  }
}
</script>

<template>
  <section ref="sectionRef" class="heatmap-view">
    <PageHeader
      title="Grad-CAM 热力图"
      subtitle="可解释性分析：模型关注了原图的哪些像素。模式切换使用 GSAP timeline 透明度淡入淡出。"
    >
      <template #actions>
        <el-button :loading="downloading" :icon="Download" @click="onDownload" :disabled="!camUrl">
          下载 PNG
        </el-button>
      </template>
    </PageHeader>

    <div class="mode-bar">
      <el-radio-group v-model="mode" size="default">
        <el-radio-button value="original">原图</el-radio-button>
        <el-radio-button value="cam">热力图</el-radio-button>
        <el-radio-button value="overlay">叠加</el-radio-button>
      </el-radio-group>
    </div>

    <EmptyState
      v-if="!upload.imageUrl"
      icon="Picture"
      title="尚无原图"
      description="请先在「图像上传」页面上传图片。"
    />

    <div v-else ref="stageRef" class="heatmap-stage">
      <el-image
        v-if="mode === 'original' || mode === 'overlay'"
        ref="originalRef"
        :src="upload.imageUrl" fit="contain"
        class="layer original"
      />
      <el-image
        v-if="mode === 'cam' || mode === 'overlay'"
        ref="camRef"
        :src="camUrl" fit="contain"
        class="layer cam"
        :class="{ 'overlay-mode': mode === 'overlay' }"
      />
    </div>

    <p v-if="upload.heatmap?.mock" class="mock-tip">
      当前为 mock 数据（后端未加载模型权重），热力图为示意图。
    </p>
  </section>
</template>

<style scoped>
.heatmap-view { max-width: 1080px; margin: 0 auto; }
.mode-bar { margin-bottom: var(--space-2); }
.heatmap-stage {
  position: relative;
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 360px;
  background: var(--color-bg-soft);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  overflow: hidden;
  padding: var(--space-2);
}
.layer {
  max-width: 480px;
  max-height: 480px;
  opacity: 1;
  border-radius: var(--radius-sm);
}
.layer.cam.overlay-mode {
  position: absolute;
  inset: 0;
  margin: auto;
  mix-blend-mode: multiply;
  opacity: 0.7;
  z-index: 2;
}
.mock-tip {
  margin-top: var(--space-2);
  padding: var(--space-1) var(--space-2);
  background: var(--color-accent-soft);
  color: var(--color-accent);
  border-radius: var(--radius-sm);
  font-size: var(--text-small);
}
</style>
