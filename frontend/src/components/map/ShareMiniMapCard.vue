<script setup lang="ts">
/**
 * ShareMiniMapCard - 个人专属地图分享卡
 * ====================
 *
 * 视觉:
 *   - 浮动在地图右下角(el-button)
 *   - 点击 → emit('share', payload) → 父组件调 shareMap
 *   - 接收 :shareResult → 弹 el-dialog 显示二维码 + URL
 *   - 未配 Key 时(utils/amap 的 isAMapConfigured)→ 显示 el-alert 提示
 */
import { ref } from 'vue'
import { Share, Link, Close } from '@element-plus/icons-vue'
import { isAMapConfigured } from '@/utils/amap'

export interface SharePayload {
  title: string
  markers: Array<{ lng: number; lat: number; name?: string }>
}

export interface ShareResult {
  url: string
  qrcode_base64: string
}

interface Props {
  /** 后端 LBS share 返回的结果 */
  shareResult?: ShareResult | null
  loading?: boolean
  /** 是否检测到高德 Key 未配置(覆盖默认检测) */
  keyMissing?: boolean
}
const props = withDefaults(defineProps<Props>(), {
  shareResult: null,
  loading: false,
  keyMissing: undefined,
})

const emit = defineEmits<{
  (e: 'share', payload: SharePayload): void
}>()

const dialogVisible = ref(false)
const notConfigured = ref(props.keyMissing ?? !isAMapConfigured())

function onClick() {
  if (notConfigured.value) return
  emit('share', {
    title: '我的卫星图像分类地图',
    markers: [], // 由父组件按当前 overlay 范围填充
  })
}

function onDialogOpen() {
  if (props.shareResult) dialogVisible.value = true
}

defineExpose({ open: () => { if (props.shareResult) dialogVisible.value = true } })

// 关闭时无需清 shareResult(由父组件管理生命周期)
function copyUrl() {
  if (!props.shareResult?.url) return
  try {
    navigator.clipboard?.writeText(props.shareResult.url)
  } catch { /* 旧浏览器降级 */ }
}
</script>

<template>
  <div class="share-mini-card">
    <el-alert
      v-if="notConfigured"
      type="info"
      :closable="false"
      show-icon
      title="未配置 VITE_AMAP_JS_KEY"
      description="请在 frontend/.env 中配置高德 Key 后刷新,即可启用真实分享。"
      class="share-mini-card__alert"
    />
    <el-button
      v-else
      type="primary"
      :icon="Share"
      :loading="loading"
      class="share-mini-card__btn"
      @click="onClick"
    >
      生成分享卡
    </el-button>

    <el-dialog
      v-model="dialogVisible"
      title="个人专属地图分享卡"
      width="420px"
      align-center
      :close-on-click-modal="true"
    >
      <div v-if="shareResult" class="share-mini-card__dialog">
        <div class="share-mini-card__qr">
          <img
            v-if="shareResult.qrcode_base64"
            :src="`data:image/png;base64,${shareResult.qrcode_base64}`"
            alt="分享二维码"
            class="share-mini-card__qr-img"
          />
          <div v-else class="share-mini-card__qr-placeholder">无二维码</div>
        </div>
        <div class="share-mini-card__url">
          <el-input :model-value="shareResult.url" readonly>
            <template #prefix><el-icon><Link /></el-icon></template>
          </el-input>
          <el-button :icon="Share" plain @click="copyUrl">复制</el-button>
        </div>
        <p class="share-mini-card__tip">
          微信/高德扫码即可在小程序中打开此地图。
        </p>
      </div>
      <template #footer>
        <el-button @click="dialogVisible = false" :icon="Close">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.share-mini-card {
  position: absolute;
  right: var(--space-2);
  bottom: var(--space-2);
  z-index: 5;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: var(--space-1);
}
.share-mini-card__btn {
  box-shadow: var(--shadow-2);
  border-radius: var(--radius-pill);
  padding: 10px 18px;
  font-weight: var(--weight-medium);
}
.share-mini-card__alert {
  max-width: 280px;
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-2);
}
.share-mini-card__dialog {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2);
}
.share-mini-card__qr {
  width: 240px;
  height: 240px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg-soft);
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}
.share-mini-card__qr-img { width: 100%; height: 100%; object-fit: contain; }
.share-mini-card__qr-placeholder { color: var(--color-fg-3); font-size: var(--text-small); }
.share-mini-card__url {
  display: flex;
  gap: var(--space-1);
  width: 100%;
  align-items: center;
}
.share-mini-card__url .el-input { flex: 1; }
.share-mini-card__tip {
  font-size: var(--text-small);
  color: var(--color-fg-3);
  margin: 0;
  text-align: center;
}
</style>
