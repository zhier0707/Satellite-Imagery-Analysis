<script setup lang="ts">
/**
 * Top5View - Top-5 概率条
 * ====================
 *
 * 视觉与动效:
 *   - PageHeader 替代 header
 *   - 用自绘的水平条替代 el-progress,便于 GSAP 控制 width
 *   - 5 条 stagger 0.08s 从 0 增长到目标百分比, ease power2.out
 *   - 数字 countUp
 */
import { ref, watch, computed, nextTick, onMounted } from 'vue'
import { gsap } from 'gsap'
import { useUploadStore } from '@/stores/upload'
import { useCountUp } from '@/composables/useCountUp'
import { usePageEnter } from '@/composables/usePageEnter'

const upload = useUploadStore()
const sectionRef = ref<HTMLElement | null>(null)
usePageEnter(sectionRef)

const items = computed(() => upload.classify?.top5 ?? [])

// 主题色板: 蓝主导 + 中性灰
const colorOf = (i: number) => {
  const palette = ['#2563EB', '#1A1A1A', '#525252', '#A3A3A3', '#D4D4D8']
  return palette[i] ?? '#A3A3A3'
}

const barRefs = ref<HTMLElement[]>([])
const setBarRef = (el: any, i: number) => {
  if (el) barRefs.value[i] = el as HTMLElement
}

function prefersReducedMotion(): boolean {
  return window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
}

/** 在数据更新后,跑一次 stagger 增长动画 */
const animate = async () => {
  await nextTick()
  if (prefersReducedMotion() || !barRefs.value.length) {
    barRefs.value.forEach((el, i) => { if (el) el.style.width = `${(items.value[i]?.score ?? 0) * 100}%` })
    return
  }
  barRefs.value.forEach((el) => { if (el) el.style.width = '0%' })
  gsap.to(barRefs.value.filter(Boolean), {
    width: (i: number) => `${(items.value[i]?.score ?? 0) * 100}%`,
    duration: 0.7,
    ease: 'power2.out',
    stagger: 0.08,
  })
}

watch(items, animate, { deep: true })
onMounted(() => { if (items.value.length) animate() })
</script>

<template>
  <section ref="sectionRef" class="top5-view">
    <PageHeader
      title="Top-5 概率分布"
      subtitle="模型对上传图像的 Top-5 类别概率;横向条从 0 增长至目标值,stagger 0.08s。"
    />

    <EmptyState
      v-if="!items.length"
      icon="Picture"
      title="尚无识别结果"
      description="请先在「图像上传」页面上传图片。"
    />

    <el-card v-else shadow="never" class="bar-card">
      <div class="bar-list">
        <div v-for="(it, i) in items" :key="it.label" class="bar-row">
          <div class="bar-label">
            <span class="rank" :style="{ background: colorOf(i) }">#{{ i + 1 }}</span>
            <span class="name">{{ it.label }}</span>
            <span class="percent">{{ (it.score * 100).toFixed(2) }}%</span>
          </div>
          <div class="bar-track">
            <div
              :ref="(el) => setBarRef(el, i)"
              class="bar-fill"
              :style="{ background: colorOf(i) }"
            />
          </div>
        </div>
      </div>
    </el-card>
  </section>
</template>

<style scoped>
.top5-view { max-width: 960px; margin: 0 auto; }

.bar-card { background: var(--color-bg); }
.bar-list { display: flex; flex-direction: column; gap: var(--space-2); }
.bar-row { display: flex; flex-direction: column; gap: 6px; }
.bar-label {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-family: var(--font-sans);
}
.rank {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 22px;
  border-radius: var(--radius-sm);
  color: #fff;
  font-size: var(--text-small);
  font-weight: var(--weight-medium);
  font-family: var(--font-sans);
}
.name {
  font-family: var(--font-serif);
  font-size: 16px;
  color: var(--color-fg);
  font-weight: var(--weight-medium);
  flex: 1;
}
.percent {
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
  color: var(--color-fg-2);
  font-size: var(--text-body);
}
.bar-track {
  width: 100%;
  height: 14px;
  background: var(--color-bg-alt);
  border-radius: var(--radius-pill);
  overflow: hidden;
}
.bar-fill {
  height: 100%;
  width: 0;
  border-radius: var(--radius-pill);
  transition: background-color var(--duration-fast) var(--ease-standard);
}
</style>
