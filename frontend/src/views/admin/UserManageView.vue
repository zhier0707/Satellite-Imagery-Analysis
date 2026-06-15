<script setup lang="ts">
/**
 * UserManageView - 用户管理
 * ====================
 *
 * 视觉: PageHeader + LoadingSkeleton + 统一表格
 */
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { useAdminStore } from '@/stores/admin'
import type { UserOut } from '@/api'
import { usePageEnter } from '@/composables/usePageEnter'

const sectionRef = ref<HTMLElement | null>(null)
usePageEnter(sectionRef)

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
  <section ref="sectionRef" class="user-manage-view">
    <PageHeader
      title="用户管理"
      subtitle="管理注册用户：改角色、停用/启用、软删除。"
    >
      <template #actions>
        <el-button :icon="Refresh" :loading="admin.loading" class="is-accent" @click="refresh">刷新</el-button>
      </template>
    </PageHeader>

    <el-card v-if="admin.loading && !admin.users.length" shadow="never">
      <LoadingSkeleton :rows="5" :avatar="true" />
    </el-card>

    <el-card v-else shadow="never">
      <el-table :data="admin.users" border v-loading="admin.loading" empty-text="暂无用户">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="username" label="用户名" min-width="140" />
        <el-table-column prop="email" label="邮箱" min-width="200" />
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
  </section>
</template>

<style scoped>
.user-manage-view { max-width: 1280px; margin: 0 auto; }
</style>
