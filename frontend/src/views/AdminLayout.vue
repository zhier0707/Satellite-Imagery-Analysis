<script setup lang="ts">
/**
 * AdminLayout - 管理端布局
 *
 * - 左侧 el-menu: 5 菜单项
 * - 顶部 el-header: 用户信息 + 退出
 * - 主区 <router-view />
 */
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessageBox, ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

interface AdminMenu { name: string; index: string; label: string; icon: string }
const menus: AdminMenu[] = [
  { name: 'users',    index: '/admin/users',    label: '用户管理', icon: 'User' },
  { name: 'records',  index: '/admin/records',  label: '全量记录', icon: 'Tickets' },
  { name: 'training', index: '/admin/training', label: '训练任务', icon: 'Cpu' },
  { name: 'convert',  index: '/admin/convert',  label: 'ONNX 转换', icon: 'Refresh' },
  { name: 'reports',  index: '/admin/reports',  label: '全部报表', icon: 'Document' },
]

const activeMenu = computed<string>(() => {
  for (const m of menus) if (route.path.startsWith(m.index)) return m.index
  return menus[0].index
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
    <el-aside width="220px" class="aside">
      <div class="logo">
        <span class="logo-icon">⚙️</span>
        <span class="logo-text">管理控制台</span>
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
          <h2>{{ menus.find((m) => m.index === activeMenu)?.label }}</h2>
        </div>
        <div class="header-right">
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
.admin-layout { min-height: 100vh; }
.aside { background: #1d1d1d; color: #fff; }
.logo { padding: 18px 16px; display: flex; gap: 8px; align-items: center; border-bottom: 1px solid #333; }
.logo-icon { font-size: 22px; }
.logo-text { font-weight: 600; }
.menu { background: #1d1d1d; border-right: none; }
:deep(.el-menu) { background: #1d1d1d; }
:deep(.el-menu-item) { color: rgba(255,255,255,.85); }
:deep(.el-menu-item.is-active) { background: #d4380d; color: #fff; }
:deep(.el-menu-item:hover) { background: #2a2a2a; }

.header { background: #fff; display: flex; align-items: center; justify-content: space-between;
  box-shadow: 0 1px 4px rgba(0,0,0,.08); padding: 0 24px; }
.header h2 { margin: 0; font-size: 18px; color: #303133; }
.header-right { display: flex; align-items: center; gap: 12px; }
.user-info { display: inline-flex; align-items: center; gap: 6px; cursor: pointer; padding: 4px 8px; }
.username { font-size: 14px; color: #303133; }
.main { background: #f0f2f5; padding: 24px; }
.fade-enter-active, .fade-leave-active { transition: opacity .15s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
