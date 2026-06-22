<script setup lang="ts">
/**
 * EmptyState - 统一空状态
 * ====================
 *
 * 替代 el-empty 的"系统蓝"风格,符合学术白底主题。
 * 支持纯文本 description,也支持 default slot 自定义按钮。
 *
 * Phase E.2: 新增 variant 语义色,根据场景决定图标颜色。
 *   - default: 学术蓝(项目主色)
 *   - success: 绿(成功/完成)
 *   - warning: 橙(警告/提示)
 *   - error:   红(失败/异常)
 *   - info:    蓝(信息/引导)
 */
import { computed } from 'vue'

type VariantType = 'default' | 'success' | 'warning' | 'error' | 'info'

interface Props {
  /** Element Plus icon 组件名,如 'PictureFilled' */
  icon?: string
  title: string
  description?: string
  /** 语义变体 - 决定图标颜色;缺省时为学术蓝 */
  variant?: VariantType
}
const props = defineProps<Props>()

/** 根据 variant 返回对应 CSS 变量;带 fallback 保证主题缺失时仍可读 */
const variantColor = computed<string>(() => {
  switch (props.variant) {
    case 'success': return 'var(--color-success, #10B981)'
    case 'warning': return 'var(--color-warning, #F59E0B)'
    case 'error':   return 'var(--color-danger, #EF4444)'
    case 'info':    return 'var(--color-info, #3B82F6)'
    default:        return 'var(--color-accent, #2563EB)'
  }
})
</script>

<template>
  <div class="empty-state">
    <div class="empty-state__inner">
      <div
        v-if="icon"
        class="empty-state__icon"
        :style="{ color: variantColor }"
      >
        <el-icon :size="48">
          <component :is="icon" />
        </el-icon>
      </div>
      <h3 class="empty-state__title">{{ title }}</h3>
      <p v-if="description" class="empty-state__desc">{{ description }}</p>
      <div v-if="$slots.default" class="empty-state__action">
        <slot />
      </div>
    </div>
  </div>
</template>

<style scoped>
.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-5) var(--space-3);
}
.empty-state__inner {
  text-align: center;
  max-width: 480px;
}
.empty-state__icon {
  /* 图标颜色由 :style color 控制(根据 variant 决定);无 variant 时为学术蓝 */
  margin-bottom: var(--space-2);
  display: inline-block;
}
.empty-state__title {
  font-family: var(--font-serif);
  font-size: var(--text-h3);
  color: var(--color-fg);
  margin: 0;
  font-weight: var(--weight-semibold);
}
.empty-state__desc {
  margin: var(--space-1) 0 0 0;
  color: var(--color-fg-2);
  font-size: var(--text-body);
  line-height: var(--line-base);
}
.empty-state__action {
  margin-top: var(--space-2);
  display: flex;
  justify-content: center;
  gap: var(--space-1);
}
</style>
