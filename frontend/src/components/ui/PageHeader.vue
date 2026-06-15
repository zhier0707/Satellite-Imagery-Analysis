<script setup lang="ts">
/**
 * PageHeader - 统一页面标题区
 * ====================
 *
 * 设计意图:
 *   - 衬线大字 32px,源于学术海报标题字号
 *   - 副标题灰色 14px,1 行说明本页面职责
 *   - 右侧 actions slot 放主操作按钮
 *   - 上下间距与卡片 24px 节奏一致
 */
interface Props {
  title: string
  subtitle?: string
}
defineProps<Props>()
</script>

<template>
  <header class="page-header">
    <div class="page-header__text">
      <h1 class="page-header__title">{{ title }}</h1>
      <p v-if="subtitle" class="page-header__subtitle">{{ subtitle }}</p>
    </div>
    <div v-if="$slots.actions" class="page-header__actions">
      <slot name="actions" />
    </div>
  </header>
</template>

<style scoped>
.page-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-3) 0 var(--space-2);
  border-bottom: 1px solid var(--color-border);
  margin-bottom: var(--space-3);
}
.page-header__title {
  font-family: var(--font-serif);
  font-size: var(--text-h1);
  font-weight: var(--weight-semibold);
  color: var(--color-fg);
  letter-spacing: -0.01em;
  line-height: var(--line-tight);
  margin: 0;
}
.page-header__subtitle {
  margin: 6px 0 0 0;
  color: var(--color-fg-2);
  font-size: var(--text-body);
  font-family: var(--font-sans);
  line-height: var(--line-base);
  max-width: 720px;
}
.page-header__actions {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  flex-shrink: 0;
}
@media (max-width: 720px) {
  .page-header { flex-direction: column; align-items: flex-start; }
}
</style>
