/**
 * EarthScene - 3D 大屏地球场景封装
 * ====================
 *
 * 职责:
 *   - 构造时一次性创建 Scene / Camera / Renderer / Lights
 *   - 公开 addEarth / addClouds / addGlow / addAtmosphere / addStars / addOrbit / addPointCloud
 *   - 启动 startRotation 后,requestAnimationFrame 持续渲染
 *   - dispose 时释放 GPU 资源 + DOM 节点
 *
 * 设计原则:
 *   - 单一职责:本类不感知 Vue / ECharts / KPI 业务
 *   - 状态只走类成员,无全局副作用(可同时实例化多个)
 *   - 点云呼吸是物理动效,业务侧只需传 baseSize,scene 内部自己驱动
 *
 * 坐标公式:
 *   - 经纬度 → 3D 球面坐标 与 colors.ts 中 latLngToVec3 保持一致
 *   - latLngToVec3 在 colors.ts 中已经过单元测试验证
 */
import * as THREE from 'three'
import { latLngToVec3 } from './colors'

/** 点云项业务类型:由大屏的 top_locations 派生 */
export interface EarthPointItem {
  lng: number
  lat: number
  /** 10 类土地利用标签,用于上色 */
  label: string
  /** 该点与上次相比的"差异量",用于呼吸相位 */
  offset: number
  /** 16 进制颜色 - 由调用方按 label 映射 LABEL_COLORS 得到 */
  color: number
}

/** shader uniforms 的类型,避免 unknown 满天飞 */
interface StarShaderMaterial extends THREE.ShaderMaterial {
  uniforms: {
    time: { value: number }
    baseSize: { value: number }
  }
}

export class EarthScene {
  scene: THREE.Scene
  camera: THREE.PerspectiveCamera
  renderer: THREE.WebGLRenderer
  earth: THREE.Mesh | null = null
  private container: HTMLElement
  private points: THREE.Points | null = null
  private clouds: THREE.Mesh | null = null
  private glow: THREE.Mesh | null = null
  private stars: THREE.Points | null = null
  private starsMaterial: StarShaderMaterial | null = null
  private basePointSize: number = 6
  private autoRotate: boolean = true
  private rotationSpeed: number = 0.05
  private time: number = 0
  private animationId: number = 0

  constructor(container: HTMLElement) {
    this.container = container
    this.scene = new THREE.Scene()

    // 相机: 45° FOV / 0.1~1000 远裁 / 初始 (0, 30, 100) 俯视
    this.camera = new THREE.PerspectiveCamera(
      45,
      container.clientWidth / container.clientHeight,
      0.1,
      1000,
    )
    this.camera.position.set(0, 30, 100)
    this.camera.lookAt(0, 0, 0)

    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
    this.renderer.setSize(container.clientWidth, container.clientHeight)
    this.renderer.setPixelRatio(window.devicePixelRatio)
    container.appendChild(this.renderer.domElement)

    // 环境光 + 平行光:让地球明暗立体
    this.scene.add(new THREE.AmbientLight(0xffffff, 0.4))
    const dirLight = new THREE.DirectionalLight(0xffffff, 0.7)
    dirLight.position.set(50, 50, 50)
    this.scene.add(dirLight)

    // 响应式
    window.addEventListener('resize', this.handleResize)
  }

  // ==================== 地球本体 ====================
  addEarth(texture: THREE.Texture): void {
    const geometry = new THREE.SphereGeometry(50, 64, 64)
    const material = new THREE.MeshPhongMaterial({ map: texture, shininess: 8 })
    this.earth = new THREE.Mesh(geometry, material)
    this.scene.add(this.earth)
  }

  // ==================== 云层(半透明球壳) ====================
  /**
   * 在地球外侧加一层半透明白噪声云,稍大于地球避免 z-fighting
   * @param texture  createCloudTexture() 生成的云图
   */
  addClouds(texture: THREE.Texture): void {
    // 释放旧云层(重复调用时)
    if (this.clouds) {
      this.scene.remove(this.clouds)
      this.clouds.geometry.dispose()
      ;(this.clouds.material as THREE.Material).dispose()
      this.clouds = null
    }
    const geometry = new THREE.SphereGeometry(50.5, 64, 64)
    const material = new THREE.MeshLambertMaterial({
      map: texture,
      transparent: true,
      opacity: 0.55,
      depthWrite: false,
    })
    this.clouds = new THREE.Mesh(geometry, material)
    this.scene.add(this.clouds)
  }

