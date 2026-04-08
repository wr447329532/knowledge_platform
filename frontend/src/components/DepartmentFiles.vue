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

      <!-- 部门文件库表格（用作部门文件视图） -->
      <div v-else class="dept-files-wrap">
        <div v-if="rows.length" class="dept-files-table card">
          <table>
            <thead>
              <tr>
                <th>名称</th>
                <th>类型</th>
                <th>描述</th>
                <th>创建者</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="r in rows"
                :key="r.id"
                class="dept-file-row"
                @click="$emit('open-lib', r.raw)"
              >
                <td>
                  <div class="dept-file-name">
                    <Icons :name="r.type === 'folder' ? 'folder' : 'file-text'" class="dept-file-icon" />
                    <span class="dept-file-title">{{ r.name }}</span>
                  </div>
                </td>
                <td class="dept-file-type">
                  {{ r.type === 'folder' ? '部门库' : '文件库' }}
                </td>
                <td class="dept-file-desc">
                  {{ r.description || '-' }}
                </td>
                <td class="dept-file-owner">
                  {{ r.owner }}
                </td>
                <td class="dept-file-actions">
                  <button
                    v-if="r.raw?.is_owner"
                    type="button"
                    class="btn-icon"
                    title="编辑"
                    @click.stop="$emit('edit-lib', r.raw)"
                  >⋯</button>
                  <button
                    v-if="r.raw?.is_owner"
                    type="button"
                    class="btn-icon danger"
                    title="删除"
                    @click.stop="$emit('del-lib', r.raw)"
                  >🗑</button>
                  <span v-if="!r.raw?.is_owner" class="dept-action-placeholder">-</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-if="rows.length" class="audit-pagination">
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
import { ref, watch } from 'vue'
import Icons from './Icons.vue'
import * as api from '../api/client'

const props = defineProps({
  me: { type: Object, default: null },
  activeDeptId: { type: Number, default: null },
  reloadKey: { type: Number, default: 0 },
})

const emit = defineEmits(['back', 'open-lib', 'edit-lib', 'del-lib'])

const loading = ref(false)
const err = ref('')
const deptInfo = ref(null)
const rows = ref([])
const limit = ref(20)
const offset = ref(0)
const hasMore = ref(false)

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
      const libs = await api.listDepartmentLibraries(id, {
        limit: limit.value,
        offset: offset.value,
      })
      rows.value = Array.isArray(libs)
        ? libs.map((lib) => ({
            id: lib.id,
            name: lib.name,
            type: 'folder',
            description: lib.description || '',
            owner: lib.owner_username || (lib.is_owner ? (props.me?.username || '我') : '-'),
            raw: lib,
          }))
        : []
      hasMore.value = rows.value.length === limit.value
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
  height: 100%;
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
  flex: 1;
  padding: 0 24px 20px;
  overflow: auto;
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

.dept-files-table {
  border-radius: 12px;
  border: 1px solid #e5e7eb;
  overflow: hidden;
}

.dept-files-table table {
  width: 100%;
  border-collapse: collapse;
}

.dept-files-table thead {
  background: #f9fafb;
  border-bottom: 1px solid #e5e7eb;
}

.dept-files-table th,
.dept-files-table td {
  padding: 10px 16px;
  font-size: 13px;
  text-align: left;
}

.dept-files-table th {
  font-weight: 600;
  color: #6b7280;
  text-transform: uppercase;
  font-size: 12px;
}

.dept-file-row:hover {
  background: #f9fafb;
}

.dept-file-name {
  display: flex;
  align-items: center;
  gap: 8px;
}

.dept-file-icon {
  width: 18px;
  height: 18px;
  color: #4a90e2;
}

.dept-file-title {
  font-size: 14px;
  font-weight: 500;
  color: #111827;
}

.dept-file-type,
.dept-file-desc,
.dept-file-owner {
  font-size: 13px;
  color: #4b5563;
}

.dept-file-actions {
  white-space: nowrap;
}

.dept-file-actions .btn-icon + .btn-icon {
  margin-left: 8px;
}

.btn-icon {
  width: 22px;
  height: 22px;
  border: none;
  background: transparent;
  border-radius: 0;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #374151;
  font-size: 15px;
  padding: 0;
}

.btn-icon:hover {
  opacity: 0.78;
}

.btn-icon.danger {
  color: #dc2626;
}

.dept-action-placeholder {
  color: #9ca3af;
}

.audit-pagination {
  margin-top: 12px;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
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

