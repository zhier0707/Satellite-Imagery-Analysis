<script setup lang="ts">
/**
 * UserManageView - 用户管理
 */
import { onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAdminStore } from '@/stores/admin'
import type { UserOut } from '@/api'

const admin = useAdminStore()

const refresh = () => admin.fetchUsers()

onMounted(refresh)

const onToggleRole = async (u: UserOut) => {
  const newRole = u.role === 'admin' ? 'user' : 'admin'
  try {
    await ElMessageBox.confirm(`将 ${u.username} 的角色从 ${u.role} 改为 ${newRole}?`, '提示')
    await admin.updateUser(u.id, { role: newRole })
    ElMessage.success('已更新')
  } catch {}
}

const onToggleActive = async (u: UserOut) => {
  try {
    await ElMessageBox.confirm(`${u.is_active ? '停用' : '启用'} ${u.username}?`, '提示')
    await admin.updateUser(u.id, { is_active: !u.is_active })
    ElMessage.success('已更新')
  } catch {}
}

const onDelete = async (u: UserOut) => {
  try {
    await ElMessageBox.confirm(`确定删除（软删） ${u.username}?`, '危险操作', { type: 'warning' })
    await admin.deleteUser(u.id)
    ElMessage.success('已停用')
  } catch {}
}

const asUser = (row: any): UserOut => row as UserOut
</script>

<template>
  <el-card shadow="hover">
    <template #header>
      <span>用户管理</span>
      <el-button text @click="refresh" style="float: right">刷新</el-button>
    </template>
    <el-table :data="admin.users" border v-loading="admin.loading" empty-text="暂无用户">
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="username" label="用户名" />
      <el-table-column prop="email" label="邮箱" />
      <el-table-column prop="role" label="角色" width="120">
        <template #default="{ row }">
          <el-tag :type="row.role === 'admin' ? 'danger' : 'info'" size="small">{{ row.role }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="is_active" label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'warning'" size="small">
            {{ row.is_active ? '活跃' : '停用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" min-width="180" />
      <el-table-column label="操作" width="320" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="onToggleRole(asUser(row))">
            改角色为 {{ (row as UserOut).role === 'admin' ? 'user' : 'admin' }}
          </el-button>
          <el-button size="small" :type="(row as UserOut).is_active ? 'warning' : 'success'" @click="onToggleActive(asUser(row))">
            {{ (row as UserOut).is_active ? '停用' : '启用' }}
          </el-button>
          <el-button size="small" type="danger" @click="onDelete(asUser(row))">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>
</template>
