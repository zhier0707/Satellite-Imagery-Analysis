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
