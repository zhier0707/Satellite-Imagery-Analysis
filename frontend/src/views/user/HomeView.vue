<script setup lang="ts">
/**
 * HomeView - 用户端首页 Dashboard（项目价值主张）
 * ====================
 *
 * 设计目标:
 *   - 一屏时间传达"项目是什么 / 5 个核心能力 / 怎么开始"
 *   - 衬线大字 H1 + 副标题 + 2 个 CTA
 *   - 2x2 + 1 特性卡片网格，第 5 张"3D 数据驾驶舱"为推荐
 *   - GSAP stagger fade-up 入场
 *   - 底部数据来源区（学术可追溯）
 *
 * 视觉规范:
 *   - 白底 + 衬线大字 + 蓝色 (#2563EB) 强调，与现有 11 视图一致
 *   - 使用 el-button / el-card / el-icon
 */
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { gsap } from 'gsap'
import {
  Grid,
  Aim,
  Clock,
  MapLocation,
  DataLine,
  ArrowRight,
  Position,
} from '@element-plus/icons-vue'

const router = useRouter()
const heroRef = ref<HTMLElement | null>(null)
const cardsRef = ref<HTMLElement | null>(null)

function prefersReducedMotion(): boolean {
  return window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
}

// ==================== 特性卡片数据 ====================
interface FeatureCard {
  title: string
  desc: string
  icon: any
  to: string
  recommended?: boolean
  linkLabel: string
}

const features: FeatureCard[] = [
  {
    title: '10 类精细分类',
    desc: '基于 EuroSAT 数据集训练的 EfficientNetV2-M 模型，秒级返回土地利用分类',
    icon: Grid,
    to: '/app/upload',
    linkLabel: '上传图像',
  },
  {
    title: 'Grad-CAM 可解释 AI',
    desc: '每个分类都附带热力图，告诉你模型在原图上关注了哪些像素',
    icon: Aim,
    to: '/app/heatmap',
    linkLabel: '查看热力图',
  },
  {
    title: '时相对比',
    desc: '同区域两期影像自动对比，发现新增 / 消失 / 类别变化区域',
    icon: Clock,
    to: '/app/change',
    linkLabel: '时相分析',
  },
  {
    title: '高德地理可视化',
    desc: '分类结果上高德卫星地图，看点位分布与边界多边形',
    icon: MapLocation,
    to: '/app/map',
    linkLabel: '打开地图',
  },
  {
    title: '3D 数据驾驶舱',
    desc: '路演 / 学术报告 / 团队周会专用大屏：3D 地球 + 实时 KPI',
    icon: DataLine,
    to: '/app/screen',
    linkLabel: '进入大屏',
    recommended: true,
  },
]

// ==================== 入场动效 ====================
onMounted(() => {
  if (prefersReducedMotion()) return

  // Hero 区 fade-up
  if (heroRef.value) {
    gsap.fromTo(
      heroRef.value.children,
      { opacity: 0, y: 24 },
      { opacity: 1, y: 0, duration: 0.6, stagger: 0.08, ease: 'power2.out' },
    )
  }
  // 卡片 stagger（0.06s 间隔）
  if (cardsRef.value) {
    const cards = cardsRef.value.querySelectorAll('.feature-card')
    gsap.fromTo(
      cards,
      { opacity: 0, y: 20 },
      { opacity: 1, y: 0, duration: 0.5, stagger: 0.06, ease: 'power2.out', delay: 0.25 },
    )
  }
})

const goTo = (path: string) => router.push(path)
</script>

<template>
  <section class="home-view">
    <!-- ============ Hero ============ -->
    <div ref="heroRef" class="hero">
      <p class="kicker">SATELLITE · REMOTE SENSING</p>
      <h1 class="display">卫星图像分析平台</h1>
      <p class="lede">
        用深度学习解译卫星图像，从欧空局 Sentinel-2 影像到土地利用分类、热力图、时相变化一站直达。
      </p>
      <div class="cta-row">
        <el-button class="is-accent cta-primary" size="large" @click="goTo('/app/upload')">
          <el-icon><Position /></el-icon>
          快速开始
        </el-button>
        <el-button size="large" @click="goTo('/app/map')">
          <el-icon><MapLocation /></el-icon>
          查看地图
        </el-button>
      </div>
    </div>

    <!-- ============ 特性卡片网格 ============ -->
    <div ref="cardsRef" class="feature-grid">
      <el-card
        v-for="f in features"
        :key="f.title"
        class="feature-card"
        :class="{ 'feature-card--recommended': f.recommended }"
        shadow="never"
        @click="goTo(f.to)"
      >
        <div v-if="f.recommended" class="ribbon">推荐</div>
        <div class="feature-icon">
          <el-icon :size="28"><component :is="f.icon" /></el-icon>
        </div>
        <h3 class="feature-title">{{ f.title }}</h3>
        <p class="feature-desc">{{ f.desc }}</p>
        <div class="feature-link">
          <span>{{ f.linkLabel }}</span>
          <el-icon class="link-arrow"><ArrowRight /></el-icon>
        </div>
      </el-card>
    </div>

    <!-- ============ 数据来源 ============ -->
    <footer class="source">
      <p class="source-title">数据来源</p>
      <p class="source-list">
        欧空局 Copernicus 计划 · EuroSAT 数据集 · EfficientNetV2-M · timm 库 · 高德开放平台
      </p>
    </footer>
  </section>
