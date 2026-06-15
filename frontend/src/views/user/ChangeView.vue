<script setup lang="ts">
/**
 * ChangeView - 时相变化检测
 * ====================
 *
 * 视觉与动效:
 *   - PageHeader 替代 header
 *   - A → B 用 GSAP 横向位移 (slide-left / slide-right)
 *   - 中间箭头 + 摘要标签 fade-in
 *   - top1_changed 红色标签 pulse 循环 3 次
 */
import { ref, nextTick, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Picture, Refresh, Aim, ArrowRight } from '@element-plus/icons-vue'
import { gsap } from 'gsap'
import { useUploadStore } from '@/stores/upload'
import { changeDetect } from '@/api'
import { usePageEnter } from '@/composables/usePageEnter'

const upload = useUploadStore()
const sectionRef = ref<HTMLElement | null>(null)
usePageEnter(sectionRef)

const resultARef = ref<HTMLElement | null>(null)
const resultBRef = ref<HTMLElement | null>(null)
const changedTagRef = ref<HTMLElement | null>(null)

function prefersReducedMotion(): boolean {
  return window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
}

const onA = (file: any) => {
  const raw = file.raw ?? file
  if (raw) upload.setImageA(raw)
}
const onB = (file: any) => {
  const raw = file.raw ?? file
  if (raw) upload.setImageB(raw)
}

const runChange = async () => {
  if (!upload.imageA || !upload.imageB) {
    ElMessage.warning('请先分别上传两期图像 A 和 B')
    return
  }
  upload.changeLoading = true
  try {
    upload.changeResult = await changeDetect(upload.imageA, upload.imageB)
    ElMessage.success('变化检测完成')
    await nextTick()
    playEnterAnimation()
  } catch (e: any) {
    ElMessage.error('变化检测失败：' + (e?.response?.data?.detail || e?.message || e))
  } finally {
    upload.changeLoading = false
  }
}

const playEnterAnimation = async () => {
  if (prefersReducedMotion()) return
  // A slide-left 0.4s, B slide-right 0.4s
  if (resultARef.value) {
    gsap.fromTo(resultARef.value,
      { x: 60, opacity: 0 },
      { x: 0, opacity: 1, duration: 0.4, ease: 'power2.out' },
    )
  }
  if (resultBRef.value) {
    gsap.fromTo(resultBRef.value,
      { x: -60, opacity: 0 },
      { x: 0, opacity: 1, duration: 0.4, ease: 'power2.out' },
    )
  }
  // top1_changed pulse
  const hasChanged = upload.changeResult?.changes.some((c) => c.type === 'top1_changed')
  if (hasChanged && changedTagRef.value) {
    gsap.fromTo(changedTagRef.value,
      { scale: 1 },
      { scale: 1.1, duration: 0.4, yoyo: true, repeat: 3, ease: 'power1.inOut' },
    )
  }
}

const tagType = (t: string) => {
  if (t === 'top1_changed') return 'danger'
  if (t === 'label_gained') return 'success'
  if (t === 'label_lost') return 'warning'
  return 'info'
}
const tagLabel = (t: string) => {
  if (t === 'top1_changed') return '主类变化'
  if (t === 'label_gained') return '新增标签'
  if (t === 'label_lost') return '失去标签'
  return t
}

onMounted(() => { if (upload.changeResult) playEnterAnimation() })
</script>

