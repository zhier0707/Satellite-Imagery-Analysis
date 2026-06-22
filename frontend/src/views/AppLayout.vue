<script setup lang="ts">
/**
 * AppLayout - 用户端布局
 * ====================
 *
 * 视觉规范 (Phase 10):
 *   - 顶部 64px 水平导航: Logo + 7 个一级菜单 + 右侧用户信息
 *   - 左侧 240px 二级标签栏: 当前一级菜单的 children
 *   - 主区白底 32/24px 内边距
 *   - 菜单顺序: 图像上传 / Top-5 / 热力图 / **地图视图** / 分类统计 / 变化检测 / 我的报表
 *
 * Phase C:
 *   - 用户下拉菜单加「进入管理控制台」项 (admin 可见)
 *   - 品牌区右侧加 ADMIN 徽章 + 控制台按钮 (admin 可见)
 *   - 顶部水平导航追加「管理控制台」菜单项 (admin 可见)
 */
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessageBox, ElMessage } from 'element-plus'
import { Setting } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

interface MenuItem {
  name: string
  index: string
  label: string
  icon: string
  children: { path: string; label: string }[]
}
const menus: MenuItem[] = [
  { name: 'home',    index: '/app/home',    label: '首页',     icon: 'HomeFilled',    children: [{ path: '/app/home',    label: '项目概览' }] },
  // 任务硬性要求: Phase B 在「首页」后插入「3D 大屏」
  { name: 'screen',  index: '/app/screen',  label: '3D 大屏',  icon: 'DataLine',      children: [{ path: '/app/screen',  label: '数据驾驶舱' }] },
  { name: 'upload',  index: '/app/upload',  label: '图像上传', icon: 'UploadFilled',  children: [{ path: '/app/upload',  label: '上传与识别' }] },
  { name: 'top5',    index: '/app/top5',    label: 'Top-5',  icon: 'ChatLineRound', children: [{ path: '/app/top5',    label: '概率条' }] },
  { name: 'heatmap', index: '/app/heatmap', label: '热力图',  icon: 'PictureFilled', children: [{ path: '/app/heatmap', label: 'Grad-CAM' }] },
  // 任务硬性要求: 第 7 项 = 地图视图,位于 heatmap 与 stats 之间
  { name: 'map',     index: '/app/map',     label: '地图视图', icon: 'MapLocation',   children: [{ path: '/app/map',     label: '高德地图' }] },
  { name: 'stats',   index: '/app/stats',   label: '分类统计', icon: 'PieChart',      children: [{ path: '/app/stats',   label: '统计' }] },
  { name: 'change',  index: '/app/change',  label: '变化检测', icon: 'Refresh',       children: [{ path: '/app/change',  label: '时相对比' }] },
  { name: 'reports', index: '/app/reports', label: '我的报表', icon: 'Document',      children: [{ path: '/app/reports', label: '导出与下载' }] },
]

const activeMenu = computed<MenuItem | null>(() => {
  for (const m of menus) {
    if (m.children.some((c) => route.path.startsWith(c.path))) return m
  }
  return menus[0]
})

const handleSelect = (idx: string) => router.push(idx)

/** Phase C: 跳转到管理控制台默认页 (用户管理) */
const goToAdmin = () => router.push('/admin/users')

const handleLogout = async () => {
  try {
    await ElMessageBox.confirm('确定要退出登录吗？', '提示', { type: 'warning' })
  } catch {
    return
  }
  await auth.logout()
  ElMessage.success('已退出')
  router.replace('/login')
}
</script>

