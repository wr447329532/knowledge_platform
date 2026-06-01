<template>
  <div class="dept-page" v-if="activeDeptId">
    <!-- 顶部：返回 + 部门信息 -->
    <div class="dept-header card">
      <button type="button" class="dept-back-btn" @click="$emit('back')">
        <Icons name="arrow-left" class="dept-back-icon" />
        <span>返回</span>
      </button>
      <div class="dept-header-main">
        <div class="dept-header-title">
          <Icons name="building" class="dept-header-icon" />
          <h1 class="dept-header-name">{{ deptInfo?.name || '部门文件' }}</h1>
        </div>
        <div v-if="deptInfo" class="dept-header-path">
          <span>组织架构</span>
          <span>/</span>
          <span>{{ deptInfo.path }}</span>
        </div>
      </div>
    </div>

    <!-- 内容区域 -->
    <div class="dept-body">
      <!-- 加载 / 错误 -->
      <p v-if="loading" class="empty-hint">加载中...</p>
      <p v-else-if="err" class="error-text">{{ err }}</p>

      <!-- 部门不存在或无详情 -->
      <div v-else-if="!deptInfo" class="dept-empty">
        <Icons name="building" class="dept-empty-icon" />
        <p class="dept-empty-text">部门不存在或信息不可用</p>
      </div>

      <!-- 无访问权限 -->
      <div v-else-if="!deptInfo.has_access" class="dept-lock card">
        <div class="dept-lock-icon-wrap">
          <Icons name="lock" class="dept-lock-icon" />
        </div>
        <h2 class="dept-lock-title">访问受限</h2>
        <p class="dept-lock-text">
          您没有权限访问「{{ deptInfo.name }}」的文件库，请联系系统管理员或部门负责人。
        </p>
      </div>

      <!-- 部门文件库：列表 / 网格与「我的文件库」同款（LibraryPage） -->
      <div v-else class="dept-files-wrap">
        <template v-if="sortedRows.length">
          <div class="lib-grid-wrap">
            <!-- 行视图：与 LibraryPage 一级库列表一致 -->
            <div v-if="fileViewMode === 'list'" class="lib-list-container">
              <div class="lib-list-table">
                <div class="lib-list-head">
                  <div class="lib-col-name">名称</div>
                  <div class="lib-col-desc">描述</div>
                  <div class="lib-col-type">类型</div>
                  <div class="lib-col-source">来源</div>
                  <div class="lib-col-actions">操作</div>
                </div>
                <div
                  v-for="r in sortedRows"
                  :key="r.id"
                  class="lib-list-row"
                >
                  <div class="lib-col-name">
                    <div class="lib-name-inner">
                      <Icons name="folder" class="lib-folder-icon" />
                      <a
                        href="#"
                        class="lib-name-text"
                        :title="r.name"
                        @click.prevent="$emit('open-lib', r.raw)"
                      >
                        {{ r.name }}
                      </a>
                      <span v-if="!r.raw?.is_owner" class="lib-badge-shared">共享给我</span>
                    </div>
                  </div>
                  <div class="lib-col-desc">
                    {{ r.description || '-' }}
                  </div>
                  <div class="lib-col-type">
                    <LibraryTypeTags :lib="r.raw" />
                  </div>
                  <div class="lib-col-source">
                    <template v-if="r.raw?.is_owner">-</template>
                    <template v-else>
                      分享者：{{ r.raw?.owner_username || r.owner || '-' }}
                      <template v-if="r.raw?.department_name">
                        · 来源部门：{{ r.raw.department_name }}
                      </template>
                    </template>
                  </div>
                  <div class="lib-col-actions">
                    <div class="lib-actions">
                      <button
                        v-if="r.raw?.is_owner"
                        type="button"
                        class="btn-icon"
                        title="编辑"
                        @click.stop="$emit('edit-lib', r.raw)"
                      >
                        ⋯
                      </button>
                      <button
                        v-if="r.raw?.is_owner"
                        type="button"
                        class="btn-icon"
                        title="移动"
                        @click.stop="$emit('move-lib', r.raw)"
                      >
                        ⇄
                      </button>
                      <button
                        v-if="r.raw?.is_owner"
                        type="button"
                        class="btn-icon danger"
                        title="删除"
                        @click.stop="$emit('del-lib', r.raw)"
                      >
                        🗑
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- 网格视图：与 LibraryPage 一级库卡片一致 -->
            <div v-else class="lib-grid dept-files-lib-grid">
              <div
                v-for="r in sortedRows"
                :key="r.id"
                class="lib-card"
                @click="$emit('open-lib', r.raw)"
              >
                <button
                  v-if="r.raw?.is_owner"
                  type="button"
                  class="lib-card-more"
                  title="更多操作"
                  @click.stop="toggleDeptCardMenu('d-' + r.id)"
                >
                  ⋯
                </button>
                <div
                  v-if="deptCardMenuId === 'd-' + r.id"
                  class="action-dropdown lib-card-dropdown"
                  @click.stop
                >
                  <button
                    type="button"
                    class="btn-small"
                    @click="$emit('edit-lib', r.raw); closeDeptCardMenu()"
                  >
                    编辑
                  </button>
                  <button
                    type="button"
                    class="btn-small"
                    @click="$emit('move-lib', r.raw); closeDeptCardMenu()"
                  >
                    移动
                  </button>
                  <button
                    type="button"
                    class="btn-small danger"
                    @click="$emit('del-lib', r.raw); closeDeptCardMenu()"
                  >
                    删除
                  </button>
                </div>
                <div class="lib-card-icon-wrap">
                  <Icons name="folder" class="lib-card-icon" />
                </div>
                <div class="lib-card-text">
                  <p class="lib-card-name" :title="r.name">
                    {{ r.name }}
                  </p>
                  <p v-if="r.description" class="lib-card-desc">
                    {{ r.description }}
                  </p>
                </div>
                <div class="lib-card-meta">
                  <span v-if="!r.raw?.is_owner" class="lib-badge-shared">共享给我</span>
                  <LibraryTypeTags :lib="r.raw" />
                  <div v-if="!r.raw?.is_owner" class="lib-card-share-meta">
                    <span>分享者：{{ r.raw?.owner_username || r.owner || '-' }}</span>
                    <span v-if="r.raw?.department_name">来源：{{ r.raw.department_name }}</span>
                  </div>
                </div>
              </div>
            </div>

            <div class="audit-pagination">
              <div class="audit-pagination-actions">
                <button
                  type="button"
                  class="admin-btn-secondary page-icon-btn"
                  :disabled="offset <= 0 || loading"
                  title="上一页"
                  @click="prevPage"
                >
                  <Icons name="arrow-left" />
                </button>
                <button
                  type="button"
                  class="admin-btn-secondary page-icon-btn"
                  :disabled="!hasMore || loading"
                  title="下一页"
                  @click="nextPage"
                >
                  <Icons name="chevron-right" />
                </button>
              </div>
              <div class="audit-pagination-info">
                第 {{ Math.floor(offset / limit) + 1 }} 页，每页 {{ limit }} 条
              </div>
            </div>
          </div>
        </template>
        <div v-else class="dept-empty">
          <Icons name="folder" class="dept-empty-icon" />
          <p class="dept-empty-text">该部门暂无文件库</p>
          <p class="dept-empty-hint">可在右上角「新建文件库」中选择所属部门后创建。</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import Icons from './Icons.vue'
