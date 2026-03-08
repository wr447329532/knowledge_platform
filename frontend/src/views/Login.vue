<template>
  <div class="login-page">
    <!-- 左侧品牌区：仅平台名称居中 + 背景图 -->
    <div class="login-left">
      <div class="login-left-bg">
        <img src="https://images.unsplash.com/photo-1674981208693-de5a9c4c4f44?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&q=80&w=1080" alt="" class="login-bg-img" />
        <div class="login-bg-overlay"></div>
      </div>
      <div class="login-brand-center">
        <h1 class="brand-title">文件共享和知识平台</h1>
      </div>
    </div>
    <!-- 右侧登录表单 -->
    <div class="login-right">
      <div class="login-form-wrap">
        <h2 class="form-title">欢迎登录</h2>
        <p class="form-subtitle">请输入您的账号信息</p>
        <form @submit.prevent="submit" class="login-form">
          <div class="form-field">
            <label>用户名</label>
            <div class="input-wrap">
              <Icons name="user" class="input-icon" />
              <input v-model="username" placeholder="请输入用户名" required />
            </div>
          </div>
          <div class="form-field">
            <label>密码</label>
            <div class="input-wrap">
              <Icons name="lock" class="input-icon" />
              <input :type="showPwd ? 'text' : 'password'" v-model="password" placeholder="请输入密码" required />
              <Icons :name="showPwd ? 'eye-off' : 'eye'" class="input-icon input-icon-right" :clickable="true" @click="showPwd = !showPwd" />
            </div>
          </div>
          <div class="form-options">
            <label class="form-checkbox"><input type="checkbox" v-model="rememberMe" /> 记住登录状态</label>
            <a href="#" class="form-link" @click.prevent>忘记密码?</a>
          </div>
          <p v-if="error" class="form-error">{{ error }}</p>
          <button type="submit" class="form-btn primary">登录</button>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { login } from '../api/client'
import Icons from '../components/Icons.vue'

const router = useRouter()
const username = ref('')
const password = ref('')
const error = ref('')
const showPwd = ref(false)
const rememberMe = ref(false)

async function submit() {
  error.value = ''
  try {
    await login(username.value, password.value)
    router.push('/')
  } catch (e) {
    error.value = e.message || '登录失败'
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
}
.login-left {
  flex: 1;
  position: relative;
  overflow: hidden;
}
.login-left-bg {
  position: absolute;
  inset: 0;
}
.login-bg-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  opacity: 0.3;
}
.login-bg-overlay {
  position: absolute;
  inset: 0;
  background: linear-gradient(135deg, rgba(26,31,58,0.9) 0%, rgba(45,53,97,0.75) 50%, rgba(26,31,58,0.9) 100%);
}
.login-brand-center {
  position: relative;
  z-index: 1;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px;
}
.brand-title { color: #fff; font-size: 36px; font-weight: 700; margin: 0; text-align: center; }
.login-right {
  width: 520px;
  background: #f9fafb;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px;
}
.login-form-wrap {
  width: 100%;
  max-width: 400px;
  background: #fff;
  border-radius: 16px;
  box-shadow: 0 4px 24px rgba(0,0,0,0.1);
  padding: 40px;
}
.form-title { font-size: 24px; font-weight: 600; color: #111; margin: 0 0 8px 0; }
.form-subtitle { font-size: 14px; color: #6b7280; margin: 0 0 32px 0; }
.form-field { margin-bottom: 20px; }
.form-field label { display: block; font-size: 14px; font-weight: 500; color: #374151; margin-bottom: 8px; }
.input-wrap {
  display: flex;
  align-items: center;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #f9fafb;
  padding: 0 12px;
  transition: border-color 0.2s, background 0.2s;
}
.input-wrap:focus-within {
  border-color: var(--primary);
  background: #fff;
  box-shadow: 0 0 0 2px rgba(74,144,226,0.2);
}
.input-wrap input {
  flex: 1;
  border: none;
  padding: 12px 10px;
  font-size: 14px;
  background: transparent;
}
.input-wrap input:focus { outline: none; }
.input-icon { width: 20px; height: 20px; color: #9ca3af; flex-shrink: 0; }
.input-icon-right { margin-left: 8px; cursor: pointer; }
.form-options { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.form-checkbox { font-size: 14px; color: #6b7280; cursor: pointer; display: flex; align-items: center; gap: 8px; }
.form-checkbox input { margin: 0; }
.form-link { font-size: 14px; color: #4a90e2; text-decoration: none; }
.form-link:hover { text-decoration: underline; color: #357abd; }
.form-error { color: var(--danger); font-size: 14px; margin: 0 0 12px 0; }
.form-btn {
  width: 100%;
  padding: 12px 16px;
  font-size: 16px;
  font-weight: 500;
  border: none;
  border-radius: 8px;
  cursor: pointer;
}
.form-btn.primary {
  background: linear-gradient(90deg, #4a90e2, #357abd);
  color: #fff;
  box-shadow: 0 4px 14px rgba(74,144,226,0.4);
}
.form-btn.primary:hover {
  background: linear-gradient(90deg, #357abd, #2d6ba8);
  box-shadow: 0 6px 20px rgba(74,144,226,0.5);
}
</style>
