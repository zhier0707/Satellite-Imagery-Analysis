<script setup lang="ts">
/**
 * AdminLayout - 管理端布局
 * ====================
 *
 * 与 AppLayout 视觉一致:
 *   - 顶部 64px 水平导航 (5 个一级菜单)
 *   - 左侧 240px 二级标签
 *   - 白底 32/24px 主区
 */
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessageBox, ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

interface AdminMenu {
  name: string
  index: string
  label: string
  icon: string
  children: { path: string; label: string }[]
}
const menus: AdminMenu[] = [
  { name: 'users',    index: '/admin/users',    label: '用户管理', icon: 'User',     children: [{ path: '/admin/users',    label: '账号列表' }] },
  { name: 'records',  index: '/admin/records',  label: '全量记录', icon: 'Tickets',  children: [{ path: '/admin/records',  label: '分类记录' }] },
  { name: 'training', index: '/admin/training', label: '训练任务', icon: 'Cpu',      children: [{ path: '/admin/training', label: '训练列表' }] },
  { name: 'convert',  index: '/admin/convert',  label: 'ONNX 转换', icon: 'Refresh', children: [{ path: '/admin/convert',  label: '模型导出' }] },
  { name: 'reports',  index: '/admin/reports',  label: '全部报表', icon: 'Document', children: [{ path: '/admin/reports',  label: '任务管理' }] },
]

const activeMenu = computed<AdminMenu | null>(() => {
  for (const m of menus) {
    if (m.children.some((c) => route.path.startsWith(c.path))) return m
  }
  return menus[0]
})

const handleSelect = (idx: string) => router.push(idx)

const handleLogout = async () => {
  try { await ElMessageBox.confirm('确定退出？', '提示', { type: 'warning' }) } catch { return }
  await auth.logout()
  ElMessage.success('已退出')
  router.replace('/login')
}
</script>

<template>
  <el-container class="admin-layout">
    <!-- ============ 顶部水平导航 ============ -->
    <el-header class="topbar">
      <div class="topbar-left">
        <span class="brand">
          <el-icon class="brand-icon"><Setting /></el-icon>
          <span class="brand-text">管理控制台</span>
          <el-tag type="danger" size="small" class="role-tag">ADMIN</el-tag>
        </span>
        <el-menu
          mode="horizontal"
          :default-active="activeMenu?.index"
          class="topbar-menu"
          @select="handleSelect"
        >
          <el-menu-item v-for="m in menus" :key="m.name" :index="m.index">
            <el-icon><component :is="m.icon" /></el-icon>
            <span>{{ m.label }}</span>
          </el-menu-item>
        </el-menu>
      </div>
      <div class="topbar-right">
        <el-button text @click="router.push('/app')">← 回到用户端</el-button>
        <el-dropdown>
          <span class="user-info">
            <el-icon><UserFilled /></el-icon>
            <span class="username">{{ auth.user?.username }}</span>
            <el-tag type="danger" size="small">管理员</el-tag>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item disabled>{{ auth.user?.email }}</el-dropdown-item>
              <el-dropdown-item divided @click="handleLogout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </el-header>

    <el-container class="body">
      <el-aside width="240px" class="side">
        <div class="side-title">{{ activeMenu?.label }}</div>
        <el-menu
          :default-active="route.path"
          class="side-menu"
          @select="handleSelect"
        >
          <el-menu-item
            v-for="c in (activeMenu?.children ?? [])"
            :key="c.path"
            :index="c.path"
          >
            <el-icon><Minus /></el-icon>
            <template #title>{{ c.label }}</template>
          </el-menu-item>
        </el-menu>
      </el-aside>

      <el-main class="main">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
/* 与 AppLayout 共用同一套变量与节奏 */
.admin-layout { min-height: 100vh; background: var(--color-bg); }

.topbar {
  background: var(--color-bg);
  border-bottom: 1px solid var(--color-border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--space-3);
  height: 64px;
  position: sticky;
  top: 0;
  z-index: 10;
}
.topbar-left { display: flex; align-items: center; gap: var(--space-3); }
.brand {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-family: var(--font-serif);
  font-size: 18px;
  font-weight: var(--weight-semibold);
  color: var(--color-fg);
  letter-spacing: -0.01em;
  margin-right: var(--space-2);
}
.brand-icon { color: var(--color-accent); font-size: 22px; }
.role-tag { margin-left: 4px; }

.topbar-menu { border-bottom: none !important; background: transparent; }
.topbar-menu :deep(.el-menu-item) {
  font-family: var(--font-sans);
  font-size: 14px;
  font-weight: var(--weight-medium);
  height: 64px;
  line-height: 64px;
  padding: 0 var(--space-1);
  margin: 0 2px;
}
.topbar-right { display: flex; align-items: center; gap: var(--space-1); }
.user-info {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  padding: 6px var(--space-1);
  border-radius: var(--radius-sm);
  transition: background-color var(--duration-fast) var(--ease-standard);
}
.user-info:hover { background: var(--color-bg-alt); }
.username { font-size: var(--text-body); color: var(--color-fg); font-weight: var(--weight-medium); }

.body { height: calc(100vh - 64px); }
.side {
  background: var(--color-bg);
  border-right: 1px solid var(--color-border);
  padding: var(--space-2) 0;
  overflow-y: auto;
}
.side-title {
  padding: 0 var(--space-2);
  margin-bottom: var(--space-1);
  font-family: var(--font-sans);
  font-size: var(--text-small);
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--color-fg-3);
}
.side-menu { border-right: none; }
.side-menu :deep(.el-menu-item) {
  font-family: var(--font-sans);
  font-size: var(--text-body);
  color: var(--color-fg-2);
  height: 44px;
  line-height: 44px;
  margin: 2px var(--space-1);
  border-radius: var(--radius-sm);
}
.side-menu :deep(.el-menu-item.is-active) {
  color: var(--color-accent);
  background: var(--color-accent-soft);
  font-weight: var(--weight-medium);
}

.main {
  background: var(--color-bg);
  padding: var(--space-4);
  overflow-y: auto;
}

.fade-enter-active, .fade-leave-active { transition: opacity var(--duration-base) var(--ease-standard); }
.fade-enter-from, .fade-leave-to { opacity: 0; }

@media (max-width: 900px) {
  .topbar-menu { display: none; }
  .side { width: 180px !important; }
}
</style>
