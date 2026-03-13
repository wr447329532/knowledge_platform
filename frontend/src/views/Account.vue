<template>
  <div class="settings-layout">
    <header class="settings-header">
      <div class="settings-header-left">
        <Icons name="drive" class="settings-logo" />
        <div>
          <h1 class="settings-title">账户设置</h1>
          <p class="settings-subtitle">管理您的个人信息和安全设置</p>
        </div>
      </div>
      <button type="button" class="settings-back-btn" @click="goBackHome">
        <Icons name="arrow-left" class="settings-back-icon" />
        返回
      </button>
    </header>

    <div class="settings-body">
      <aside class="settings-sidebar">
        <nav class="settings-nav">
          <button
            :class="['settings-nav-item', { active: activeTab === 'profile' }]"
            @click="activeTab = 'profile'"
          >
            <Icons name="user" class="settings-nav-icon" />
            个人信息
          </button>
          <button
            :class="['settings-nav-item', { active: activeTab === 'security' }]"
            @click="activeTab = 'security'"
          >
            <Icons name="lock" class="settings-nav-icon" />
            安全设置
          </button>
        </nav>
      </aside>

      <main class="settings-main">
        <!-- 个人信息 -->
        <div v-if="activeTab === 'profile'" class="settings-page">
          <div class="settings-card">
            <div class="settings-card-header">
              <div>
                <h2 class="settings-card-title">个人信息</h2>
                <p class="settings-card-desc">更新您的基本资料信息</p>
              </div>
            </div>
            <div class="settings-card-body">
              <div class="profile-avatar-row">
                <div class="profile-avatar">
                  <span>{{ initials }}</span>
                </div>
                <div>
                  <h3 class="profile-name">{{ profile.name || '-' }}</h3>
                  <p class="profile-dept">{{ profile.department || '未分配部门' }}</p>
                </div>
              </div>

              <div class="settings-form-grid">
                <div class="form-group">
                  <label>姓名</label>
                  <input v-model="profile.name" type="text" />
                </div>
                <div class="form-group">
                  <label>邮箱</label>
                  <input :value="profile.email" type="email" disabled class="input-disabled" />
                  <p class="form-hint">邮箱用于登录，不支持在此处修改，如需变更请联系管理员。</p>
                </div>
                <div class="form-group form-group-full">
                  <label>所属部门</label>
                  <input :value="profile.department || '未分配部门'" type="text" disabled class="input-disabled" />
                </div>
              </div>
            </div>
            <div class="settings-card-footer">
              <span v-if="profileSuccess" class="settings-success">{{ profileSuccess }}</span>
              <div class="settings-card-footer-actions">
                <button type="button" class="btn-outline" @click="resetProfile">
                  取消
                </button>
                <button type="button" class="btn-primary" @click="saveProfile">
                  保存更改
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- 安全设置 -->
        <div v-else class="settings-page">
          <div class="settings-card">
            <div class="settings-card-header">
              <div>
                <h2 class="settings-card-title">修改密码</h2>
                <p class="settings-card-desc">定期更换密码可以提高账户安全性</p>
              </div>
            </div>
            <div class="settings-card-body">
              <div class="settings-form-grid">
                <div class="form-group form-group-full">
                  <label>当前密码</label>
                  <input
                    v-model="password.oldPassword"
                    :type="showOld ? 'text' : 'password'"
                  />
                </div>
                <div class="form-group form-group-full">
                  <label>新密码</label>
                  <input
                    v-model="password.newPassword"
                    :type="showNew ? 'text' : 'password'"
                  />
                  <p class="form-hint">密码长度至少 8 位，包含大小写字母、数字和特殊字符。</p>
                </div>
                <div class="form-group form-group-full">
                  <label>确认新密码</label>
                  <input
                    v-model="password.confirmPassword"
                    :type="showConfirm ? 'text' : 'password'"
                  />
                </div>
              </div>
            </div>
            <div class="settings-card-footer">
              <button type="button" class="btn-primary" @click="changePassword">
                修改密码
              </button>
            </div>
          </div>

          <div class="settings-card">
            <div class="settings-card-header">
              <div>
                <h2 class="settings-card-title">安全信息</h2>
              </div>
            </div>
            <div class="settings-card-body">
              <div class="security-row">
                <div>
                  <p class="security-label">账户状态</p>
                  <p class="security-text">您的账户安全状态良好</p>
                </div>
                <span class="security-badge">正常</span>
              </div>
              <div class="security-row">
                <div>
                  <p class="security-label">上次登录时间</p>
                  <p class="security-text">——</p>
                </div>
              </div>
              <div class="security-row">
                <div>
                  <p class="security-label">上次修改密码</p>
                  <p class="security-text">——</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import * as api from '../api/client'
import Icons from '../components/Icons.vue'

const router = useRouter()

const activeTab = ref('profile')
const profile = ref({
  name: '',
  email: '',
  department: '',
})

const originalProfile = ref(null)

const password = ref({
  oldPassword: '',
  newPassword: '',
  confirmPassword: '',
})

const showOld = ref(false)
const showNew = ref(false)
const showConfirm = ref(false)
const err = ref('')
const profileSuccess = ref('')

const initials = computed(() => {
  if (profile.value.name) return profile.value.name.slice(0, 2)
  if (profile.value.email) return profile.value.email[0].toUpperCase()
  return '?'
})

function goBackHome() {
  router.push('/')
}

