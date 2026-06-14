/**
 * Admin store - 管理端数据（用户/记录/训练任务/转换）
 */
import { defineStore } from 'pinia'
import * as api from '@/api'
import type {
  UserOut, RecordOut, TrainingJob,
} from '@/api'

interface AdminState {
  users: UserOut[]
  records: RecordOut[]
  recordsTotal: number
  training: TrainingJob[]
  trainingTotal: number
  loading: boolean
}

export const useAdminStore = defineStore('admin', {
  state: (): AdminState => ({
    users: [],
    records: [],
    recordsTotal: 0,
    training: [],
    trainingTotal: 0,
    loading: false,
  }),
  actions: {
    async fetchUsers() {
      this.loading = true
      try {
        this.users = await api.adminListUsers()
      } finally {
        this.loading = false
      }
    },
    async updateUser(id: number, patch: Partial<Pick<UserOut, 'role' | 'is_active'>>) {
      const r = await api.adminUpdateUser(id, patch)
      const idx = this.users.findIndex((u) => u.id === id)
      if (idx >= 0) this.users[idx] = r
      return r
    },
    async deleteUser(id: number) {
      await api.adminDeleteUser(id)
      this.users = this.users.filter((u) => u.id !== id)
    },
    async fetchRecords(userId?: number, page = 1, pageSize = 50) {
      const r = await api.adminListRecords(userId, page, pageSize)
      this.records = r.items
      this.recordsTotal = r.total
    },
    async fetchTraining(page = 1, pageSize = 20) {
      const r = await api.adminListTraining(page, pageSize)
      this.training = r.items
      this.trainingTotal = r.total
    },
    async startTraining(payload: {
      stage: number; epochs: number; batch_size: number; lr: number
      resume_from?: string; weights?: string
    }) {
      const r = await api.adminStartTraining(payload)
      this.training.unshift(r)
      return r
    },
    async stopTraining(id: number) {
      await api.adminStopTraining(id)
    },
    async getTraining(id: number): Promise<TrainingJob> {
      return await api.adminGetTraining(id)
    },
    async startConvert(payload: {
      weights: string; output?: string; image_size?: number; opset?: number
    }) {
      return await api.adminStartConvert(payload)
    },
  },
})
