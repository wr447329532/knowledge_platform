<template>
  <aside class="app-sidebar">
    <!-- Logo -->
    <div class="sidebar-logo">
      <Icons name="drive" class="logo-icon" />
      <span class="logo-text">文件共享和知识管理平台</span>
    </div>

    <!-- 存储空间 -->
    <div class="sidebar-storage">
      <div class="storage-label">存储空间</div>
      <div class="storage-value">
        <span class="storage-used">{{ storageStats?.used_display || '0 B' }}</span>
        <span class="storage-total">/ {{ storageStats?.total_display || '500 GB' }}</span>
      </div>
      <div class="storage-bar">
        <div class="storage-fill" :style="{ width: Math.min((storageStats?.percent || 0), 100) + '%' }"></div>
      </div>
    </div>

    <!-- 主导航 -->
    <nav class="sidebar-nav">
      <a
        :class="['nav-item', { active: activeTab === 'lib' && !activeDeptId }]"
        href="#"
        @click.prevent="emit('nav', 'lib')"
      >
        <Icons name="folder" class="nav-icon" />
        <span>我的文件库</span>
      </a>
      <a
        :class="['nav-item', { active: activeTab === 'shared' }]"
        href="#"
        @click.prevent="emit('nav', 'shared')"
      >
        <Icons name="share" class="nav-icon" />
        <span>共享文件</span>
      </a>
      <a
        :class="['nav-item', { active: activeTab === 'trash' }]"
        href="#"
        @click.prevent="emit('nav', 'trash')"
      >
        <Icons name="trash" class="nav-icon" />
        <span>回收站</span>
      </a>
    </nav>

    <!-- 部门树 -->
    <div class="sidebar-dept">
      <DepartmentTree :me="me" :active-dept-id="activeDeptId" @select="emit('dept-select', $event)" />
    </div>

    <div class="sidebar-spacer"></div>

    <!-- 底部导航 -->
    <div class="sidebar-bottom">
      <button class="nav-item" @click="emit('account')">
        <Icons name="user" class="nav-icon" />
        <span>账户</span>
      </button>
      <button v-if="me?.is_superuser" class="nav-item" @click="emit('go-admin')">
        <Icons name="settings" class="nav-icon" />
        <span>系统管理</span>
      </button>
    </div>

    <!-- 用户信息 -->
    <div class="sidebar-user">
      <div class="user-avatar">{{ me?.username?.[0] || '?' }}</div>
      <div class="user-info">
        <span class="user-name">{{ me?.username }}</span>
        <div class="user-actions">
          <button @click="emit('logout')" class="user-btn">退出</button>
        </div>
      </div>
    </div>
  </aside>
</template>

<script setup>
import Icons from './Icons.vue'
import DepartmentTree from './DepartmentTree.vue'

defineProps({
  me: Object,
  activeTab: String,
  activeDeptId: { type: Number, default: null },
  storageStats: Object,
})

const emit = defineEmits(['nav', 'dept-select', 'go-admin', 'account', 'logout'])
</script>

<style scoped>
.app-sidebar {
  width: var(--sidebar-width);
  height: 100vh;
  background: var(--sidebar-bg);
  color: var(--sidebar-text);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  overflow: hidden;
}
.sidebar-logo {
  height: 56px;
  display: flex;
  align-items: center;
  padding: 0 24px;
  border-bottom: 1px solid rgba(75,85,99,0.5);
  flex-shrink: 0;
}
.logo-icon { width: 28px; height: 28px; font-size: 28px; color: var(--sidebar-accent); }
.logo-text { margin-left: 12px; font-size: 14px; font-weight: 600; line-height: 1.3; }
.sidebar-storage {
  padding: 16px 24px;
  border-bottom: 1px solid rgba(75,85,99,0.5);
  flex-shrink: 0;
}
.storage-label { font-size: 12px; color: rgba(156,163,175); margin-bottom: 6px; }
.storage-value { display: flex; align-items: baseline; gap: 6px; margin-bottom: 6px; }
.storage-used { font-size: 20px; font-weight: 600; }
.storage-total { font-size: 12px; color: rgba(156,163,175); }
.storage-bar {
  width: 100%;
  height: 6px;
  background: rgba(75,85,99);
  border-radius: 999px;
  overflow: hidden;
}
.storage-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--sidebar-accent), #357abd);
  border-radius: 999px;
  transition: width 0.3s;
}
.sidebar-nav {
  padding: 12px;
  border-bottom: 1px solid rgba(75,85,99,0.5);
  flex-shrink: 0;
}
.sidebar-nav .nav-item { margin-bottom: 2px; }
.sidebar-nav .nav-item:last-child { margin-bottom: 0; }
.sidebar-dept {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 12px;
  border-bottom: 1px solid rgba(75,85,99,0.5);
}
.sidebar-spacer { flex: 0; min-height: 0; }
.sidebar-bottom {
  padding: 12px;
  border-top: 1px solid rgba(75,85,99,0.5);
  flex-shrink: 0;
}
.sidebar-bottom .nav-item { margin-bottom: 2px; }
.sidebar-bottom .nav-item:last-child { margin-bottom: 0; }
.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
  color: rgba(209,213,219);
  text-decoration: none;
  font-size: 14px;
  font-weight: 500;
  border: none;
  background: none;
  width: 100%;
  text-align: left;
  cursor: pointer;
  border-radius: 8px;
  transition: background 0.2s, color 0.2s;
}
.nav-item:hover { background: rgba(75,85,99,0.5); color: #fff; }
.nav-item.active { background: var(--sidebar-accent); color: #fff; }
.nav-icon { width: 16px; height: 16px; font-size: 16px; flex-shrink: 0; opacity: 0.9; }
.sidebar-user {
  padding: 12px 24px;
  border-top: 1px solid rgba(75,85,99,0.5);
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}
.user-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--sidebar-accent), #357abd);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
  flex-shrink: 0;
}
.user-info { flex: 1; min-width: 0; }
.user-name { display: block; font-size: 14px; font-weight: 500; }
.user-actions { display: flex; gap: 8px; margin-top: 4px; }
.user-btn {
  background: none;
  border: none;
  color: var(--sidebar-text-muted);
  padding: 0;
  font-size: 12px;
  cursor: pointer;
}
.user-btn:hover { color: var(--sidebar-text); text-decoration: underline; }
</style>