<template>
  <el-container class="app-layout">
    <!-- ============ 顶部水平导航 ============ -->
    <el-header class="topbar">
      <div class="topbar-left">
        <span class="brand">
          <el-icon class="brand-icon"><Compass /></el-icon>
          <span class="brand-text">卫星图像分析</span>
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
          <!-- Phase C: 管理员可见的管理控制台入口 -->
          <el-menu-item v-if="auth.isAdmin" index="/admin/users" class="admin-menu-item">
            <el-icon><Setting /></el-icon>
            <span>管理控制台</span>
          </el-menu-item>
        </el-menu>
      </div>
      <div class="topbar-right">
        <!-- Phase C: 管理员在头部右侧的醒目入口 -->
        <div v-if="auth.isAdmin" class="admin-entry">
          <el-tag type="danger" size="small" class="admin-badge">ADMIN</el-tag>
          <el-button text type="primary" class="admin-console-btn" @click="goToAdmin">
            <el-icon><Setting /></el-icon>
            <span>控制台</span>
          </el-button>
        </div>
        <el-dropdown>
          <span class="user-info">
            <el-icon><UserFilled /></el-icon>
            <span class="username">{{ auth.user?.username }}</span>
            <el-tag v-if="auth.isAdmin" type="danger" size="small">管理员</el-tag>
            <el-tag v-else type="info" size="small">用户</el-tag>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item disabled>{{ auth.user?.email }}</el-dropdown-item>
              <!-- Phase C: 管理员在下拉菜单中也可进入管理控制台 -->
              <el-dropdown-item
                v-if="auth.isAdmin"
                :icon="Setting"
                divided
                @click="goToAdmin"
              >
                进入管理控制台
              </el-dropdown-item>
              <el-dropdown-item divided @click="handleLogout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </el-header>

    <!-- ============ 主体 ============ -->
    <el-container class="body">
      <!-- 左侧二级标签 -->
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
        <router-view v-slot="{ Component, route }">
          <transition name="fade-slide" mode="out-in">
            <component :is="Component" :key="route.path" />
          </transition>
        </router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
/* ==================== 布局 ==================== */
.app-layout { min-height: 100vh; background: var(--color-bg); }

/* ==================== 顶部 ==================== */
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
.topbar-menu {
  border-bottom: none !important;
  background: transparent;
}
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

/* ==================== Phase C: 管理员入口 ==================== */
.admin-entry {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 4px 10px;
  margin-right: var(--space-1);
  border-radius: var(--radius-sm);
  background: rgba(245, 63, 63, 0.06);
  border: 1px solid rgba(245, 63, 63, 0.18);
}
.admin-badge {
  font-family: var(--font-sans);
  font-weight: var(--weight-semibold);
  letter-spacing: 0.08em;
}
.admin-console-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-weight: var(--weight-medium);
}
.admin-menu-item {
  --el-menu-hover-bg-color: rgba(245, 63, 63, 0.08);
}
.admin-menu-item :deep(.el-icon) {
  color: var(--el-color-danger);
}

/* ==================== 主体 ==================== */
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

/* ==================== 主区 ==================== */
.main {
  background: var(--color-bg);
  padding: var(--space-4) var(--space-4);
  overflow-y: auto;
}

/* ==================== 过渡 ==================== */
/* Phase E.1: 路由切换 fade-slide - 新页面上滑入场,旧页面下滑离场 */
.fade-slide-enter-active,
.fade-slide-leave-active {
  transition: all 0.3s ease;
}
.fade-slide-enter-from {
  opacity: 0;
  transform: translateY(16px);
}
.fade-slide-leave-to {
  opacity: 0;
  transform: translateY(-16px);
}
/* Phase E.1: 菜单 hover/active 底部 2px 蓝色横线 */
:deep(.el-menu-item) {
  position: relative;
  transition: color 0.2s;
}
:deep(.el-menu-item::after) {
  content: '';
  position: absolute;
  bottom: 0;
  left: 50%;
  width: 0;
  height: 2px;
  background: var(--color-accent, #2563EB);
  transition: all 0.2s ease;
  transform: translateX(-50%);
}
:deep(.el-menu-item:hover::after),
:deep(.el-menu-item.is-active::after) {
  width: 80%;
}

@media (max-width: 900px) {
  .topbar-menu { display: none; }
  .side { width: 180px !important; }
}
</style>