  // ==================== 大气光晕(Fresnel shader) ====================
  /**
   * 在最外层加一个 Fresnel shader 大气光晕,产生"行星辉光"效果
   * 多次调用会先释放旧 glow
   */
  addGlow(): void {
    if (this.glow) {
      this.scene.remove(this.glow)
      this.glow.geometry.dispose()
      ;(this.glow.material as THREE.Material).dispose()
      this.glow = null
    }
    const geometry = new THREE.SphereGeometry(60, 64, 64)
    const material = new THREE.ShaderMaterial({
      uniforms: {
        glowColor: { value: new THREE.Color(0x4FC3F7) },
      },
      vertexShader: /* glsl */ `
        varying vec3 vNormal;
        varying vec3 vViewDir;
        void main() {
          vec4 mvPos = modelViewMatrix * vec4(position, 1.0);
          vNormal = normalize(normalMatrix * normal);
          vViewDir = normalize(-mvPos.xyz);
          gl_Position = projectionMatrix * mvPos;
        }
      `,
      fragmentShader: /* glsl */ `
        uniform vec3 glowColor;
        varying vec3 vNormal;
        varying vec3 vViewDir;
        void main() {
          // Fresnel: 边缘强、中心弱
          float fresnel = pow(1.0 - max(dot(vNormal, vViewDir), 0.0), 2.5);
          gl_FragColor = vec4(glowColor, fresnel * 0.75);
        }
      `,
      side: THREE.BackSide,
      transparent: true,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    })
    this.glow = new THREE.Mesh(geometry, material)
    this.scene.add(this.glow)
  }

  // ==================== 兼容老接口的薄大气层(保留) ====================
  addAtmosphere(): void {
    const geometry = new THREE.SphereGeometry(52, 64, 64)
    const material = new THREE.MeshBasicMaterial({
      color: 0x4FC3F7,
      side: THREE.BackSide,
      transparent: true,
      opacity: 0.15,
    })
    this.scene.add(new THREE.Mesh(geometry, material))
  }

  // ==================== 3 条卫星轨道环 ====================
  addOrbit(): void {
    const colors = [0x00E5FF, 0x10F2C5, 0xFF6B6B]
    for (let i = 0; i < 3; i++) {
      const geometry = new THREE.RingGeometry(60 + i * 5, 60 + i * 5 + 0.3, 64)
      const material = new THREE.MeshBasicMaterial({
        color: colors[i],
        side: THREE.DoubleSide,
        transparent: true,
        opacity: 0.4,
      })
      const ring = new THREE.Mesh(geometry, material)
      ring.rotation.x = Math.PI / 2 + (i - 1) * 0.3
      ring.rotation.z = (i - 1) * 0.5
      this.scene.add(ring)
    }
  }