import * as api from '../api/client'
import LibraryTypeTags from './LibraryTypeTags.vue'

const props = defineProps({
  me: { type: Object, default: null },
  activeDeptId: { type: Number, default: null },
  reloadKey: { type: Number, default: 0 },
  fileSortOrder: { type: String, default: 'modified' },
  fileViewMode: { type: String, default: 'list' },
})

const emit = defineEmits(['back', 'open-lib', 'edit-lib', 'del-lib', 'move-lib'])

const loading = ref(false)
const err = ref('')
const deptInfo = ref(null)
const rows = ref([])
const limit = ref(20)
const offset = ref(0)
const hasMore = ref(false)
const deptCardMenuId = ref(null)

function toggleDeptCardMenu(id) {
  deptCardMenuId.value = deptCardMenuId.value === id ? null : id
}

function closeDeptCardMenu() {
  deptCardMenuId.value = null
}

watch(deptCardMenuId, (id) => {
  if (!id) return
  const onDoc = () => {
    deptCardMenuId.value = null
    document.removeEventListener('click', onDoc)
  }
  setTimeout(() => document.addEventListener('click', onDoc), 0)
})

const sortedRows = computed(() => {
  const arr = [...(rows.value || [])]
  const order = props.fileSortOrder || 'modified'
  if (order === 'name') {
    arr.sort((a, b) => (a.name || '').localeCompare(b.name || ''))
  } else if (order === 'size') {
    arr.sort((a, b) => (b.size_bytes || 0) - (a.size_bytes || 0))
  } else if (order === 'created') {
    arr.sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0))
  } else {
    arr.sort((a, b) => new Date(b.updated_at || 0) - new Date(a.updated_at || 0))
  }
  return arr
})

