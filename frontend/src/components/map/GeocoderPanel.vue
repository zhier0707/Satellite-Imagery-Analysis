<script setup lang="ts">
/**
 * GeocoderPanel - 地理编码 / 逆地理编码
 * ====================
 *
 * 两个 Tab:
 *   1. 地址 → 经纬度:输入地址 → emit('geocode', address) → 父组件调 api
 *      接收 :point props → 在右侧显示
 *   2. 经纬度 → 地址:点击地图选点 → emit('regeocode', lng, lat)
 *      接收 :address props → 显示
 *
 * 视觉:
 *   - el-tabs 极简风
 *   - 结果区在表单下方,带淡入
 */
import { ref, watch } from 'vue'
import type { LngLat } from '@/utils/amap'

interface Props {
  /** 正向地理编码结果(由父组件传回) */
  point?: LngLat | null
  /** 正向匹配的地址(可选) */
  formattedAddress?: string
  /** 逆地理结果(由父组件传回) */
  address?: string
  /** 父组件 loading 态(用于禁用按钮) */
  loading?: boolean
}
const props = withDefaults(defineProps<Props>(), {
  point: null,
  formattedAddress: '',
  address: '',
  loading: false,
})

const emit = defineEmits<{
  (e: 'geocode', address: string): void
  (e: 'regeocode', lng: number, lat: number): void
}>()

const activeTab = ref<'forward' | 'reverse'>('forward')

// 正向
const forwardAddr = ref('')
function onForward() {
  const a = forwardAddr.value.trim()
  if (!a) return
  emit('geocode', a)
}

// 逆地理
const lng = ref<number | null>(null)
const lat = ref<number | null>(null)
function onReverse() {
  if (lng.value == null || lat.value == null) return
  emit('regeocode', lng.value, lat.value)
}

/** 父组件可通过 setReverseCoord(lng, lat) 让面板回填(由父组件用 ref 调) */
defineExpose({
  setReverseCoord: (l: number, la: number) => {
    lng.value = l
    lat.value = la
    activeTab.value = 'reverse'
  },
})

// 监听 props.point 清空(比如用户切换到逆地理),避免误用
watch(
  () => props.point,
  (p) => {
    if (!p) forwardAddr.value = ''
  },
)
</script>

<template>
  <div class="geocoder-panel">
    <el-tabs v-model="activeTab" class="geocoder-panel__tabs">
      <!-- ==================== 正向 ==================== -->
      <el-tab-pane label="地址→经纬度" name="forward">
        <div class="geocoder-panel__row">
          <el-input
            v-model="forwardAddr"
            placeholder="例如:北京市海淀区中关村"
            clearable
            @keyup.enter="onForward"
          />
          <el-button type="primary" :loading="loading" @click="onForward">转换</el-button>
        </div>
        <div v-if="point" class="geocoder-panel__result fade-in">
          <div class="geocoder-panel__coord">
            <span class="text-fg-3">经度</span>
            <span class="text-mono">{{ point[0].toFixed(6) }}</span>
          </div>
          <div class="geocoder-panel__coord">
            <span class="text-fg-3">纬度</span>
            <span class="text-mono">{{ point[1].toFixed(6) }}</span>
          </div>
          <div v-if="formattedAddress" class="geocoder-panel__addr">
            {{ formattedAddress }}
          </div>
        </div>
      </el-tab-pane>

      <!-- ==================== 逆地理 ==================== -->
      <el-tab-pane label="经纬度→地址" name="reverse">
        <div class="geocoder-panel__row">
          <el-input
            v-model.number="lng"
            type="number"
            placeholder="经度(lng)"
          />
          <el-input
            v-model.number="lat"
            type="number"
            placeholder="纬度(lat)"
          />
          <el-button type="primary" :loading="loading" @click="onReverse">查询</el-button>
        </div>
        <p class="geocoder-panel__hint">
          提示:也可点击地图空白处自动填充当前坐标。
        </p>
        <div v-if="address" class="geocoder-panel__result fade-in">
          <div class="geocoder-panel__addr">{{ address }}</div>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<style scoped>
.geocoder-panel { width: 100%; }
.geocoder-panel__tabs :deep(.el-tabs__nav-wrap::after) { background: var(--color-border); }
.geocoder-panel__row {
  display: flex;
  gap: var(--space-1);
  align-items: center;
}
.geocoder-panel__row .el-input { flex: 1; }
.geocoder-panel__hint {
  margin-top: var(--space-1);
  font-size: var(--text-small);
  color: var(--color-fg-3);
}
.geocoder-panel__result {
  margin-top: var(--space-2);
  padding: var(--space-2);
  background: var(--color-bg-soft);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.geocoder-panel__coord {
  display: flex;
  justify-content: space-between;
  font-size: var(--text-body);
  color: var(--color-fg-2);
}
.geocoder-panel__addr {
  margin-top: 4px;
  font-size: var(--text-body);
  color: var(--color-fg);
  line-height: var(--line-base);
}
.fade-in { animation: fadeIn 0.25s var(--ease-standard); }
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(4px); }
  to   { opacity: 1; transform: translateY(0); }
}
</style>
