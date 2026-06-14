<script setup lang="ts">
/**
 * LoginView - 登录/注册双 Tab
 */
import { reactive, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const tab = ref<'login' | 'register'>('login')
const loading = ref(false)

const loginForm = reactive({ username: '', password: '' })
const regForm = reactive({ username: '', email: '', password: '', confirm: '' })

const loginRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}
const regRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 32, message: '长度 3-32', trigger: 'blur' },
  ],
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '邮箱格式不正确', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '至少 6 位', trigger: 'blur' },
  ],
  confirm: [
    { required: true, message: '请再次输入密码', trigger: 'blur' },
    {
      validator: (_: any, v: string, cb: any) => v === regForm.password ? cb() : cb(new Error('两次密码不一致')),
      trigger: 'blur',
    },
  ],
}

const loginFormRef = ref()
const regFormRef = ref()

async function doLogin() {
  if (!loginFormRef.value) return
  await loginFormRef.value.validate(async (valid: boolean) => {
    if (!valid) return
    loading.value = true
    try {
      await auth.login(loginForm.username, loginForm.password)
      ElMessage.success('登录成功')
      const redirect = (route.query.redirect as string) || (auth.isAdmin ? '/admin' : '/app')
      router.replace(redirect)
    } catch (e: any) {
      ElMessage.error(e?.response?.data?.detail || '登录失败')
    } finally {
      loading.value = false
    }
  })
}

async function doRegister() {
  if (!regFormRef.value) return
  await regFormRef.value.validate(async (valid: boolean) => {
    if (!valid) return
    loading.value = true
    try {
      await auth.register(regForm.username, regForm.email, regForm.password)
      ElMessage.success('注册成功，已自动登录')
      const redirect = (route.query.redirect as string) || (auth.isAdmin ? '/admin' : '/app')
      router.replace(redirect)
    } catch (e: any) {
      ElMessage.error(e?.response?.data?.detail || '注册失败')
    } finally {
      loading.value = false
    }
  })
}
</script>

<template>
  <div class="login-page">
    <el-card class="login-card" shadow="always">
      <div class="title">
        <h2>卫星图像分析平台</h2>
        <p class="subtitle">基于 EfficientNetV2-M · EuroSAT 10 类土地利用分类</p>
      </div>
      <el-tabs v-model="tab" class="tabs">
        <!-- ============ 登录 ============ -->
        <el-tab-pane label="登录" name="login">
          <el-form ref="loginFormRef" :model="loginForm" :rules="loginRules" label-position="top" @keyup.enter="doLogin">
            <el-form-item label="用户名" prop="username">
              <el-input v-model="loginForm.username" placeholder="请输入用户名" />
            </el-form-item>
            <el-form-item label="密码" prop="password">
              <el-input v-model="loginForm.password" type="password" show-password placeholder="请输入密码" />
            </el-form-item>
            <el-button type="primary" :loading="loading" class="submit" @click="doLogin">登录</el-button>
          </el-form>
        </el-tab-pane>
        <!-- ============ 注册 ============ -->
        <el-tab-pane label="注册" name="register">
          <el-form ref="regFormRef" :model="regForm" :rules="regRules" label-position="top" @keyup.enter="doRegister">
            <el-form-item label="用户名（3-32 位）" prop="username">
              <el-input v-model="regForm.username" placeholder="请输入用户名" />
            </el-form-item>
            <el-form-item label="邮箱" prop="email">
              <el-input v-model="regForm.email" placeholder="请输入邮箱" />
            </el-form-item>
            <el-form-item label="密码（≥ 6 位）" prop="password">
              <el-input v-model="regForm.password" type="password" show-password />
            </el-form-item>
            <el-form-item label="确认密码" prop="confirm">
              <el-input v-model="regForm.confirm" type="password" show-password />
            </el-form-item>
            <el-button type="primary" :loading="loading" class="submit" @click="doRegister">注册并登录</el-button>
            <p class="hint">注：首个注册的账户自动成为管理员。</p>
          </el-form>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<style scoped>
.login-page { min-height: 100vh; display: flex; align-items: center; justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
.login-card { width: 420px; max-width: 90vw; }
.title { text-align: center; margin-bottom: 16px; }
.title h2 { margin: 0 0 8px 0; color: #303133; }
.subtitle { color: #909399; font-size: 12px; margin: 0; }
.tabs { margin-top: 8px; }
.submit { width: 100%; margin-top: 8px; }
.hint { color: #909399; font-size: 12px; margin-top: 12px; text-align: center; }
</style>