async function loadMe() {
  const me = await api.getMe()
  profile.value = {
    name: me.username || '',
    email: me.email || '',
    department: me.department_name || '',
  }
  originalProfile.value = { ...profile.value }
}

function resetProfile() {
  if (originalProfile.value) {
    profile.value = { ...originalProfile.value }
  }
  err.value = ''
  profileSuccess.value = ''
}

async function saveProfile() {
  err.value = ''
  try {
    await api.updateMe({ name: profile.value.name })
    // 重新拉取一次后端的 me，确保展示与服务器一致
    await loadMe()
    profileSuccess.value = '个人信息已保存'
    alert('个人信息已保存')
    setTimeout(() => {
      profileSuccess.value = ''
    }, 2000)
  } catch (e) {
    err.value = e.message || '保存失败'
  }
}

async function changePassword() {
  err.value = ''
  if (!password.value.oldPassword || !password.value.newPassword || !password.value.confirmPassword) {
    err.value = '请完整填写当前密码和新密码。'
    return
  }
  if (password.value.newPassword !== password.value.confirmPassword) {
    err.value = '两次输入的新密码不一致。'
    return
  }
  try {
    await api.changePassword(password.value.oldPassword, password.value.newPassword)
    password.value = { oldPassword: '', newPassword: '', confirmPassword: '' }
    alert('密码修改成功，请使用新密码重新登录。')
  } catch (e) {
    err.value = e.message || '修改密码失败'
  }
}

onMounted(() => {
  loadMe()
})
</script>

<style scoped>
.settings-layout {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  background: #f3f4f6;
}

.settings-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 24px;
  background: #fff;
  border-bottom: 1px solid var(--border);
}

.settings-header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.settings-logo {
  width: 32px;
  height: 32px;
}

.settings-title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
}

.settings-subtitle {
  margin: 2px 0 0;
  font-size: 12px;
  color: #6b7280;
}

.settings-back-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 999px;
  border: 1px solid #d1d5db;
  background: #fff;
  font-size: 13px;
  cursor: pointer;
}

.settings-back-icon {
  width: 16px;
  height: 16px;
}

.settings-body {
  display: flex;
  max-width: 1120px;
  margin: 16px auto;
  gap: 16px;
  padding: 0 16px 24px;
  width: 100%;
}

.settings-sidebar {
  width: 220px;
}

.settings-nav {
  background: #fff;
  border-radius: 12px;
  border: 1px solid #e5e7eb;
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.settings-nav-item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 8px 10px;
  border-radius: 8px;
  border: none;
  background: transparent;
  cursor: pointer;
  font-size: 14px;
  color: #374151;
}

.settings-nav-item.active {
  background: #4a90e2;
  color: #fff;
}

.settings-nav-icon {
  width: 16px;
  height: 16px;
}

.settings-main {
  flex: 1;
}

.settings-page {
  max-width: 720px;
}

.settings-card {
  background: #fff;
  border-radius: 12px;
  border: 1px solid #e5e7eb;
  margin-bottom: 16px;
  overflow: hidden;
}

.settings-card-header {
  padding: 16px 20px;
  border-bottom: 1px solid #e5e7eb;
}

.settings-card-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}

.settings-card-desc {
  margin: 4px 0 0;
  font-size: 13px;
  color: #6b7280;
}

.settings-card-body {
  padding: 16px 20px 12px;
}

.settings-card-footer {
  padding: 12px 20px 16px;
  border-top: 1px solid #e5e7eb;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.settings-card-footer-actions {
  display: flex;
  gap: 8px;
}

.settings-success {
  font-size: 13px;
  color: #16a34a;
}

.profile-avatar-row {
  display: flex;
  align-items: center;
  gap: 16px;
  padding-bottom: 16px;
  border-bottom: 1px solid #e5e7eb;
  margin-bottom: 16px;
}

.profile-avatar {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background: linear-gradient(135deg, #4a90e2, #357abd);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 20px;
  font-weight: 600;
}

.profile-name {
  margin: 0 0 2px;
  font-size: 16px;
  font-weight: 600;
}

.profile-dept {
  margin: 0;
  font-size: 13px;
  color: #6b7280;
}

.settings-form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-group-full {
  grid-column: 1 / -1;
}

label {
  font-size: 13px;
  color: #374151;
}

input {
  padding: 8px 10px;
  border-radius: 8px;
  border: 1px solid #d1d5db;
  font-size: 14px;
}

.input-disabled {
  background: #f9fafb;
  color: #9ca3af;
}

.form-hint {
  font-size: 12px;
  color: #9ca3af;
}

.btn-primary {
  padding: 8px 14px;
  border-radius: 999px;
  border: none;
  background: #4a90e2;
  color: #fff;
  font-size: 13px;
  cursor: pointer;
}

.btn-primary:hover {
  background: #357abd;
}

.btn-outline {
  padding: 8px 14px;
  border-radius: 999px;
  border: 1px solid #d1d5db;
  background: #fff;
  font-size: 13px;
  cursor: pointer;
}

.security-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 0;
}

.security-label {
  margin: 0 0 2px;
  font-size: 14px;
  font-weight: 500;
}

.security-text {
  margin: 0;
  font-size: 12px;
  color: #6b7280;
}

.security-badge {
  padding: 2px 10px;
  border-radius: 999px;
  background: #dcfce7;
  color: #166534;
  font-size: 12px;
}

.text-danger {
  margin: 0 20px 8px;
  font-size: 13px;
  color: #b91c1c;
}
</style>

