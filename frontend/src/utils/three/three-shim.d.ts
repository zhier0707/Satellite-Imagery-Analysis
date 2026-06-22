/**
 * three 包类型 shim（仅类型，不含运行时）
 * ====================
 *
 * 设计动机:
 *   - 项目声明了 `three` 与 `@types/three` 作为依赖，但本会话内未执行 npm install
 *   - vue-tsc 在找不到 `three` 模块时会让 BigScreenView / EarthScene 全部报错
 *   - 本文件用 ambient module 声明，为我们实际使用的 API 提供最小类型
 *   - 运行时由 vite 自动按需从 npm 解析（用户执行 npm install 后即可工作）
 *
 * 维护原则:
 *   - 只声明本项目实际 import 的 API，不要追求覆盖整个 @types/three
 *   - 新增 three API 时，先在这里加类型，再在业务代码中引用
 */
declare module 'three' {
  // ==================== 基础类型 ====================
  export class Color {
    constructor(n?: number | string)
    r: number
    g: number
    b: number
  }
  export class Vector3 {
    constructor(x?: number, y?: number, z?: number)
    x: number
    y: number
    z: number
    set(x: number, y: number, z: number): this
    copy(v: Vector3): this
    clone(): Vector3
    multiplyScalar(s: number): this
    normalize(): this
  }

  // ==================== 几何 ====================
  export class BufferGeometry {
    setAttribute(name: string, attribute: BufferAttribute): this
    dispose(): void
  }
  export class BufferAttribute {
    constructor(array: ArrayLike<number>, itemSize: number)
  }
  export class SphereGeometry {
    constructor(radius?: number, widthSegments?: number, heightSegments?: number)
  }
  export class RingGeometry {
    constructor(innerRadius: number, outerRadius: number, thetaSegments?: number)
  }

  // ==================== 材质 ====================
  export class Material {
    transparent: boolean
    opacity: number
    dispose(): void
  }
  export class MeshPhongMaterial {
    constructor(params?: { map?: Texture; shininess?: number })
  }
  export class MeshBasicMaterial {
    constructor(params?: {
      color?: number
      side?: number
      transparent?: boolean
      opacity?: number
    })
  }
  export class MeshLambertMaterial {
    constructor(params?: {
      map?: Texture
      transparent?: boolean
      opacity?: number
      depthWrite?: boolean
    })
  }
  export class ShaderMaterial {
    constructor(params?: {
      uniforms?: Record<string, unknown>
      vertexShader?: string
      fragmentShader?: string
      side?: number
      transparent?: boolean
      blending?: number
      depthWrite?: boolean
    })
    uniforms: Record<string, { value: unknown }>
    dispose(): void
  }
  export class PointsMaterial {
    constructor(params?: {
      color?: number
      size?: number
      sizeAttenuation?: boolean
      vertexColors?: boolean
      transparent?: boolean
      opacity?: number
    })
    transparent: boolean
    opacity: number
    size: number
    dispose(): void
  }

  // ==================== 纹理 ====================
  export class Texture {
    colorSpace: string
    needsUpdate: boolean
  }
  export class CanvasTexture {
    constructor(canvas: HTMLCanvasElement)
    colorSpace: string
    needsUpdate: boolean
  }

  // ==================== 光源 ====================
  export class AmbientLight {
    constructor(color?: number, intensity?: number)
  }
  export class DirectionalLight {
    constructor(color?: number, intensity?: number)
    position: Vector3
  }

  // ==================== 场景与渲染 ====================
  export class Scene {
    constructor()
    add(obj: unknown): this
    remove(obj: unknown): this
    traverse(fn: (obj: Object3D) => void): void
  }
  export class PerspectiveCamera {
    constructor(fov: number, aspect: number, near: number, far: number)
    position: Vector3
    aspect: number
    lookAt(x: number, y: number, z: number): void
    updateProjectionMatrix(): void
  }
  export class WebGLRenderer {
    constructor(params?: { antialias?: boolean; alpha?: boolean })
    domElement: HTMLCanvasElement
    setSize(w: number, h: number): void
    setPixelRatio(r: number): void
    render(scene: Scene, camera: PerspectiveCamera): void
    dispose(): void
  }

  // ==================== 物体基类 ====================
  export class Object3D {
    rotation: { x: number; y: number; z: number }
    position: Vector3
    userData: Record<string, unknown>
  }
  export class Mesh extends Object3D {
    constructor(geometry?: unknown, material?: unknown)
    geometry: { dispose: () => void }
    material: Material | Material[]
  }
  export class Points extends Object3D {
    constructor(geometry?: BufferGeometry, material?: PointsMaterial | ShaderMaterial)
    geometry: BufferGeometry
    material: PointsMaterial | ShaderMaterial
  }

  // ==================== 常量 ====================
  export const BackSide: number
  export const DoubleSide: number
  export const AdditiveBlending: number
  export const SRGBColorSpace: string
}
