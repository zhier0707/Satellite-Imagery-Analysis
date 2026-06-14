<script setup lang="ts">
/**
 * ConvertView - ONNX 转换触发
 */
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useAdminStore } from '@/stores/admin'

const admin = useAdminStore()

const form = ref({
  weights: 'models/checkpoints/best.pt',
  output: 'models/web_model/best.onnx',
  image_size: 384,
  opset: 13,
})
const submitting = ref(false)
const lastId = ref<number | null>(null)
const lastStatus = ref<string>('')

const submit = async () => {
  submitting.value = true
  try {
    const r = await admin.startConvert({
      weights: form.value.weights,
      output: form.value.output,
      image_size: form.value.image_size,
      opset: form.value.opset,
    })
    lastId.value = r.id
    lastStatus.value = r.status
    ElMessage.success(`已提交转换任务 #${r.id}`)
    pollStatus()
  } catch (e: any) {
    ElMessage.error('提交失败：' + (e?.response?.data?.detail || e?.message))
  } finally {
    submitting.value = false
  }
}

let pollTimer: number | null = null
const pollStatus = () => {
  if (pollTimer) clearInterval(pollTimer)
  pollTimer = window.setInterval(async () => {
    if (lastId.value == null) return
    try {
      const r = await admin.getTraining(lastId.value)
      lastStatus.value = r.status
      if (['completed', 'failed', 'stopped'].includes(r.status)) {
        if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
      }
    } catch {}
  }, 2000)
}
</script>

<template>
  <el-card shadow="hover">
    <template #header><span>ONNX 模型导出</span></template>

    <el-alert title="执行流程" type="info" :closable="false" show-icon style="margin-bottom: 16px">
      <p>1. 在本页面提交 PyTorch 权重路径 → 2. 后端启动 <code>scripts/convert_to_onnx.py</code> 导出 ONNX → 3. 用 ONNX Runtime 验证 shape → 4. 拿到 <code>model.web_model/best.onnx</code> 后,去 Colab 跑 <code>notebooks/tfjs_convert.ipynb</code> 转换到 TF.js。</p>
    </el-alert>

    <el-form :model="form" label-width="120px">
      <el-form-item label="PyTorch 权重">
        <el-input v-model="form.weights" placeholder="models/checkpoints/best.pt" />
      </el-form-item>
      <el-form-item label="ONNX 输出">
        <el-input v-model="form.output" placeholder="models/web_model/best.onnx" />
      </el-form-item>
      <el-form-item label="图像尺寸">
        <el-input-number v-model="form.image_size" :min="64" :max="1024" />
      </el-form-item>
      <el-form-item label="ONNX Opset">
        <el-input-number v-model="form.opset" :min="11" :max="17" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" :loading="submitting" @click="submit">开始导出</el-button>
      </el-form-item>
    </el-form>

    <el-divider />

    <div v-if="lastId != null">
      <p>最新任务 #{{ lastId }}: 状态 <el-tag>{{ lastStatus }}</el-tag></p>
      <p v-if="lastStatus === 'completed'">
        ✅ 导出完成。请在服务器上拉取 <code>{{ form.output }}</code>，然后到 Colab 跑转换笔记本。
      </p>
    </div>
  </el-card>
</template>
