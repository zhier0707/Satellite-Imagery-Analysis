<script setup lang="ts">
/**
 * LoginView - 登录/注册双 Tab
 * ====================
 *
 * 视觉:
 *   - 双栏布局 (白底学术主题):
 *     左 1/3: SatelliteOrbitSvg 装饰 + 衬线大字标语
 *     右 2/3: 表单卡片
 *   - GSAP timeline 入场: 标语 fade-up → 表单 slide-in
 */
import { reactive, ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { gsap } from 'gsap'
import { useAuthStore } from '@/stores/auth'
import SatelliteOrbitSvg from '@/components/decor/SatelliteOrbitSvg.vue'

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

// ==================== 入场动效 ====================
const leftColRef = ref<HTMLElement | null>(null)
const rightColRef = ref<HTMLElement | null>(null)
const orbitRef = ref<InstanceType<typeof SatelliteOrbitSvg> | null>(null)

function prefersReducedMotion(): boolean {
  return window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
}

onMounted(() => {
  if (prefersReducedMotion()) return
  // 标语 fade-up + 表单 slide-in 串行
  const tl = gsap.timeline({ defaults: { ease: 'power2.out' } })
  if (leftColRef.value) {
    tl.fromTo(
      leftColRef.value.children,
      { opacity: 0, y: 20 },
      { opacity: 1, y: 0, duration: 0.6, stagger: 0.08 },
      0,
    )
  }
  if (rightColRef.value) {
    tl.fromTo(
      rightColRef.value,
      { opacity: 0, x: 24 },
      { opacity: 1, x: 0, duration: 0.5 },
      0.2,
    )
  }
})
</script>

<template>
  <div class="login-page">
    <!-- ============ 左侧 1/3 装饰栏 ============ -->
    <aside ref="leftColRef" class="login-aside">
      <SatelliteOrbitSvg ref="orbitRef" class="orbit-svg" />
      <div class="aside-text">
        <p class="kicker">SATELLITE · REMOTE SENSING</p>
        <h1 class="display">洞察地表<br />每一帧变化</h1>
        <p class="lede">
          基于 EfficientNetV2-M 与 EuroSAT 数据集的十类土地利用分类、Grad-CAM
          可解释性分析与时相变化检测。
        </p>
        <p class="hint">首个注册账号自动获得管理员权限。</p>
      </div>
    </aside>

    <!-- ============ 右侧 2/3 表单栏 ============ -->
    <main ref="rightColRef" class="login-main">
      <div class="form-wrap">
        <header class="form-head">
          <h2>欢迎回来</h2>
          <p>请登录以继续你的卫星图像分析任务。</p>
        </header>
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
              <el-button :loading="loading" class="is-accent submit" @click="doLogin">登录</el-button>
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
              <el-button :loading="loading" class="is-accent submit" @click="doRegister">注册并登录</el-button>
            </el-form>
          </el-tab-pane>
        </el-tabs>
        <footer class="form-foot">
          <span class="dim">登录即表示同意学术研究用途与隐私政策</span>
        </footer>
      </div>
    </main>
  </div>
</template>

<style scoped>
/* ==================== 布局 ==================== */
.login-page {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 1fr 2fr;
  background: var(--color-bg);
  color: var(--color-fg);
}

/* ==================== 左侧 ==================== */
.login-aside {
  position: relative;
  border-right: 1px solid var(--color-border);
  background: var(--color-bg-soft);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  padding: var(--space-4);
}
.orbit-svg {
  position: absolute;
  inset: 0;
  margin: auto;
  opacity: 0.85;
  pointer-events: none;
}
.aside-text {
  position: relative;
  z-index: 1;
  max-width: 480px;
  margin-top: auto;
}
.kicker {
  font-family: var(--font-sans);
  font-size: var(--text-small);
  letter-spacing: 0.18em;
  color: var(--color-accent);
  text-transform: uppercase;
  margin: 0 0 var(--space-2) 0;
  font-weight: var(--weight-medium);
}
.display {
  font-family: var(--font-serif);
  font-size: var(--text-display);
  line-height: 1.1;
  color: var(--color-fg);
  font-weight: var(--weight-semibold);
  letter-spacing: -0.015em;
  margin: 0;
}
.lede {
  margin: var(--space-3) 0 0 0;
  color: var(--color-fg-2);
  font-size: 15px;
  line-height: var(--line-loose);
  max-width: 420px;
}
.hint {
  margin: var(--space-3) 0 0 0;
  font-size: var(--text-small);
  color: var(--color-fg-3);
  font-family: var(--font-sans);
}

/* ==================== 右侧 ==================== */
.login-main {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-5) var(--space-4);
}
.form-wrap {
  width: 100%;
  max-width: 420px;
}
.form-head { margin-bottom: var(--space-3); }
.form-head h2 {
  font-family: var(--font-serif);
  font-size: var(--text-h1);
  color: var(--color-fg);
  margin: 0;
  font-weight: var(--weight-semibold);
}
.form-head p {
  margin: var(--space-1) 0 0 0;
  color: var(--color-fg-2);
  font-size: var(--text-body);
}
.tabs { margin-top: var(--space-1); }
.submit { width: 100%; margin-top: var(--space-2); }
.form-foot {
  margin-top: var(--space-3);
  padding-top: var(--space-2);
  border-top: 1px solid var(--color-border);
  text-align: center;
}
.dim { color: var(--color-fg-3); font-size: var(--text-small); }

/* ==================== 响应式 ==================== */
@media (max-width: 900px) {
  .login-page { grid-template-columns: 1fr; }
  .login-aside { display: none; }
}
</style>
