<template>
  <header class="app-topbar">
    <!-- 第一行：搜索 + 右侧全局操作 -->
    <div class="app-topbar-row">
      <div class="search-box">
        <Icons name="search" class="search-icon" />
        <input
          :value="searchKeyword"
          type="text"
          placeholder="搜索文件、文件夹..."
          class="search-input"
          @input="emit('update:searchKeyword', $event.target.value)"
          @keyup.enter="emit('search')"
        />
      </div>
      <div class="topbar-actions">
        <template v-if="activeTab === 'lib'">
          <button v-if="!currentLib" class="btn-primary" @click="emit('new-lib')">
            + 新建文件库
          </button>
          <button v-else-if="currentLib?.is_writeable" class="btn-primary" @click="emit('upload')">
            + 新建
          </button>
        </template>
        <button
          type="button"
          class="notify-btn"
          @click="emit('toggle-notify')"
          title="通知"
        >
          <Icons name="bell" class="notify-icon" />
          <span v-if="notifyCount > 0" class="notify-dot">{{ notifyCount }}</span>
        </button>
        <div class="user-menu-wrap" ref="userMenuWrapRef">
          <button
            type="button"
            class="user-avatar-btn"
            :title="me?.username || '用户'"
            @click="toggleUserMenu"
          >
            {{ avatarLetter }}
          </button>
          <Transition name="dropdown">
            <div
              v-if="userMenuOpen"
              ref="userDropdownRef"
              class="user-dropdown"
              role="menu"
            >
              <div class="user-dropdown-head">
                <div class="user-dropdown-name">{{ me?.username || '-' }}</div>
                <div class="user-dropdown-email">{{ me?.email || '-' }}</div>
              </div>
              <div class="user-dropdown-divider" />
              <div class="user-dropdown-item" role="menuitem" @click="onGoAccount">账户管理</div>
              <div
                v-if="me?.is_superuser"
                class="user-dropdown-item"
                role="menuitem"
                @click="onGoAdmin"
              >
                系统管理
              </div>
              <div
                v-if="showDeptManage"
                class="user-dropdown-item"
                role="menuitem"
                @click="onGoDeptManage"
              >
                部门管理
              </div>
              <div class="user-dropdown-divider" />
              <div class="user-dropdown-item user-dropdown-logout" role="menuitem" @click="onLogout">
                退出登录
              </div>
            </div>
          </Transition>
        </div>
      </div>
    </div>

    <!-- 第二行：面包屑 + 视图切换（仅我的文件库，非部门视图） -->
    <div v-if="activeTab === 'lib' && !activeDeptId" class="file-toolbar file-toolbar-topbar">
      <div class="file-toolbar-left">
        <span class="file-breadcrumb-item">文件库</span>
        <template v-if="currentLib">
          <span class="file-breadcrumb-sep">/</span>
          <a href="#" @click.prevent="emit('clear-lib')" class="file-breadcrumb-link">{{ currentLib?.name }}</a>
          <template v-for="(seg, i) in breadcrumbSegments" :key="i">
            <span class="file-breadcrumb-sep">/</span>
            <a v-if="seg.path !== undefined" href="#" @click.prevent="emit('set-path', seg.path)" class="file-breadcrumb-link">{{ seg.label }}</a>
            <span v-else class="file-breadcrumb-current">{{ seg.label }}</span>
          </template>
        </template>
        <template v-else>
          <span class="file-breadcrumb-sep">/</span>
          <span class="file-breadcrumb-current">全部文件</span>
        </template>
      </div>
      <div class="file-toolbar-right">
        <select :value="fileSortOrder" class="file-sort-select" @change="emit('update:fileSortOrder', $event.target.value)">
          <option value="modified">最近修改</option>
          <option value="name">文件名</option>
          <option value="size">文件大小</option>
          <option value="created">创建时间</option>
        </select>
        <div class="file-view-toggle">
          <button type="button" :class="['file-view-btn', { active: fileViewMode === 'list' }]" @click="emit('update:fileViewMode', 'list')" title="列表">
            <Icons name="list" class="file-view-icon" />
          </button>
          <button type="button" :class="['file-view-btn', { active: fileViewMode === 'grid' }]" @click="emit('update:fileViewMode', 'grid')" title="网格">
            <Icons name="layout-grid" class="file-view-icon" />
          </button>
        </div>
      </div>
    </div>
  </header>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import Icons from './Icons.vue'

const props = defineProps({
  activeTab: String,
  activeDeptId: { type: Number, default: null },
  currentLib: Object,
  searchKeyword: String,
  fileSortOrder: String,
  fileViewMode: String,
  breadcrumbSegments: Array,
  notifyCount: { type: Number, default: 0 },
  me: { type: Object, default: null },
})

const emit = defineEmits([
  'update:searchKeyword', 'update:fileSortOrder', 'update:fileViewMode',
  'search', 'new-lib', 'upload', 'clear-lib', 'set-path', 'toggle-notify',
  'go-account', 'go-admin', 'go-dept-manage', 'logout',
])

const userMenuWrapRef = ref(null)
const userDropdownRef = ref(null)
const userMenuOpen = ref(false)

const avatarLetter = computed(() => {
  const name = props.me?.username || ''
  if (!name) return '?'
  const first = name.trim()[0]
  if (/[\u4e00-\u9fa5]/.test(first)) return first
  return (first || '?').toUpperCase()
})

const showDeptManage = computed(() => {
  const m = props.me
  if (!m) return false
  if (m.role === 'dept_leader') return true
  return !!m.is_department_leader
})

function toggleUserMenu() {
  userMenuOpen.value = !userMenuOpen.value
}