  // ==================== 星空背景(带 Twinkle 闪烁) ====================
  /**
   * 用 ShaderMaterial 给每颗星一个独立相位,实现非同步闪烁。
   * 多次调用会先释放旧 stars
   */
  addStars(count: number = 1000): void {
    if (this.stars) {
      this.scene.remove(this.stars)
      this.stars.geometry.dispose()
      ;(this.stars.material as THREE.Material).dispose()
      this.stars = null
      this.starsMaterial = null
    }
    const positions = new Float32Array(count * 3)
    const phases = new Float32Array(count)
    for (let i = 0; i < count; i++) {
      const r = 300 + Math.random() * 200
      const theta = Math.random() * Math.PI * 2
      const phi = Math.acos(2 * Math.random() - 1)
      positions[i * 3]     = r * Math.sin(phi) * Math.cos(theta)
      positions[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta)
      positions[i * 3 + 2] = r * Math.cos(phi)
      phases[i] = Math.random() * Math.PI * 2
    }
    const geometry = new THREE.BufferGeometry()
    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3))
    geometry.setAttribute('phase', new THREE.BufferAttribute(phases, 1))

    const material = new THREE.ShaderMaterial({
      uniforms: {
        time: { value: 0 },
        baseSize: { value: 1.8 },
      },
      vertexShader: /* glsl */ `
        attribute float phase;
        uniform float time;
        uniform float baseSize;
        void main() {
          vec4 mvPos = modelViewMatrix * vec4(position, 1.0);
          // 距离衰减 + 相位独立呼吸
          float size = baseSize * (1.0 + 0.6 * sin(time * 2.0 + phase));
          gl_PointSize = size * (300.0 / -mvPos.z);
          gl_Position = projectionMatrix * mvPos;
        }
      `,
      fragmentShader: /* glsl */ `
        void main() {
          vec2 uv = gl_PointCoord - 0.5;
          float d = length(uv);
          // 中心亮、边缘软的圆点
          float a = smoothstep(0.5, 0.05, d);
          gl_FragColor = vec4(1.0, 1.0, 1.0, a);
        }
      `,
      transparent: true,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    })
    this.starsMaterial = material as unknown as StarShaderMaterial
    this.stars = new THREE.Points(geometry, material)
    this.scene.add(this.stars)
  }

  // ==================== 分类点云 ====================
  addPointCloud(items: EarthPointItem[], radius: number = 51): void {
    // 释放旧点云(场景切换或刷新时)
    if (this.points) {
      this.scene.remove(this.points)
      this.points.geometry.dispose()
      ;(this.points.material as THREE.Material).dispose()
      this.points = null
    }

    const positions = new Float32Array(items.length * 3)
    const colors = new Float32Array(items.length * 3)
    items.forEach((it, i) => {
      const v = latLngToVec3(it.lng, it.lat, radius)
      positions[i * 3]     = v.x
      positions[i * 3 + 1] = v.y
      positions[i * 3 + 2] = v.z
      const c = new THREE.Color(it.color)
      colors[i * 3]     = c.r
      colors[i * 3 + 1] = c.g
      colors[i * 3 + 2] = c.b
    })

    const geometry = new THREE.BufferGeometry()
    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3))
    geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3))

    const material = new THREE.PointsMaterial({
      size: this.basePointSize,
      vertexColors: true,
      sizeAttenuation: true,
      transparent: true,
      opacity: 0.9,
    })

    this.points = new THREE.Points(geometry, material)
    // 偏移量通过 userData 携带,供 animate 阶段做相位呼吸
    ;(this.points as unknown as { userData: { offsets: number[] } }).userData = {
      offsets: items.map((it) => it.offset),
    }
    this.scene.add(this.points)
  }

  // ==================== 启动 RAF 循环 ====================
  startRotation(speed: number = 0.05): void {
    this.rotationSpeed = speed
    this.autoRotate = true

    const animate = (): void => {
      this.animationId = requestAnimationFrame(animate)
      this.time += 0.016

      if (this.autoRotate && this.earth) {
        this.earth.rotation.y += this.rotationSpeed * 0.016
        // 云层与地球同步自转
        if (this.clouds) this.clouds.rotation.y += this.rotationSpeed * 0.016
      }

      // 星空 Twinkle: 推 time uniform
      if (this.starsMaterial) {
        this.starsMaterial.uniforms.time.value = this.time
      }

      // 点云呼吸: size = base * (1 + 0.5 * sin(t)),opacity 同步起伏
      if (this.points) {
        const ud = (this.points as unknown as { userData: { offsets: number[] } }).userData
        if (ud?.offsets) {
          const mat = this.points.material as THREE.PointsMaterial
          const breath = 1 + 0.5 * Math.sin(this.time * 2)
          mat.size = this.basePointSize * breath
          mat.opacity = 0.7 + 0.3 * Math.sin(this.time * 1.5)
        }
      }

      this.renderer.render(this.scene, this.camera)
    }
    animate()
  }

  // ==================== 缩放(由外部按钮或滚轮调用) ====================
  setZoom(distance: number): void {
    // 距离范围 60-200
    const clamped = Math.max(60, Math.min(200, distance))
    const dir = this.camera.position.clone().normalize()
    this.camera.position.copy(dir.multiplyScalar(clamped))
  }

  // ==================== 响应式 ====================
  handleResize = (): void => {
    if (!this.container) return
    this.camera.aspect = this.container.clientWidth / this.container.clientHeight
    this.camera.updateProjectionMatrix()
    this.renderer.setSize(this.container.clientWidth, this.container.clientHeight)
  }

  // ==================== 释放资源 ====================
  dispose(): void {
    cancelAnimationFrame(this.animationId)
    window.removeEventListener('resize', this.handleResize)
    this.renderer.dispose()
    if (this.container.contains(this.renderer.domElement)) {
      this.container.removeChild(this.renderer.domElement)
    }
    // 显式释放点云 / 云层 / 星空(它们在 traverse 之前可能被替换)
    if (this.points) {
      this.points.geometry.dispose()
      ;(this.points.material as THREE.Material).dispose()
    }
    if (this.clouds) {
      this.clouds.geometry.dispose()
      ;(this.clouds.material as THREE.Material).dispose()
    }
    if (this.glow) {
      this.glow.geometry.dispose()
      ;(this.glow.material as THREE.Material).dispose()
    }
    if (this.stars) {
      this.stars.geometry.dispose()
      ;(this.stars.material as THREE.Material).dispose()
    }
    this.scene.traverse((obj) => {
      const o = obj as unknown as { geometry?: { dispose: () => void }; material?: THREE.Material | THREE.Material[] }
      if (o.geometry) o.geometry.dispose()
      if (o.material) {
        if (Array.isArray(o.material)) {
          o.material.forEach((m) => m.dispose())
        } else {
          o.material.dispose()
        }
      }
    })
  }
}