async function loadDept(id) {
  if (!id) {
    deptInfo.value = null
    rows.value = []
    return
  }
  loading.value = true
  err.value = ''
  deptInfo.value = null
  rows.value = []
  hasMore.value = false
  try {
    const info = await api.getDepartmentInfo(id)
    deptInfo.value = info
    if (info?.has_access) {
      const pageSize = limit.value
      let off = offset.value
      let list = []
      for (;;) {
        const libs = await api.listDepartmentLibraries(id, {
          limit: pageSize + 1,
          offset: off,
        })
        list = Array.isArray(libs) ? libs : []
        if (list.length > 0 || off <= 0) break
        off = Math.max(0, off - pageSize)
      }
      offset.value = off
      hasMore.value = list.length > pageSize
      rows.value = list.slice(0, pageSize).map((lib) => ({
        id: lib.id,
        name: lib.name,
        type: 'folder',
        description: lib.description || '',
        owner: lib.owner_username || (lib.is_owner ? (props.me?.username || '我') : '-'),
        size_bytes: Number(lib.size_bytes || lib.total_size || 0),
        updated_at: lib.updated_at || null,
        created_at: lib.created_at || null,
        raw: lib,
      }))
    }
  } catch (e) {
    err.value = e?.message || '加载部门信息失败'
  } finally {
    loading.value = false
  }
}

watch(
  () => props.activeDeptId,
  (id) => {
    offset.value = 0
    loadDept(id)
  },
  { immediate: true },
)

// 创建文件库成功后不一定会改变 activeDeptId，这里用 reloadKey 强制刷新列表
watch(
  () => props.reloadKey,
  () => {
    offset.value = 0
    if (props.activeDeptId) loadDept(props.activeDeptId)
  },
)

function prevPage() {
  if (offset.value <= 0 || loading.value) return
  offset.value = Math.max(0, offset.value - limit.value)
  if (props.activeDeptId) loadDept(props.activeDeptId)
}

function nextPage() {
  if (!hasMore.value || loading.value) return
  offset.value += limit.value
  if (props.activeDeptId) loadDept(props.activeDeptId)
}
</script>

<style scoped>
.dept-page {
  display: flex;
  flex-direction: column;
  min-height: min-content;
}

.dept-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 20px;
  border-radius: 12px;
  margin: 16px 24px 8px;
}

.dept-back-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 6px 10px;
  border-radius: 999px;
  border: none;
  background: #f3f4f6;
  color: #374151;
  cursor: pointer;
  font-size: 13px;
}

