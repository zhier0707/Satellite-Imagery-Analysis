<script setup lang="ts">
/**
 * AppLayout - 用户端布局
 *
 * - 左侧 el-menu: 6 菜单项
 * - 顶部 el-header: 用户信息 + 退出
 * - 主区 <router-view />
 */
import { computed, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessageBox, ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const activeMenu = computed<string>(() => {
  // 找到子路由中第一个匹配的 name
  for (const m of menus) {
    if (m.children.some((c) => route.path.startsWith(c.path))) return m.name as string
  }
  return menus[0].name as string
})

interface MenuItem { name: string; index: string; label: string; icon: string; children: { path: string; label: string }[] }
const menus: MenuItem[] = [
  { name: 'upload',  index: '/app/upload',  label: '图像上传', icon: 'UploadFilled',    children: [{ path: '/app/upload',  label: '上传与识别' }] },
  { name: 'top5',    index: '/app/top5',    label: 'Top-5',  icon: 'ChatLineRound',   children: [{ path: '/app/top5',    label: '概率条' }] },
  { name: 'heatmap', index: '/app/heatmap', label: '热力图',  icon: 'PictureFilled',   children: [{ path: '/app/heatmap', label: 'Grad-CAM' }] },
  { name: 'stats',   index: '/app/stats',   label: '分类统计', icon: 'PieChart',        children: [{ path: '/app/stats',   label: '统计' }] },
  { name: 'change',  index: '/app/change',  label: '变化检测', icon: 'Refresh',         children: [{ path: '/app/change',  label: '时相对比' }] },
  { name: 'reports', index: '/app/reports', label: '我的报表', icon: 'Document',        children: [{ path: '/app/reports', label: '导出与下载' }] },
]

const handleSelect = (idx: string) => router.push(idx)

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

const drawerOpen = ref(false)
</script>

<template>
  <el-container class="app-layout">
    <el-aside width="220px" class="aside">
      <div class="logo">
        <span class="logo-icon">🛰️</span>
        <span class="logo-text">卫星图像分析</span>
      </div>
      <el-menu :default-active="activeMenu" class="menu" @select="handleSelect">
        <el-menu-item v-for="m in menus" :key="m.name" :index="m.index">
          <el-icon><component :is="m.icon" /></el-icon>
          <template #title>{{ m.label }}</template>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="header">
        <div class="header-left">
          <h2>{{ menus.find((m) => m.name === activeMenu)?.label }}</h2>
        </div>
        <div class="header-right">
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
                <el-dropdown-item divided @click="handleLogout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

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
.app-layout { min-height: 100vh; }
.aside { background: #001529; color: #fff; }
.logo { padding: 18px 16px; display: flex; gap: 8px; align-items: center; border-bottom: 1px solid #1f3247; }
.logo-icon { font-size: 22px; }
.logo-text { font-weight: 600; }
.menu { background: #001529; border-right: none; }
:deep(.el-menu) { background: #001529; }
:deep(.el-menu-item) { color: rgba(255,255,255,.85); }
:deep(.el-menu-item.is-active) { background: #1890ff; color: #fff; }
:deep(.el-menu-item:hover) { background: #002140; }

.header { background: #fff; display: flex; align-items: center; justify-content: space-between;
  box-shadow: 0 1px 4px rgba(0,21,41,.08); padding: 0 24px; }
.header h2 { margin: 0; font-size: 18px; color: #303133; }
.user-info { display: inline-flex; align-items: center; gap: 6px; cursor: pointer; padding: 4px 8px; }
.username { font-size: 14px; color: #303133; }

.main { background: #f0f2f5; padding: 24px; }

.fade-enter-active, .fade-leave-active { transition: opacity .15s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
