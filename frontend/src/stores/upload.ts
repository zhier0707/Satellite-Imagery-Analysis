/**
 * Upload store - 单图分类与热力图状态
 *
 * 替代旧的 store.ts：imageFile / classify / heatmap / loading
 * 新增：changeResult（时相变化检测结果）
 */
import { defineStore } from 'pinia'
import type { ClassifyResult, HeatmapResult, ChangeResult } from '@/api'

interface UploadState {
  imageFile: File | null
  imageUrl: string
  classify: ClassifyResult | null
  heatmap: HeatmapResult | null
  loading: boolean
  /** 当前选中的热力图目标类别索引(0-9);用于在 HeatmapView 下拉切换后保留状态 */
  heatmapTarget: number

  // ==================== 变化检测 ====================
  imageA: File | null
  imageB: File | null
  imageAUrl: string
  imageBUrl: string
  changeResult: ChangeResult | null
  changeLoading: boolean
}

export const useUploadStore = defineStore('upload', {
  state: (): UploadState => ({
    imageFile: null,
    imageUrl: '',
    classify: null,
    heatmap: null,
    loading: false,
    heatmapTarget: 0,
    imageA: null,
    imageB: null,
    imageAUrl: '',
    imageBUrl: '',
    changeResult: null,
    changeLoading: false,
  }),
  actions: {
    setImage(file: File) {
      this.imageFile = file
      if (this.imageUrl) URL.revokeObjectURL(this.imageUrl)
      this.imageUrl = URL.createObjectURL(file)
      this.classify = null
      this.heatmap = null
      this.heatmapTarget = 0
    },
    /** 重置单图分类状态：清空图像文件、URL、分类结果与热力图 */
    resetUpload() {
      this.imageFile = null
      if (this.imageUrl) URL.revokeObjectURL(this.imageUrl)
      this.imageUrl = ''
      this.classify = null
      this.heatmap = null
      this.heatmapTarget = 0
      this.loading = false
    },
    /**
     * 写入热力图结果与对应目标类别索引。
     * 由 HeatmapView 在切换 el-select 时调用,保证 store 与 UI 状态一致。
     */
    setHeatmap(result: HeatmapResult, target: number) {
      this.heatmap = result
      this.heatmapTarget = target
    },
    setImageA(file: File) {
      this.imageA = file
      if (this.imageAUrl) URL.revokeObjectURL(this.imageAUrl)
      this.imageAUrl = URL.createObjectURL(file)
    },
    setImageB(file: File) {
      this.imageB = file
      if (this.imageBUrl) URL.revokeObjectURL(this.imageBUrl)
      this.imageBUrl = URL.createObjectURL(file)
    },
    clearChange() {
      this.imageA = null
      this.imageB = null
      if (this.imageAUrl) URL.revokeObjectURL(this.imageAUrl)
      if (this.imageBUrl) URL.revokeObjectURL(this.imageBUrl)
      this.imageAUrl = ''
      this.imageBUrl = ''
      this.changeResult = null
    },
  },
})
