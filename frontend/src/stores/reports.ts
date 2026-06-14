/**
 * Reports store - 我的报表任务列表
 */
import { defineStore } from 'pinia'
import * as api from '@/api'
import type { ReportJob, ReportKind } from '@/api'

interface ReportsState {
  items: ReportJob[]
  total: number
  loading: boolean
  current: ReportJob | null
}

export const useReportsStore = defineStore('reports', {
  state: (): ReportsState => ({
    items: [],
    total: 0,
    loading: false,
    current: null,
  }),
  actions: {
    async fetch(page = 1, pageSize = 20) {
      this.loading = true
      try {
        const r = await api.listMyReports(page, pageSize)
        this.items = r.items
        this.total = r.total
      } finally {
        this.loading = false
      }
    },
    async create(payload: {
      kind: ReportKind
      time_range_start?: string
      time_range_end?: string
      class_filter?: string[]
    }) {
      const r = await api.createReport(payload)
      this.items.unshift(r)
      this.total += 1
      return r
    },
    async refreshOne(id: number) {
      const r = await api.getReport(id)
      const idx = this.items.findIndex((x) => x.id === id)
      if (idx >= 0) this.items[idx] = r
      this.current = r
      return r
    },
  },
})
