<script setup lang="ts">
/**
 * ConvertView - ONNX 转换触发
 * ====================
 *
 * 视觉: PageHeader + LoadingSkeleton 占位 + 衬线大字标题
 */
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useAdminStore } from '@/stores/admin'
import { usePageEnter } from '@/composables/usePageEnter'

const sectionRef = ref<HTMLElement | null>(null)
usePageEnter(sectionRef)

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
  <section ref="sectionRef" class="convert-view">
    <PageHeader
      title="ONNX 模型导出"
      subtitle="提交 PyTorch 权重路径,后端执行导出并校验 shape,再交由 TF.js 笔记本转换。"
    />

    <el-card shadow="never">
      <el-alert title="执行流程" type="info" :closable="false" show-icon class="flow-alert">
        <template #default>
          <ol class="flow-steps">
            <li>在本页面提交 PyTorch 权重路径</li>
            <li>后端启动 <code>scripts/convert_to_onnx.py</code> 导出 ONNX</li>
            <li>用 ONNX Runtime 验证 shape</li>
            <li>拿到 <code>model.web_model/best.onnx</code> 后,去 Colab 跑 <code>notebooks/tfjs_convert.ipynb</code></li>
          </ol>
        </template>
      </el-alert>

      <el-form :model="form" label-width="140px" class="convert-form">
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
          <el-button class="is-accent" :loading="submitting" @click="submit">开始导出</el-button>
        </el-form-item>
      </el-form>

      <div v-if="lastId != null" class="status-block">
        <p class="status-line">
          最新任务
          <span class="status-id">#{{ lastId }}</span>
          ：状态
          <el-tag :type="lastStatus === 'completed' ? 'success' : (lastStatus === 'failed' ? 'danger' : 'info')">
            {{ lastStatus }}
          </el-tag>
        </p>
        <p v-if="lastStatus === 'completed'" class="status-done">
          ✅ 导出完成。请在服务器上拉取 <code>{{ form.output }}</code>，然后到 Colab 跑转换笔记本。
        </p>
      </div>
    </el-card>
  </section>
</template>

<style scoped>
.convert-view { max-width: 1080px; margin: 0 auto; }
.flow-alert :deep(.el-alert__content) { font-family: var(--font-sans); }
.flow-steps { margin: 0; padding-left: var(--space-3); }
.flow-steps li { margin: 4px 0; color: var(--color-fg-2); }
.flow-steps code { background: var(--color-bg-alt); padding: 1px 6px; border-radius: var(--radius-sm); }
.convert-form { margin-top: var(--space-2); }
.status-block {
  margin-top: var(--space-3);
  padding: var(--space-2);
  background: var(--color-bg-soft);
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border);
}
.status-line { margin: 0; color: var(--color-fg-2); font-family: var(--font-sans); }
.status-id { font-family: var(--font-mono); font-weight: var(--weight-semibold); color: var(--color-fg); }
.status-done { margin: var(--space-1) 0 0 0; color: var(--color-success); }
.status-done code { background: var(--color-bg); padding: 1px 6px; border-radius: var(--radius-sm); border: 1px solid var(--color-border); }
</style>
