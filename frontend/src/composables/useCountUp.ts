/**
 * useCountUp - Ref 数字动画
 * ====================
 *
 * 行为: 监听 target Ref 变化,以 easeOutCubic 缓动到目标值,持续 duration 秒。
 * 不依赖 GSAP,纯 requestAnimationFrame 实现,组件卸载自动 stop。
 *
 * 用法:
 *   const target = ref(0)
 *   const display = useCountUp(target, 0.6)
 *   target.value = 95.42
 *   // display 会在 0.6s 内从 0 渐变到 95.42
 *
 * 注意:
 *   - prefers-reduced-motion 时直接同步赋值,跳过动画
 *   - 目标非数字会被忽略
 */
import { ref, watch, onUnmounted, type Ref } from 'vue'

/** easeOutCubic: 起手快,后段减速,符合数字"落定"感 */
function easeOutCubic(t: number) {
  return 1 - Math.pow(1 - t, 3)
}

/** 减弱动效偏好检测 */
function prefersReducedMotion(): boolean {
  if (typeof window === 'undefined') return false
  return window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
}

export function useCountUp(
  target: Ref<number>,
  duration = 0.6,
): Ref<number> {
  const display = ref(target.value)
  let rafId: number | null = null
  let startVal = target.value
  let startTime = 0

  const cancel = () => {
    if (rafId !== null) {
      cancelAnimationFrame(rafId)
      rafId = null
    }
  }

  const animate = (endVal: number) => {
    cancel()
    if (prefersReducedMotion() || duration <= 0) {
      display.value = endVal
      return
    }
    startVal = display.value
    startTime = performance.now()
    const step = (now: number) => {
      const elapsed = (now - startTime) / 1000
      const t = Math.min(elapsed / duration, 1)
      display.value = startVal + (endVal - startVal) * easeOutCubic(t)
      if (t < 1) {
        rafId = requestAnimationFrame(step)
      } else {
        rafId = null
      }
    }
    rafId = requestAnimationFrame(step)
  }

  watch(target, (v) => {
    if (typeof v !== 'number' || Number.isNaN(v)) return
    animate(v)
  })

  onUnmounted(cancel)

  return display
}