</template>

<style scoped>
/* ==================== 容器 ==================== */
.home-view {
  max-width: 1180px;
  margin: 0 auto;
  padding: var(--space-4) 0;
}

/* ==================== Hero ==================== */
.hero {
  padding: var(--space-5) 0 var(--space-4);
  text-align: left;
}
.kicker {
  font-family: var(--font-sans);
  font-size: var(--text-small);
  letter-spacing: 0.18em;
  color: var(--color-accent);
  text-transform: uppercase;
  margin: 0 0 var(--space-2) 0;
  font-weight: var(--weight-medium);
}
.display {
  font-family: var(--font-serif);
  font-size: var(--text-display);
  line-height: 1.1;
  color: var(--color-fg);
  font-weight: var(--weight-semibold);
  letter-spacing: -0.02em;
  margin: 0;
}
.lede {
  margin: var(--space-2) 0 0 0;
  color: var(--color-fg-2);
  font-size: 16px;
  line-height: var(--line-loose);
  max-width: 720px;
}
.cta-row {
  margin-top: var(--space-3);
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
}
.cta-primary {
  font-weight: var(--weight-medium);
}

/* ==================== 特性卡片网格 2x2+1 ==================== */
.feature-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-3);
  margin-top: var(--space-4);
}
/* 第 5 张占满整行 */
.feature-card:last-child {
  grid-column: 1 / -1;
}
.feature-card {
  position: relative;
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: transform var(--duration-base) var(--ease-standard),
    box-shadow var(--duration-base) var(--ease-standard),
    border-color var(--duration-base) var(--ease-standard);
  padding: var(--space-3);
}
.feature-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-2);
  border-color: var(--color-accent);
}
.feature-card--recommended {
  background: linear-gradient(135deg, #F0F5FF 0%, #FFFFFF 70%);
  border-color: var(--color-accent);
}
.feature-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 48px;
  height: 48px;
  border-radius: var(--radius-sm);
  background: var(--color-accent-soft);
  color: var(--color-accent);
  margin-bottom: var(--space-2);
}
.feature-title {
  font-family: var(--font-serif);
  font-size: var(--text-h2);
  font-weight: var(--weight-semibold);
  color: var(--color-fg);
  margin: 0 0 var(--space-1) 0;
}
.feature-desc {
  color: var(--color-fg-2);
  font-size: var(--text-body);
  line-height: var(--line-base);
  margin: 0 0 var(--space-2) 0;
  min-height: 44px;
}
.feature-link {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: var(--color-accent);
  font-size: var(--text-body);
  font-weight: var(--weight-medium);
  margin-top: auto;
}
.link-arrow {
  transition: transform var(--duration-fast) var(--ease-standard);
}
.feature-card:hover .link-arrow {
  transform: translateX(4px);
}

/* ==================== 推荐角标 ==================== */
.ribbon {
  position: absolute;
  top: 14px;
  right: 14px;
  background: var(--color-danger);
  color: #fff;
  font-size: 11px;
  font-weight: var(--weight-semibold);
  letter-spacing: 0.05em;
  padding: 3px 10px;
  border-radius: var(--radius-pill);
  box-shadow: 0 2px 6px rgba(220, 38, 38, 0.3);
}

/* ==================== 数据来源 ==================== */
.source {
  margin-top: var(--space-5);
  padding: var(--space-3) 0;
  border-top: 1px solid var(--color-border);
  text-align: center;
}
.source-title {
  font-family: var(--font-sans);
  font-size: var(--text-small);
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--color-fg-3);
  margin: 0 0 var(--space-1) 0;
  font-weight: var(--weight-medium);
}
.source-list {
  color: var(--color-fg-2);
  font-size: var(--text-small);
  font-family: var(--font-sans);
}

/* ==================== 响应式 ==================== */
@media (max-width: 720px) {
  .feature-grid { grid-template-columns: 1fr; }
  .feature-card:last-child { grid-column: 1; }
  .display { font-size: 36px; }
}
</style>
