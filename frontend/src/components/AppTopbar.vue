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
        <div
          v-if="activeTab === 'lib' && showNewDropdown"
          class="new-menu-wrap"
          ref="newMenuWrapRef"
        >
          <button
            type="button"
            class="btn-primary btn-new-split"
            aria-haspopup="menu"
            :aria-expanded="newMenuOpen"
            @click.stop="toggleNewMenu"
          >
            + 新建
            <span class="btn-new-chevron" aria-hidden="true">▾</span>
          </button>
          <Transition name="dropdown">
            <div
              v-if="newMenuOpen"
              class="new-dropdown"
              role="menu"
            >
              <template v-if="!currentLib">
                <button type="button" class="new-dropdown-item" role="menuitem" @click="chooseNewLib">
                  新建文件库
                </button>
              </template>
              <template v-else-if="currentLib?.is_writeable">
                <button
                  v-if="canCreateSubLib"
                  type="button"
                  class="new-dropdown-item"
                  role="menuitem"
                  @click="chooseNewSubLib"
                >
                  新建文件库
                </button>
                <button type="button" class="new-dropdown-item" role="menuitem" @click="chooseUpload">
                  上传文件
                </button>
              </template>
            </div>
          </Transition>
        </div>
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

    <!-- 第二行：面包屑 + 视图切换（我的文件库与部门文件共用） -->
    <div v-if="activeTab === 'lib'" class="file-toolbar file-toolbar-topbar">
      <div class="file-toolbar-left">
        <template v-if="activeDeptId">
          <span class="file-breadcrumb-item">{{ activeDeptName || '部门' }}</span>
        </template>
        <template v-else>
          <span class="file-breadcrumb-item">文件库</span>
        </template>
        <template v-if="currentLib">
          <span class="file-breadcrumb-sep">/</span>
          <a href="#" @click.prevent="emit('clear-lib')" class="file-breadcrumb-link">{{ currentLib?.name }}</a>
          <template v-for="(seg, i) in breadcrumbSegments" :key="i">
            <span class="file-breadcrumb-sep">/</span>
            <a v-if="seg.path !== undefined" href="#" @click.prevent="emit('set-path', seg.path)" class="file-breadcrumb-link">{{ seg.label }}</a>
            <span v-else class="file-breadcrumb-current">{{ seg.label }}</span>
          </template>
        </template>
        <template v-else-if="activeDeptId">
          <span class="file-breadcrumb-sep">/</span>
          <span class="file-breadcrumb-current">部门文件库</span>
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
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import Icons from './Icons.vue'

const props = defineProps({
  activeTab: String,
  activeDeptId: { type: Number, default: null },
  activeDeptName: { type: String, default: '' },
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
  'search', 'new-lib', 'new-sub-lib', 'upload', 'clear-lib', 'set-path', 'toggle-notify',
  'go-account', 'go-admin', 'go-dept-manage', 'logout',
])

const userMenuWrapRef = ref(null)
const userDropdownRef = ref(null)
const userMenuOpen = ref(false)

const newMenuWrapRef = ref(null)
const newMenuOpen = ref(false)

/** 全部文件列表：新建根库；进入资料库且可写：下拉含新建（子库）与上传文件 */
const showNewDropdown = computed(() => {
  if (props.activeTab !== 'lib') return false
  if (!props.currentLib) return true
  return !!props.currentLib?.is_writeable
})

/** 一级 depth=1；最多三级，depth < 3 时可再建子库 */
const canCreateSubLib = computed(() => {
  const d = props.currentLib?.depth
  if (d == null || d === undefined) return true
  return Number(d) < 3
})

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
  return !!m.is_department_leader
})

function toggleUserMenu() {
  userMenuOpen.value = !userMenuOpen.value
}

function closeUserMenu() {
  userMenuOpen.value = false
}

function closeNewMenu() {
  newMenuOpen.value = false
}

function toggleNewMenu() {
  newMenuOpen.value = !newMenuOpen.value
}

function chooseNewLib() {
  closeNewMenu()
  emit('new-lib')
}

function chooseNewSubLib() {
  closeNewMenu()
  emit('new-sub-lib')
}

function chooseUpload() {
  closeNewMenu()
  emit('upload')
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
  const newWrap = newMenuWrapRef.value
  if (wrap && wrap.contains(e.target)) return
  if (dropdown && dropdown.contains(e.target)) return
  closeUserMenu()
  if (newWrap && !newWrap.contains(e.target)) closeNewMenu()
}

watch(
  () => [props.activeTab, props.currentLib?.id],
  () => closeNewMenu()
)

onMounted(() => {
  document.addEventListener('click', onDocumentClick)
})
onUnmounted(() => {
  document.removeEventListener('click', onDocumentClick)
})
</script>

<style scoped>
.app-topbar {
  flex-shrink: 0;
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
  gap: 10px;
}
.search-box {
  flex: 1 1 760px;
  min-width: 360px;
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
.topbar-actions { margin-left: 6px; display: flex; align-items: center; gap: 12px; }
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
.btn-secondary {
  background: #fff;
  color: var(--primary);
  border: 1px solid var(--primary);
  padding: 8px 14px;
  border-radius: var(--radius);
  font-size: 14px;
  cursor: pointer;
}
.btn-secondary:hover {
  background: #eff6ff;
}

.new-menu-wrap {
  position: relative;
}
.btn-new-split {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 36px;
  padding-left: 14px;
  padding-right: 12px;
}
.btn-new-chevron {
  font-size: 10px;
  opacity: 0.85;
}
.new-dropdown {
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  min-width: 148px;
  padding: 4px 0;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  border: 1px solid #e5e7eb;
  z-index: 998;
}
.new-dropdown-item {
  display: block;
  width: 100%;
  padding: 10px 16px;
  border: none;
  background: none;
  text-align: left;
  font-size: 14px;
  color: #111827;
  cursor: pointer;
}
.new-dropdown-item:hover {
  background: #f3f4f6;
}

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
