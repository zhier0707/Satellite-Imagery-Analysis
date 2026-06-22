<script setup lang="ts">
/**
 * HeatmapView - Grad-CAM 热力图
 * ====================
 *
 * 视觉与动效:
 *   - PageHeader 替代 header
 *   - 3 种模式切换: original / cam / overlay;用 gsap.timeline() 透明度淡入淡出
 *   - 下载按钮触发动画反馈
 *
 * Phase D.1 修复:
 *   - 删除原 top5.findIndex(top1) 漏洞(永远为 0)
 *   - 新增 targetIndex ref + el-select 切换
 *   - loading 状态控制下拉禁用
 *   - overlay 模式视觉升级: mix-blend-mode: screen + opacity: 0.85
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

/** 当前选中的目标类别索引(0-9);从 store 同步初值 */
const targetIndex = ref<number>(upload.heatmapTarget ?? 0)
/** 热力图生成加载态;用于禁用下拉 */
const heatmapLoading = ref(false)
/** 热力图生成失败时的错误信息(用于错误态展示);成功或重置时清空 */
const heatmapError = ref<string | null>(null)

/** 目标类别下拉选项:top5 优先,少于 5 时用全 10 类兜底 */
const targetOptions = computed<Array<{ value: number; label: string }>>(() => {
  const top5 = upload.classify?.top5 ?? []
  if (top5.length > 0) {
    return top5.map((it, i) => ({
      value: i,
      label: `#${i + 1} ${it.label} ${(it.score * 100).toFixed(1)}%`,
    }))
  }
  // 没有 top5 时(异常态),允许 0-9 任意索引
  return Array.from({ length: 10 }, (_, i) => ({ value: i, label: `类别 #${i + 1}` }))
})

function prefersReducedMotion(): boolean {
  return window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
}

const fetchHeatmap = async (idx?: number) => {
  if (!upload.imageFile) return
  const useIdx = idx ?? targetIndex.value
  heatmapLoading.value = true
  heatmapError.value = null
  try {
    const result = await heatmap(upload.imageFile, useIdx)
    // 通过 setHeatmap action 同步写入 store(避免直接赋值绕过 action)
    upload.setHeatmap(result, useIdx)
  } catch (e: any) {
    const msg = e?.response?.data?.detail || e?.message || String(e)
    heatmapError.value = msg
    ElMessage.error('热力图生成失败：' + msg)
  } finally {
    heatmapLoading.value = false
  }
}

/** 切换下拉时重新生成热力图 */
watch(targetIndex, (idx) => {
  if (!upload.imageFile) return
  fetchHeatmap(idx)
})

/** 图像切换时,若当前有图像且下拉 != 已存 target,则重新生成 */
watch(() => upload.imageFile, () => {
  if (!upload.imageFile) return
  // 优先用 store 里的 target(用户可能从其他视图跳回)
  if (upload.heatmapTarget !== targetIndex.value) {
    targetIndex.value = upload.heatmapTarget
  }
  fetchHeatmap()
})

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

      <div class="mode-bar__target">
        <span class="text-fg-2 mode-bar__target-label">目标类别</span>
        <el-select
          v-model="targetIndex"
          :loading="heatmapLoading"
          :disabled="heatmapLoading || !upload.imageFile"
          size="default"
          style="min-width: 240px"
          placeholder="选择热力图目标类别"
        >
          <el-option
            v-for="opt in targetOptions"
            :key="opt.value"
            :value="opt.value"
            :label="opt.label"
          />
        </el-select>
      </div>
    </div>

    <EmptyState
      v-if="!upload.imageUrl"
      icon="Picture"
      title="尚无原图"
      description="请先在「图像上传」页面上传图片。"
    />

    <el-alert
      v-else-if="heatmapError"
      type="error"
      :closable="false"
      show-icon
      :title="`热力图加载失败:${heatmapError}`"
      class="heatmap-error"
    >
      <template #default>
        <p class="heatmap-error__desc">{{ heatmapError }}</p>
        <el-button size="small" type="primary" @click="fetchHeatmap(targetIndex)">重试</el-button>
      </template>
    </el-alert>

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
.mode-bar {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
  margin-bottom: var(--space-2);
}
.mode-bar__target {
  display: flex;
  align-items: center;
  gap: var(--space-1);
}
.mode-bar__target-label {
  font-size: var(--text-small);
  white-space: nowrap;
}
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
/**
 * Phase D.1: overlay 模式视觉升级
 * - mix-blend-mode: screen  提亮合成,热力图红/黄/绿色更鲜亮
 * - opacity: 0.85           比之前的 0.7 更突出 CAM 信号
 * - 仍居中叠在原图上 (inset:0 + margin:auto)
 */
.layer.cam.overlay-mode {
  position: absolute;
  inset: 0;
  margin: auto;
  mix-blend-mode: screen;
  opacity: 0.85;
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
/* ==================== 热力图错误态 ==================== */
.heatmap-error {
  margin-bottom: var(--space-2);
}
.heatmap-error :deep(.el-alert__content) {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}
.heatmap-error__desc {
  margin: 0;
  font-size: var(--text-small);
  color: var(--color-fg-2);
  font-family: var(--font-mono, monospace);
  word-break: break-all;
}
</style>