function closeUserMenu() {
  userMenuOpen.value = false
}

function onGoAccount() {
  closeUserMenu()
  emit('go-account')
}
function onGoAdmin() {
  closeUserMenu()
  emit('go-admin')
}
function onGoDeptManage() {
  closeUserMenu()
  emit('go-dept-manage')
}
function onLogout() {
  closeUserMenu()
  emit('logout')
}

function onDocumentClick(e) {
  const wrap = userMenuWrapRef.value
  const dropdown = userDropdownRef.value
  if (wrap && wrap.contains(e.target)) return
  if (dropdown && dropdown.contains(e.target)) return
  closeUserMenu()
}

onMounted(() => {
  document.addEventListener('click', onDocumentClick)
})
onUnmounted(() => {
  document.removeEventListener('click', onDocumentClick)
})
</script>

<style scoped>
.app-topbar {
  background: #fff;
  border-bottom: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 8px 24px 10px;
}
.app-topbar-row {
  display: flex;
  align-items: center;
  gap: 20px;
}
.search-box {
  flex: 1;
  max-width: 480px;
  display: flex;
  align-items: center;
  gap: 8px;
  background: #f5f6f8;
  border-radius: var(--radius);
  padding: 0 14px;
  height: 40px;
}
.search-icon { width: 18px; height: 18px; font-size: 18px; color: #999; flex-shrink: 0; }
.search-input { flex: 1; border: none; background: transparent; font-size: 14px; padding: 0; }
.search-input:focus { outline: none; }
.topbar-actions { margin-left: auto; display: flex; align-items: center; gap: 12px; }
.notify-btn {
  position: relative;
  border: none;
  background: transparent;
  padding: 6px;
  border-radius: 999px;
  cursor: pointer;
  color: #6b7280;
}
.notify-btn:hover {
  background: #f3f4f6;
  color: #111827;
}
.notify-icon {
  width: 18px;
  height: 18px;
}
.notify-dot {
  position: absolute;
  top: 2px;
  right: 2px;
  min-width: 18px;
  padding: 0 4px;
  height: 16px;
  border-radius: 999px;
  background: #ef4444;
  color: #ffffff;
  font-size: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.user-menu-wrap {
  position: relative;
}
.user-avatar-btn {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border: none;
  background: #4a90e2;
  color: #fff;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
}
.user-avatar-btn:hover {
  background: #357abd;
}
.user-dropdown {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  min-width: 180px;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  z-index: 999;
  overflow: hidden;
}
.user-dropdown-head {
  padding: 12px 16px;
}
.user-dropdown-name {
  font-size: 14px;
  font-weight: 500;
  color: #111827;
}
.user-dropdown-email {
  font-size: 12px;
  color: #6b7280;
  margin-top: 2px;
}
.user-dropdown-divider {
  height: 1px;
  background: #e5e7eb;
}
.user-dropdown-item {
  padding: 9px 16px;
  font-size: 14px;
  color: #111827;
  cursor: pointer;
}
.user-dropdown-item:hover {
  background: #f3f4f6;
}
.user-dropdown-logout {
  color: #ef4444;
}
.user-dropdown-logout:hover {
  background: #fef2f2;
}
.dropdown-enter-active,
.dropdown-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}
.dropdown-enter-from,
.dropdown-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

.btn-primary {
  background: var(--primary);
  color: #fff;
  border: none;
  padding: 8px 16px;
  border-radius: var(--radius);
  font-size: 14px;
  cursor: pointer;
}
.btn-primary:hover { background: var(--primary-dark); }
.file-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
}
.file-toolbar-topbar { padding: 4px 0 0; border-bottom: none; }
.file-toolbar-left { display: flex; align-items: center; gap: 6px; font-size: 14px; min-width: 0; }
.file-breadcrumb-item { color: #6b7280; }
.file-breadcrumb-sep { color: #9ca3af; user-select: none; }
.file-breadcrumb-link { color: var(--primary); text-decoration: none; }
.file-breadcrumb-link:hover { text-decoration: underline; }
.file-breadcrumb-current { color: #111; font-weight: 500; max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.file-toolbar-right { display: flex; align-items: center; gap: 16px; flex-wrap: wrap; }
.file-sort-select {
  width: 180px;
  padding: 8px 12px 8px 32px;
  border: 1px solid var(--border);
  border-radius: 8px;
  font-size: 14px;
  color: var(--text);
  background: #fff url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="%236b7280" stroke-width="2"><line x1="4" y1="21" x2="4" y2="14"/><line x1="4" y1="10" x2="4" y2="3"/><line x1="12" y1="21" x2="12" y2="12"/><line x1="12" y1="8" x2="12" y2="3"/><line x1="20" y1="21" x2="20" y2="16"/><line x1="20" y1="12" x2="20" y2="3"/><line x1="1" y1="14" x2="7" y2="14"/><line x1="9" y1="8" x2="15" y2="8"/><line x1="17" y1="16" x2="23" y2="16"/></svg>') no-repeat 10px center;
  cursor: pointer;
}
.file-view-toggle {
  display: flex;
  align-items: center;
  gap: 2px;
  padding: 4px;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  background: #fff;
}
.file-view-btn {
  padding: 6px 10px;
  border: none;
  background: transparent;
  border-radius: 6px;
  cursor: pointer;
  color: #6b7280;
  display: flex;
  align-items: center;
  justify-content: center;
}
.file-view-btn:hover { color: #111; background: #f3f4f6; }
.file-view-btn.active { background: #4a90e2; color: #fff; }
.file-view-btn.active:hover { background: #357abd; color: #fff; }
.file-view-icon { width: 16px; height: 16px; }
</style>
