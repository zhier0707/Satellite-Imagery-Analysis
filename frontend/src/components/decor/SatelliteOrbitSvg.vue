<script setup lang="ts">
/**
 * SatelliteOrbitSvg - 装饰用 SVG
 * ====================
 *
 * 用纯 SVG + CSS 动画绘制"地球 + 卫星轨道 + 雷达扫描"。
 * 不依赖任何第三方图片/Canvas;遵循 algorithmic-art 思路:
 *   - 地球: 渐变球体 + 经纬网格
 *   - 3 条椭圆轨道: 不同倾角,反向旋转
 *   - 卫星: 沿轨道公转的 3 颗小方块
 *   - 雷达扫描: 半透明扇形 sweep
 *
 * props.height 控制整体高度(宽度自动 100%)。
 * prefers-reduced-motion 时所有 CSS 动画 stop,扇形停留在 0deg。
 */
import { computed } from 'vue'

interface Props {
  height?: number | string
  /** 是否开启动画(受 reduced-motion 偏好影响) */
  animated?: boolean
}
const props = withDefaults(defineProps<Props>(), {
  height: '100%',
  animated: true,
})

const styleHeight = computed(() =>
  typeof props.height === 'number' ? `${props.height}px` : props.height,
)
</script>

<template>
  <div class="orbit-stage" :style="{ height: styleHeight }" :class="{ 'is-static': !props.animated }">
    <svg
      viewBox="0 0 600 600"
      preserveAspectRatio="xMidYMid meet"
      xmlns="http://www.w3.org/2000/svg"
      role="img"
      aria-label="卫星轨道示意图"
    >
      <defs>
        <!-- 地球径向渐变 -->
        <radialGradient id="earth" cx="40%" cy="40%" r="60%">
          <stop offset="0%" stop-color="#DBE7FF" />
          <stop offset="55%" stop-color="#2563EB" stop-opacity="0.65" />
          <stop offset="100%" stop-color="#1D4FD8" stop-opacity="0.9" />
        </radialGradient>
        <!-- 雷达扫描扇形 -->
        <linearGradient id="radar" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stop-color="#2563EB" stop-opacity="0" />
          <stop offset="100%" stop-color="#2563EB" stop-opacity="0.35" />
        </linearGradient>
        <!-- 背景星点 -->
        <pattern id="stars" width="40" height="40" patternUnits="userSpaceOnUse">
          <circle cx="6" cy="10" r="0.7" fill="#A3A3A3" />
          <circle cx="22" cy="28" r="0.5" fill="#525252" />
          <circle cx="34" cy="6" r="0.4" fill="#1A1A1A" />
          <circle cx="14" cy="34" r="0.6" fill="#A3A3A3" />
        </pattern>
      </defs>

      <!-- 星点背景 -->
      <rect width="600" height="600" fill="url(#stars)" />

      <!-- 雷达扫描层 -->
      <g transform="translate(300 300)">
        <g class="radar-sweep">
          <path d="M0,0 L260,0 A260,260 0 0,0 184,-184 Z" fill="url(#radar)" />
        </g>
      </g>

      <!-- 3 条轨道 (不同倾角) -->
      <g transform="translate(300 300)" fill="none" stroke-width="1">
        <g class="orbit orbit-1">
          <ellipse cx="0" cy="0" rx="220" ry="80" stroke="#2563EB" stroke-opacity="0.5" />
        </g>
        <g class="orbit orbit-2" transform="rotate(35)">
          <ellipse cx="0" cy="0" rx="240" ry="100" stroke="#1A1A1A" stroke-opacity="0.35" />
        </g>
        <g class="orbit orbit-3" transform="rotate(-25)">
          <ellipse cx="0" cy="0" rx="200" ry="120" stroke="#525252" stroke-opacity="0.3" />
        </g>
      </g>

      <!-- 地球 -->
      <g transform="translate(300 300)">
        <circle r="110" fill="url(#earth)" />
        <!-- 经纬网格 -->
        <g stroke="#FFFFFF" stroke-opacity="0.25" fill="none" stroke-width="0.6">
          <ellipse rx="110" ry="40" />
          <ellipse rx="110" ry="70" />
          <ellipse rx="40" ry="110" />
          <ellipse rx="70" ry="110" />
          <line x1="-110" x2="110" />
          <line y1="-110" y2="110" />
        </g>
        <!-- 极地小高光 -->
        <circle r="110" fill="none" stroke="#FFFFFF" stroke-opacity="0.4" stroke-width="0.8" />
      </g>

      <!-- 卫星 (沿 3 条轨道公转) -->
      <g class="satellite satellite-1">
        <g transform="translate(300 300)">
          <g class="orbit-spin-1">
            <g transform="translate(220 0)">
              <rect x="-4" y="-3" width="8" height="6" fill="#1A1A1A" />
              <line x1="-10" y1="0" x2="-4" y2="0" stroke="#1A1A1A" stroke-width="1.2" />
              <line x1="4" y1="0" x2="10" y2="0" stroke="#1A1A1A" stroke-width="1.2" />
            </g>
          </g>
        </g>
      </g>

      <g class="satellite satellite-2">
        <g transform="translate(300 300) rotate(35)">
          <g class="orbit-spin-2">
            <g transform="translate(240 0)">
              <rect x="-3.5" y="-2.5" width="7" height="5" fill="#2563EB" />
            </g>
          </g>
        </g>
      </g>

      <g class="satellite satellite-3">
        <g transform="translate(300 300) rotate(-25)">
          <g class="orbit-spin-3">
            <g transform="translate(200 0)">
              <rect x="-3.5" y="-2.5" width="7" height="5" fill="#525252" />
            </g>
          </g>
        </g>
      </g>
    </svg>
  </div>
</template>

<style scoped>
.orbit-stage {
  position: relative;
  width: 100%;
  background: var(--color-bg);
  overflow: hidden;
}
.orbit-stage svg { width: 100%; height: 100%; display: block; }

/* ===== 动画 ===== */
.radar-sweep {
  transform-origin: 0 0;
  animation: radar-spin 4.5s linear infinite;
}
.orbit-1 { animation: orbit-counter 28s linear infinite; transform-origin: 300px 300px; }
.orbit-2 { animation: orbit-spin 36s linear infinite; transform-origin: 300px 300px; }
.orbit-3 { animation: orbit-counter 42s linear infinite; transform-origin: 300px 300px; }
.orbit-spin-1 { animation: orbit-spin 14s linear infinite; transform-origin: 0 0; }
.orbit-spin-2 { animation: orbit-counter 18s linear infinite; transform-origin: 0 0; }
.orbit-spin-3 { animation: orbit-spin 22s linear infinite; transform-origin: 0 0; }

@keyframes radar-spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
@keyframes orbit-spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
@keyframes orbit-counter {
  from { transform: rotate(0deg); }
  to { transform: rotate(-360deg); }
}

/* ===== 减弱动效 ===== */
.is-static .radar-sweep,
.is-static .orbit-1,
.is-static .orbit-2,
.is-static .orbit-3,
.is-static .orbit-spin-1,
.is-static .orbit-spin-2,
.is-static .orbit-spin-3 {
  animation: none !important;
}
@media (prefers-reduced-motion: reduce) {
  .radar-sweep,
  .orbit-1, .orbit-2, .orbit-3,
  .orbit-spin-1, .orbit-spin-2, .orbit-spin-3 {
    animation: none !important;
  }
}
</style>
