<script setup lang="ts">
/**
 * TrainingJobsView - 训练任务管理
 *
 * - 训练任务列表
 * - "启动新训练" 表单
 * - 详情抽屉 (log_tail)
 */
import { onMounted, onUnmounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAdminStore } from '@/stores/admin'
import type { TrainingJob } from '@/api'

const admin = useAdminStore()
const drawerOpen = ref(false)
const current = ref<TrainingJob | null>(null)
const detailLog = ref('')

let pollTimer: number | null = null

const refresh = () => admin.fetchTraining(1, 50)

const poll = async () => {
  // 轮询所有非终态的 job
  const running = admin.training.filter((j) => j.status === 'queued' || j.status === 'running')
  for (const j of running) {
    try {
      const latest = await admin.getTraining(j.id)
      const idx = admin.training.findIndex((x) => x.id === j.id)
      if (idx >= 0) admin.training[idx] = latest
    } catch {}
  }
}

onMounted(async () => {
  await refresh()
  pollTimer = window.setInterval(poll, 3000)
})
onUnmounted(() => { if (pollTimer) clearInterval(pollTimer) })

const form = ref({
  stage: 3, epochs: 10, batch_size: 32, lr: 1e-4,
  resume_from: '', weights: '',
})

const submit = async () => {
  try {
    const r = await admin.startTraining({
      stage: form.value.stage,
      epochs: form.value.epochs,
      batch_size: form.value.batch_size,
      lr: form.value.lr,
      resume_from: form.value.resume_from || undefined,
      weights: form.value.weights || undefined,
    })
    ElMessage.success(`已启动训练 #${r.id}`)
  } catch (e: any) {
    ElMessage.error('启动失败：' + (e?.response?.data?.detail || e?.message))
  }
}

const stop = async (id: number) => {
  try {
    await ElMessageBox.confirm(`终止训练 #${id}?`, '提示', { type: 'warning' })
    await admin.stopTraining(id)
    ElMessage.success('已请求停止')
  } catch {}
}

const showDetail = async (j: TrainingJob) => {
  current.value = j
  detailLog.value = '加载中…'
  drawerOpen.value = true
  try {
    const full = await admin.getTraining(j.id)
    detailLog.value = full.log_tail || '（无日志）'
  } catch (e: any) {
    detailLog.value = '加载失败：' + (e?.response?.data?.detail || e?.message)
  }
}

const asJob = (row: any): TrainingJob => row as TrainingJob

const statusType = (s: string): 'success' | 'danger' | 'warning' | 'info' => {
  if (s === 'completed') return 'success'
  if (s === 'failed') return 'danger'
  if (s === 'running') return 'warning'
  if (s === 'stopped') return 'info'
  return 'info'
}
</script>

<template>
  <el-card shadow="hover">
    <template #header>
      <span>训练任务</span>
      <el-button text @click="refresh" style="float: right">刷新</el-button>
    </template>

    <el-form :inline="true" :model="form" class="start-form">
      <el-form-item label="解冻阶段">
        <el-select v-model="form.stage" style="width: 120px">
          <el-option label="1 - 仅分类头" :value="1" />
          <el-option label="2 - + 后 2 个 stage" :value="2" />
          <el-option label="3 - 全量" :value="3" />
        </el-select>
      </el-form-item>
      <el-form-item label="Epochs"><el-input-number v-model="form.epochs" :min="1" :max="100" /></el-form-item>
      <el-form-item label="Batch"><el-input-number v-model="form.batch_size" :min="4" :max="256" /></el-form-item>
      <el-form-item label="LR"><el-input-number v-model="form.lr" :step="1e-5" :precision="6" /></el-form-item>
      <el-form-item label="Resume"><el-input v-model="form.resume_from" placeholder="可选, .pt 路径" style="width: 200px" /></el-form-item>
      <el-form-item label="Weights"><el-input v-model="form.weights" placeholder="可选, 预训练权重" style="width: 200px" /></el-form-item>
      <el-form-item><el-button type="primary" @click="submit">启动训练</el-button></el-form-item>
    </el-form>

    <el-table :data="admin.training" border empty-text="暂无任务" style="margin-top: 12px">
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="stage" label="阶段" width="100" />
      <el-table-column label="状态" width="120">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)" size="small">{{ row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="pid" label="PID" width="100" />
      <el-table-column prop="created_at" label="创建时间" min-width="180" />
      <el-table-column label="完成时间" min-width="180">
        <template #default="{ row }">
          <span v-if="(row as TrainingJob).finished_at">{{ (row as TrainingJob).finished_at }}</span>
          <span v-else class="dim">—</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="240" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="showDetail(asJob(row))">详情</el-button>
          <el-button v-if="(row as TrainingJob).status === 'queued' || (row as TrainingJob).status === 'running'" size="small" type="danger" @click="stop((row as TrainingJob).id)">停止</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>

  <el-drawer v-model="drawerOpen" title="训练任务详情" size="60%">
    <div v-if="current">
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="ID">{{ current.id }}</el-descriptions-item>
        <el-descriptions-item label="Stage">{{ current.stage }}</el-descriptions-item>
        <el-descriptions-item label="状态"><el-tag :type="statusType(current.status)" size="small">{{ current.status }}</el-tag></el-descriptions-item>
        <el-descriptions-item label="PID">{{ current.pid || '—' }}</el-descriptions-item>
        <el-descriptions-item label="metrics">{{ current.metrics_json || '—' }}</el-descriptions-item>
        <el-descriptions-item label="error">{{ current.error || '—' }}</el-descriptions-item>
      </el-descriptions>
      <h4 style="margin-top: 16px">日志（最后 50 行）</h4>
      <pre class="log-box">{{ detailLog }}</pre>
    </div>
  </el-drawer>
</template>

<style scoped>
.start-form { background: #fafafa; padding: 12px; border-radius: 4px; }
.dim { color: #c0c4cc; }
.log-box { background: #1e1e1e; color: #d4d4d4; padding: 12px; border-radius: 4px;
  max-height: 60vh; overflow: auto; font-size: 12px; font-family: 'Cascadia Code', monospace; white-space: pre-wrap; }
</style>
