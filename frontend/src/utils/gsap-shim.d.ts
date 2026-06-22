/**
 * gsap 包类型 shim（仅类型，不含运行时）
 * ====================
 *
 * 设计动机:
 *   - 项目声明了 `gsap` 作为依赖，但 node_modules 中未实际安装
 *   - vue-tsc 在找不到 `gsap` 模块时让所有 import 文件报错
 *   - 本文件用 ambient module 声明，为实际使用的 API 提供最小类型
 *   - 运行时由 vite 自动按需从 npm 解析
 *
 * 维护原则:
 *   - 只声明本项目实际 import 的 API
 *   - 新增 gsap API 时，先在这里加类型，再在业务代码中引用
 */
declare module 'gsap' {
  // ==================== 缓动函数 ====================
  type EaseFunction = string | ((t: number) => number)
  type Vars = Record<string, unknown>
  type Targets = Element | Element[] | string | object | object[] | null

  /** gsap.fromTo() 与 gsap.to() 的目标对象 */
  interface TweenTarget extends Vars {
    opacity?: number
    y?: number
    x?: number
    scale?: number
    rotation?: number
    duration?: number
    delay?: number
    ease?: string
    stagger?: number
    onComplete?: () => void
  }

  export const gsap: {
    /** 动画到目标状态 */
    to(targets: Targets, vars: TweenTarget, position?: number | string): unknown
    /** 从目标状态动画到当前状态 */
    from(targets: Targets, vars: TweenTarget, position?: number | string): unknown
    /** 从 from 状态动画到 to 状态 */
    fromTo(
      targets: Targets,
      fromVars: TweenTarget,
      toVars: TweenTarget,
      position?: number | string,
    ): unknown
    /** 设置立即状态，无动画 */
    set(targets: Targets, vars: TweenTarget): unknown
    /** 创建时间线 */
    timeline(vars?: { defaults?: TweenTarget }): {
      to(targets: Targets, vars: TweenTarget, position?: number | string): unknown
      from(targets: Targets, vars: TweenTarget, position?: number | string): unknown
      fromTo(
        targets: Targets,
        fromVars: TweenTarget,
        toVars: TweenTarget,
        position?: number | string,
      ): unknown
      /** 在时间线某点插入回调 */
      add(callback: () => void, position?: number | string): unknown
      play(): unknown
      pause(): unknown
      kill(): unknown
    }
    /** 注册特效/插件 */
    registerPlugin(...plugins: unknown[]): void
  }
}
