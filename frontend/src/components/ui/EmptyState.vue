<script setup lang="ts">
/**
 * EmptyState - 统一空状态
 * ====================
 *
 * 替代 el-empty 的"系统蓝"风格,符合学术白底主题。
 * 支持纯文本 description,也支持 default slot 自定义按钮。
 */
interface Props {
  /** Element Plus icon 组件名,如 'PictureFilled' */
  icon?: string
  title: string
  description?: string
}
defineProps<Props>()
</script>

<template>
  <div class="empty-state">
    <div class="empty-state__inner">
      <el-icon v-if="icon" :size="48" class="empty-state__icon">
        <component :is="icon" />
      </el-icon>
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
  color: var(--color-fg-3);
  margin-bottom: var(--space-2);
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