.dept-back-btn:hover {
  background: #e5e7eb;
}

.dept-back-icon {
  width: 16px;
  height: 16px;
}

.dept-header-main {
  flex: 1;
  min-width: 0;
}

.dept-header-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.dept-header-icon {
  width: 22px;
  height: 22px;
  color: #4a90e2;
}

.dept-header-name {
  font-size: 20px;
  font-weight: 600;
  color: #111827;
  margin: 0;
}

.dept-header-path {
  margin-top: 4px;
  font-size: 13px;
  color: #6b7280;
  display: flex;
  align-items: center;
  gap: 4px;
}

.dept-body {
  flex: none;
  padding: 0 24px 20px;
  overflow: visible;
}

.dept-lock {
  max-width: 520px;
  margin: 40px auto 0;
  text-align: center;
  padding: 32px 24px 28px;
}

.dept-lock-icon-wrap {
  width: 80px;
  height: 80px;
  border-radius: 999px;
  background: #fee2e2;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 16px;
}

.dept-lock-icon {
  width: 40px;
  height: 40px;
  color: #dc2626;
}

.dept-lock-title {
  font-size: 18px;
  font-weight: 600;
  margin: 0 0 8px 0;
  color: #111827;
}

.dept-lock-text {
  font-size: 14px;
  color: #4b5563;
  margin: 0;
}

.dept-files-wrap {
  margin-top: 12px;
}

