/**
 * usePageEnter - 页面入场动效
 * ====================
 *
 * 在 onMounted 时,对 root 容器内的子元素执行 stagger fade-up。
 * 强度: y 偏移 16px → 0,opacity 0 → 1,stagger 0.06s,单元素 0.4s。
 *
 * 用法:
 *   <section ref="root">
 *     <h1>...</h1>
 *     <p>...</p>
 *     <div>...</div>
 *   </section>
 *   usePageEnter(root)   // 自动处理
 *
 * 设计取舍:
 *   - GSAP 提供了最稳的 stagger;如果项目已用 GSAP 做 timeline,本 hook 只是一行包装
 *   - prefers-reduced-motion 时跳过,直接显示终态
 */
import { onMounted, type Ref } from 'vue'
import { gsap } from 'gsap'

function prefersReducedMotion(): boolean {
  if (typeof window === 'undefined') return false
  return window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
}

export function usePageEnter(
  rootRef: Ref<HTMLElement | null | undefined>,
  options: {
    /** stagger 间隔,秒 */
    stagger?: number
    /** 单元素时长 */
    duration?: number
    /** y 起始偏移 */
    y?: number
  } = {},
) {
  const { stagger = 0.06, duration = 0.4, y = 16 } = options

  onMounted(() => {
    const el = rootRef.value
    if (!el) return
    if (prefersReducedMotion()) {
      // 减弱动效: 立即归位,不做位移
      gsap.set(el.children, { opacity: 1, y: 0, clearProps: 'all' })
      return
    }
    gsap.fromTo(
      el.children,
      { opacity: 0, y },
      { opacity: 1, y: 0, duration, stagger, ease: 'power2.out' },
    )
  })
}