<template>
  <section ref="sectionRef" class="change-view">
    <PageHeader
      title="时相变化检测"
      subtitle="分别上传两期图像 A / B,系统给出 Top-1 是否变化、变化标签列表与自然语言摘要。"
    />

    <!-- ============ 上传区 ============ -->
    <el-card shadow="never" class="upload-card">
      <div class="upload-row">
        <div class="upload-col">
          <h4 class="col-title">时期 A · 早期</h4>
          <el-upload drag :auto-upload="false" :show-file-list="false"
            accept="image/png,image/jpeg,image/jpg" :on-change="onA">
            <el-icon class="el-icon--upload"><Picture /></el-icon>
            <div class="el-upload__text">拖拽 A 图或<em>点击选择</em></div>
          </el-upload>
          <div v-if="upload.imageAUrl" class="preview">
            <el-image :src="upload.imageAUrl" fit="contain" class="preview-img" />
          </div>
        </div>

        <div class="upload-col">
          <h4 class="col-title">时期 B · 晚期</h4>
          <el-upload drag :auto-upload="false" :show-file-list="false"
            accept="image/png,image/jpeg,image/jpg" :on-change="onB">
            <el-icon class="el-icon--upload"><Picture /></el-icon>
            <div class="el-upload__text">拖拽 B 图或<em>点击选择</em></div>
          </el-upload>
          <div v-if="upload.imageBUrl" class="preview">
            <el-image :src="upload.imageBUrl" fit="contain" class="preview-img" />
          </div>
        </div>
      </div>

      <div class="actions">
        <el-button class="is-accent" :loading="upload.changeLoading" @click="runChange">
          <el-icon><Refresh /></el-icon> 开始对比
        </el-button>
        <el-button @click="upload.clearChange()">清空</el-button>
      </div>
    </el-card>

    <!-- ============ 结果区 ============ -->
    <el-card v-if="upload.changeResult" shadow="never" class="result-card">
      <template #header>
        <div class="result-head">
          <span class="result-title">
            <el-icon><Aim /></el-icon>
            检测结果
          </span>
          <el-tag
            v-if="upload.changeResult.changes.find((c) => c.type === 'top1_changed')"
            ref="changedTagRef"
            type="danger"
            effect="dark"
            class="changed-tag"
          >
            top1 已变化
          </el-tag>
          <el-tag v-else type="success" effect="dark">top1 未变</el-tag>
        </div>
      </template>

      <el-alert
        :title="upload.changeResult.summary"
        type="info"
        :closable="false"
        show-icon
      />

      <h4 class="section-title">Top-1 对比</h4>
      <div class="compare-row">
        <div ref="resultARef" class="compare-side a-side">
          <span class="phase-label">A · 早期</span>
          <span class="phase-label-name">{{ upload.changeResult.top1_a.label }}</span>
          <span class="phase-score">{{ (upload.changeResult.top1_a.score * 100).toFixed(2) }}%</span>
        </div>
        <el-icon class="arrow-icon"><ArrowRight /></el-icon>
        <div ref="resultBRef" class="compare-side b-side">
          <span class="phase-label">B · 晚期</span>
          <span class="phase-label-name">{{ upload.changeResult.top1_b.label }}</span>
          <span class="phase-score">{{ (upload.changeResult.top1_b.score * 100).toFixed(2) }}%</span>
        </div>
      </div>

      <h4 class="section-title">变化列表（{{ upload.changeResult.changes.length }} 项）</h4>
      <el-table :data="upload.changeResult.changes" border size="small" empty-text="无变化">
        <el-table-column label="类型" width="120">
          <template #default="{ row }">
            <el-tag :type="tagType(row.type)" size="small">{{ tagLabel(row.type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="label" label="标签" />
        <el-table-column label="A 时期分数">
          <template #default="{ row }">
            <span v-if="row.score_a !== undefined">{{ (row.score_a * 100).toFixed(2) }}%</span>
            <span v-else class="dim">—</span>
          </template>
        </el-table-column>
        <el-table-column label="B 时期分数">
          <template #default="{ row }">
            <span v-if="row.score_b !== undefined">{{ (row.score_b * 100).toFixed(2) }}%</span>
            <span v-else class="dim">—</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </section>
</template>

<style scoped>
.change-view { max-width: 1080px; margin: 0 auto; display: flex; flex-direction: column; gap: var(--space-3); }

.col-title {
  margin: 0 0 var(--space-1) 0;
  color: var(--color-fg-2);
  font-family: var(--font-serif);
  font-size: var(--text-h3);
  font-weight: var(--weight-semibold);
}
.upload-row { display: flex; gap: var(--space-3); flex-wrap: wrap; }
.upload-col { flex: 1; min-width: 320px; }
.preview { margin-top: var(--space-2); text-align: center; }
.preview-img { max-width: 280px; max-height: 280px; border-radius: var(--radius-sm); border: 1px solid var(--color-border); }
.actions { margin-top: var(--space-3); display: flex; gap: var(--space-1); }

.result-head {
  display: flex;
  align-items: center;
  gap: var(--space-1);
}
.result-title {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-family: var(--font-serif);
  font-size: var(--text-h3);
  font-weight: var(--weight-semibold);
  color: var(--color-fg);
  margin-right: var(--space-1);
}
.changed-tag { transform-origin: center; }

.section-title {
  margin: var(--space-3) 0 var(--space-1) 0;
  font-family: var(--font-serif);
  font-size: var(--text-h3);
  color: var(--color-fg);
  font-weight: var(--weight-semibold);
}

.compare-row {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2);
  background: var(--color-bg-soft);
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border);
}
.compare-side {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: var(--space-2);
  border-radius: var(--radius-sm);
}
.a-side { background: var(--color-bg); border: 1px solid var(--color-border); }
.b-side { background: var(--color-bg); border: 1px solid var(--color-border); }
.phase-label {
  font-family: var(--font-sans);
  font-size: var(--text-small);
  color: var(--color-fg-3);
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.phase-label-name {
  font-family: var(--font-serif);
  font-size: var(--text-h3);
  color: var(--color-fg);
  font-weight: var(--weight-semibold);
}
.phase-score {
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
  color: var(--color-accent);
  font-size: var(--text-h3);
  font-weight: var(--weight-medium);
}
.arrow-icon {
  font-size: 28px;
  color: var(--color-accent);
}
.dim { color: var(--color-fg-3); }
</style>