/* —— 以下与 LibraryPage「我的文件库」一级列表 / 卡片对齐 —— */
.lib-grid-wrap {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.lib-list-container {
  background: #ffffff;
  border-radius: 10px;
  border: 1px solid #e5e7eb;
  overflow: hidden;
}

.lib-list-table {
  width: 100%;
}

.lib-list-head {
  display: grid;
  grid-template-columns: minmax(0, 2.5fr) minmax(0, 2.1fr) minmax(168px, 2fr) minmax(0, 1.7fr) 120px;
  column-gap: 24px;
  padding: 10px 16px;
  background: #f9fafb;
  border-bottom: 1px solid #e5e7eb;
  font-size: 12px;
  font-weight: 600;
  color: #6b7280;
  text-transform: uppercase;
}

.lib-list-row {
  display: grid;
  grid-template-columns: minmax(0, 2.5fr) minmax(0, 2.1fr) minmax(168px, 2fr) minmax(0, 1.7fr) 120px;
  column-gap: 24px;
  padding: 10px 16px;
  font-size: 14px;
  align-items: center;
  border-bottom: 1px solid #f3f4f6;
  transition: background-color 0.15s ease, box-shadow 0.15s ease;
}

.lib-list-row:hover {
  background-color: #f9fafb;
}

.lib-col-name,
.lib-col-desc,
.lib-col-type,
.lib-col-source,
.lib-col-actions {
  overflow: hidden;
}

.lib-col-actions {
  display: flex;
  justify-content: flex-end;
  align-items: center;
}

.lib-name-inner {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.lib-folder-icon {
  width: 18px;
  height: 18px;
  color: #4a90e2;
  flex-shrink: 0;
}

.lib-name-text {
  color: #111827;
  text-decoration: none;
  white-space: nowrap;
  text-overflow: ellipsis;
  overflow: hidden;
  font-weight: 500;
}

.lib-col-desc {
  color: #6b7280;
  white-space: nowrap;
  text-overflow: ellipsis;
  overflow: hidden;
}

.lib-col-type {
  color: #4b5563;
  justify-self: start;
  padding-right: 8px;
  overflow: visible;
}

.lib-col-source {
  color: #6b7280;
  font-size: 12px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  padding-left: 4px;
}

.lib-actions {
  display: flex;
  justify-content: flex-end;
  gap: 4px;
}

.btn-icon {
  border: none;
  background: transparent;
  width: 26px;
  height: 26px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #4b5563;
  cursor: pointer;
  transition: background-color 0.15s ease, color 0.15s ease;
}

.btn-icon:hover {
  background-color: #e5e7eb;
  color: #111827;
}

.btn-icon.danger {
  color: #dc2626;
}

.btn-icon.danger:hover {
  background-color: #fee2e2;
  color: #b91c1c;
}

.lib-badge-shared {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 500;
  background-color: #eff6ff;
  color: #1d4ed8;
}

.lib-grid {
  margin-top: 4px;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 12px;
}

.dept-files-lib-grid {
  overflow: visible;
}

.lib-card {
  position: relative;
  background: #ffffff;
  border-radius: 12px;
  border: 1px solid #e5e7eb;
  padding: 14px 10px 10px;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  transition: box-shadow 0.18s ease, border-color 0.18s ease, transform 0.1s ease;
}

.lib-card:hover {
  border-color: #4a90e2;
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.08);
  transform: translateY(-1px);
}

.lib-card-more {
  position: absolute;
  top: 6px;
  right: 6px;
  width: 24px;
  height: 24px;
  border-radius: 999px;
  border: none;
  background: transparent;
  color: #6b7280;
  font-size: 16px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: opacity 0.15s ease, background-color 0.15s ease, color 0.15s ease;
}

.lib-card:hover .lib-card-more {
  opacity: 1;
}

.lib-card-more:hover {
  background-color: #e5e7eb;
  color: #111827;
}

.lib-card-icon-wrap {
  width: 48px;
  height: 48px;
  border-radius: 14px;
  background: #eff6ff;
  display: flex;
  align-items: center;
  justify-content: center;
}

.lib-card-icon {
  width: 30px;
  height: 30px;
  color: #4a90e2;
}

.lib-card-text {
  width: 100%;
  text-align: center;
}

.lib-card-name {
  font-size: 13px;
  font-weight: 500;
  color: #111827;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.lib-card-desc {
  margin-top: 2px;
  font-size: 12px;
  color: #6b7280;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.lib-card-meta {
  margin-top: 2px;
}

.lib-card-share-meta {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-top: 4px;
  font-size: 11px;
  color: #6b7280;
  text-align: center;
}

.action-dropdown {
  position: absolute;
  right: 6px;
  top: 32px;
  background: #ffffff;
  border-radius: 18px;
  border: 1px solid #e5e7eb;
  padding: 8px 6px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  box-shadow: 0 14px 40px rgba(15, 23, 42, 0.16);
  z-index: 40;
}

.action-dropdown .btn-small {
  min-width: 80px;
  padding: 6px 14px;
  border-radius: 999px;
  border: 1px solid #e5e7eb;
  background: #f9fafb;
  color: #111827;
  font-size: 13px;
  text-align: center;
  cursor: pointer;
}

.action-dropdown .btn-small:hover {
  background: #eef2ff;
  border-color: #c7d2fe;
}

.action-dropdown .btn-small.danger {
  background: #ef4444;
  border-color: #ef4444;
  color: #ffffff;
}

.action-dropdown .btn-small.danger:hover {
  background: #dc2626;
  border-color: #dc2626;
}

.audit-pagination {
  margin-top: 8px;
  padding: 10px 0 8px;
  border-top: none;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
  font-size: 12px;
  color: #6b7280;
}

.audit-pagination-actions {
  display: flex;
  gap: 8px;
}

.page-icon-btn {
  width: 34px;
  min-width: 34px;
  height: 32px;
  padding: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.dept-empty {
  margin-top: 60px;
  text-align: center;
}

.dept-empty-icon {
  width: 52px;
  height: 52px;
  color: #d1d5db;
  margin-bottom: 12px;
}

.dept-empty-text {
  font-size: 14px;
  color: #4b5563;
  margin: 0 0 4px 0;
}

.dept-empty-hint {
  font-size: 12px;
  color: #9ca3af;
  margin: 0;
}

.error-text {
  color: #dc2626;
  text-align: center;
  margin-top: 16px;
}
</style>

