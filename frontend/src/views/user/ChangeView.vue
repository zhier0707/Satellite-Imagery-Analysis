<script setup lang="ts">
/**
 * ChangeView - 时相变化检测
 *
 * 上传两图 (A/B) → 调 /api/change → 展示:
 * - top1_changed 标签
 * - 自然语言 summary
 * - changes 表格
 * - 两图并排预览
 */
import { ElMessage } from 'element-plus'
import { Picture, Refresh, Aim } from '@element-plus/icons-vue'
import { useUploadStore } from '@/stores/upload'
import { changeDetect } from '@/api'

const upload = useUploadStore()

const onA = (file: any) => {
  const raw = file.raw ?? file
  if (raw) upload.setImageA(raw)
}
const onB = (file: any) => {
  const raw = file.raw ?? file
  if (raw) upload.setImageB(raw)
}

const runChange = async () => {
  if (!upload.imageA || !upload.imageB) {
    ElMessage.warning('请先分别上传两期图像 A 和 B')
    return
  }
  upload.changeLoading = true
  try {
    upload.changeResult = await changeDetect(upload.imageA, upload.imageB)
    ElMessage.success('变化检测完成')
  } catch (e: any) {
    ElMessage.error('变化检测失败：' + (e?.response?.data?.detail || e?.message || e))
  } finally {
    upload.changeLoading = false
  }
}

const tagType = (t: string) => {
  if (t === 'top1_changed') return 'danger'
  if (t === 'label_gained') return 'success'
  if (t === 'label_lost') return 'warning'
  return 'info'
}
const tagLabel = (t: string) => {
  if (t === 'top1_changed') return '主类变化'
  if (t === 'label_gained') return '新增标签'
  if (t === 'label_lost') return '失去标签'
  return t
}
</script>

<template>
  <div class="change-view">
    <el-card shadow="hover">
      <template #header>
        <span><el-icon><Aim /></el-icon> 时相变化检测</span>
      </template>

      <div class="upload-row">
        <div class="upload-col">
          <h4>时期 A（早期）</h4>
          <el-upload drag :auto-upload="false" :show-file-list="false"
            accept="image/png,image/jpeg,image/jpg" :on-change="onA">
            <el-icon class="el-icon--upload"><Picture /></el-icon>
            <div class="el-upload__text">拖拽 A 图或<em>点击选择</em></div>
          </el-upload>
          <div v-if="upload.imageAUrl" class="preview">
            <el-image :src="upload.imageAUrl" fit="contain" style="max-width: 280px; max-height: 280px" />
          </div>
        </div>

        <div class="upload-col">
          <h4>时期 B（晚期）</h4>
          <el-upload drag :auto-upload="false" :show-file-list="false"
            accept="image/png,image/jpeg,image/jpg" :on-change="onB">
            <el-icon class="el-icon--upload"><Picture /></el-icon>
            <div class="el-upload__text">拖拽 B 图或<em>点击选择</em></div>
          </el-upload>
          <div v-if="upload.imageBUrl" class="preview">
            <el-image :src="upload.imageBUrl" fit="contain" style="max-width: 280px; max-height: 280px" />
          </div>
        </div>
      </div>

      <el-divider />
      <div class="actions">
        <el-button type="primary" :loading="upload.changeLoading" @click="runChange">
          <el-icon><Refresh /></el-icon> 开始对比
        </el-button>
        <el-button @click="upload.clearChange()">清空</el-button>
      </div>
    </el-card>

    <!-- ============ 结果区 ============ -->
    <el-card v-if="upload.changeResult" shadow="hover" class="result-card">
      <template #header>
        <span>检测结果</span>
        <el-tag v-if="upload.changeResult.changes.find((c) => c.type === 'top1_changed')" type="danger" effect="dark" style="margin-left: 12px">
          top1 已变化
        </el-tag>
        <el-tag v-else type="success" effect="dark" style="margin-left: 12px">top1 未变</el-tag>
      </template>

      <el-alert :title="upload.changeResult.summary" type="info" :closable="false" show-icon />

      <h4 style="margin-top: 16px">Top-1 对比</h4>
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="A 时期">{{ upload.changeResult.top1_a.label }} ({{ (upload.changeResult.top1_a.score * 100).toFixed(2) }}%)</el-descriptions-item>
        <el-descriptions-item label="B 时期">{{ upload.changeResult.top1_b.label }} ({{ (upload.changeResult.top1_b.score * 100).toFixed(2) }}%)</el-descriptions-item>
      </el-descriptions>

      <h4 style="margin-top: 16px">变化列表（{{ upload.changeResult.changes.length }} 项）</h4>
      <el-table :data="upload.changeResult.changes" border size="small" empty-text="无变化">
        <el-table-column label="类型" width="120">
          <template #default="{ row }">
            <el-tag :type="tagType(row.type)" size="small">{{ tagLabel(row.type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="label" label="标签" />
        <el-table-column label="A 时期分数">
          <template #default="{ row }">
            <span v-if="row.score_a !== undefined">{{ (row.score_a * 100).toFixed(2) }}%</span>
            <span v-else class="dim">—</span>
          </template>
        </el-table-column>
        <el-table-column label="B 时期分数">
          <template #default="{ row }">
            <span v-if="row.score_b !== undefined">{{ (row.score_b * 100).toFixed(2) }}%</span>
            <span v-else class="dim">—</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<style scoped>
.change-view { display: flex; flex-direction: column; gap: 16px; }
.upload-row { display: flex; gap: 24px; flex-wrap: wrap; }
.upload-col { flex: 1; min-width: 320px; }
.upload-col h4 { margin: 0 0 8px 0; color: #303133; }
.preview { margin-top: 12px; text-align: center; }
.actions { display: flex; gap: 12px; }
.dim { color: #c0c4cc; }
.result-card { margin-top: 16px; }
</style>
