<template>
  <div class="trash-page">
    <!-- Header -->
    <div class="trash-header">
      <div class="trash-header-left">
        <Icons name="trash" class="trash-header-icon" />
        <div>
          <h1 class="trash-title">{{ mode === 'dept' ? '部门回收站' : '我的回收站' }}</h1>
          <p class="trash-subtitle">{{
            mode === 'dept'
              ? '本部门所有文件库的删除记录，仅在手动彻底删除后永久移除'
              : '仅显示您私人库中的删除记录，仅在手动彻底删除后永久移除'
          }}</p>
        </div>
      </div>
      <!-- 部门回收站模式：提示范围 -->
      <div v-if="mode === 'dept'" class="trash-header-right">
        <span class="trash-header-tip">展示本部门所有部门库中的删除记录</span>
      </div>
    </div>

    <!-- Body：统一列表 -->
    <div class="trash-body">
      <section class="trash-section">
        <h2 class="trash-section-title">已删除的项目</h2>
        <p v-if="displayLoading" class="empty-hint">加载中...</p>
        <div v-else-if="displayList?.length" class="trash-table-card">
          <table class="trash-table">
            <thead>
              <tr>
                <th v-if="mode === 'dept'">用户账号</th>
                <th>类型</th>
                <th>名称</th>
                <th>所在库</th>
                <th>删除时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(item, idx) in displayList"
                :key="(item.type || 'file') + '-' + item.id + '-' + idx"
                class="trash-row"
              >
                <td v-if="mode === 'dept'" class="trash-cell-user">
                  {{ item.username || '-' }}
                </td>
                <td class="trash-cell-type">
                  <span class="trash-tag" :class="item.type === 'library' ? 'trash-tag-lib' : 'trash-tag-file'">
                    {{ item.type === 'library' ? '文件库' : (item.type === 'file_version' ? '历史版本' : '文件') }}
                  </span>
                </td>
                <td class="trash-cell-name">
                  <div class="trash-name-wrap">
                    <Icons :name="item.type === 'library' ? 'folder' : 'file-text'" class="trash-file-icon" />
                    <span class="trash-file-name">{{ trashEntryDisplayName(item) }}</span>
                  </div>
                </td>
                <td
                  class="trash-cell-path trash-lib-chain-cell"
                  :title="trashLibraryLocationText(item)"
                >
                  {{ trashLibraryLocationText(item) }}
                </td>
                <td class="trash-cell-date">
                  {{ formatDate(item.deleted_at) }}
                </td>
                <td class="trash-cell-actions">
                  <template v-if="mode === 'dept'">
                    <button
                      type="button"
                      class="trash-btn-secondary"
                      @click="emit('restore-dept', item)"
                    >
                      恢复
                    </button>
                    <button
                      type="button"
                      class="trash-btn-danger"
                      @click="emit('perm-delete-dept', item)"
                    >
                      永久删除
                    </button>
                  </template>
                  <template v-else>
                    <button
                      type="button"
                      class="trash-btn-secondary"
                      :class="{ 'trash-btn-disabled': item.can_restore === false }"
                      :disabled="item.can_restore === false"
                      @click="item.can_restore === false ? null : emit('restore-item', item)"
                    >
                      恢复
                    </button>
                    <button
                      type="button"
                      class="trash-btn-danger"
                      :class="{ 'trash-btn-disabled': item.can_delete === false }"
                      :disabled="item.can_delete === false"
                      @click="item.can_delete === false ? null : emit('perm-delete-item', item)"
                    >
                      永久删除
                    </button>
                  </template>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div
          v-if="showPersonalTrashPaginationFooter"
          class="audit-pagination"
        >
          <div class="audit-pagination-actions">
            <button
              type="button"
              class="admin-btn-secondary page-icon-btn"
              :disabled="trashPaginationOffset <= 0"
              title="上一页"
              @click="emit('trash-prev-page')"
            >
              <Icons name="arrow-left" />
            </button>
            <button
              type="button"
              class="admin-btn-secondary page-icon-btn"
              :disabled="!trashPaginationHasNext"
              title="下一页"
              @click="emit('trash-next-page')"
            >
              <Icons name="chevron-right" />
            </button>
          </div>
          <div class="audit-pagination-info">
            第 {{ trashPageNumber }} 页，每页 {{ trashPaginationLimit }} 条
          </div>
        </div>
        <div
          v-else-if="!displayLoading && !displayList?.length"
          class="trash-empty-card"
        >
          <Icons name="trash" class="trash-empty-icon" />
          <p class="trash-empty-text">回收站为空</p>
          <p class="trash-empty-hint">{{ mode === 'dept' ? '本部门暂无删除记录。' : '删除的文件库和文件会显示在这里，需手动执行彻底删除。' }}</p>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import Icons from './Icons.vue'

const props = defineProps({
  mode: { type: String, default: 'personal' }, // 'personal' | 'dept'
  // personal：统一列表（库+文件）；dept：由父组件传入的部门回收站文件列表
  trashItems: Array,
  trashLoading: Boolean,
  deptTrashList: { type: Array, default: () => [] },
  deptTrashLoading: { type: Boolean, default: false },
  /** 个人回收站分页：与 LibraryPage 文件列表一致 */
  personalTrashPagination: { type: Boolean, default: false },
  trashPaginationHasNext: { type: Boolean, default: false },
  trashPaginationOffset: { type: Number, default: 0 },
  trashPaginationLimit: { type: Number, default: 50 },
  formatDate: Function,
  libraries: { type: Array, default: () => [] },
})

const displayList = computed(() =>
  props.mode === 'dept' ? (props.deptTrashList || []) : (props.trashItems || [])
)
const displayLoading = computed(() =>
  props.mode === 'dept' ? props.deptTrashLoading : props.trashLoading
)

const trashPageNumber = computed(() =>
  props.trashPaginationLimit
    ? Math.floor(Number(props.trashPaginationOffset || 0) / Number(props.trashPaginationLimit)) + 1
    : 1,
)

const showPersonalTrashPaginationFooter = computed(() => {
  if (props.mode !== 'personal' || !props.personalTrashPagination || props.trashLoading) return false
  if (displayList.value?.length) return true
  return Number(props.trashPaginationOffset || 0) > 0
})

/**
 * 所在库列：文件/历史版本为「资料库链 / 库内路径」；已删除的文件库为层级链或库名。
 */
function trashLibraryLocationText(item) {
  if (!item) return '-'
  if (item.type === 'file' || item.type === 'file_version') {
    return formatTrashFullLocationPath(item)
  }
  if (item.type === 'library') {
    const crumb = (item.library_breadcrumb || item.library_name || '').trim()
    return crumb || '-'
  }
  return '-'
}

/**
 * 删除前在资料库内的相对路径（不含库名）；与列表页 path 字段语义一致。
 * 历史版本会把尾注 ` (历史版本 vN)` 拼在 path 上，此处只取文件位置部分。
 */
function pathWithinLibraryRaw(pathStr) {
  if (pathStr == null || String(pathStr).trim() === '') return ''
  let s = String(pathStr).trim()
  const idx = s.indexOf(' (历史版本')
  if (idx >= 0) s = s.slice(0, idx).trim()
  return s.replace(/\\/g, '/').replace(/^\/+/g, '')
}

/**
 * 路径列：资料库层级（与「所在库」同源）+ 库内相对路径。
 * 根目录文件示例：`初步设计 / 1. xxx.doc`，不再仅 `/1. xxx.doc`。
 */
function formatTrashFullLocationPath(item) {
  if (!item || item.type === 'library') return '-'
  if (item.type !== 'file' && item.type !== 'file_version') return '-'
  const inner = pathWithinLibraryRaw(item.path)
  const chain = (item.library_breadcrumb || item.library_name || '').trim()
  if (!inner && !chain) return '-'
  if (!inner) return chain || '-'
  if (!chain) return `/${inner}`
  return `${chain} / ${inner}`
}

/** 名称列：仅文件名；历史版本附加简短 (vN) */
function trashEntryDisplayName(item) {
  if (!item) return '-'
  if (item.type === 'library') {
    return item.name || item.library_name || `文件库 #${item.id}`
  }
  if (item.type !== 'file' && item.type !== 'file_version') return '-'
  const raw = item.path
  if (raw == null || String(raw).trim() === '') return '-'
  let main = String(raw)
  let versionShort = ''
  const idx = main.indexOf(' (历史版本')
  if (idx >= 0) {
    const m = main.match(/历史版本 v(\d+)/)
    if (m) versionShort = ` (v${m[1]})`
    main = main.slice(0, idx).trim()
  }
  const norm = main.replace(/\\/g, '/')
  const parts = norm.split('/').filter(Boolean)
  const base = parts.length ? parts[parts.length - 1] : norm
  return base + versionShort
}

const emit = defineEmits([
  'restore-item',
  'perm-delete-item',
  'restore-dept',
  'perm-delete-dept',
  'trash-prev-page',
  'trash-next-page',
])
</script>

<style scoped>
.trash-page {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: #f9fafb;
}

.trash-header {
  background: #ffffff;
  border-bottom: 1px solid #e5e7eb;
  padding: 12px 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.trash-header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.trash-header-icon {
  width: 24px;
  height: 24px;
  color: #4b5563;
}

.trash-title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: #111827;
}

.trash-subtitle {
  margin: 4px 0 0 0;
  font-size: 13px;
  color: #6b7280;
}

.trash-header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.trash-mode-select {
  padding: 6px 10px;
  border-radius: 8px;
  border: 1px solid #d1d5db;
  font-size: 13px;
}

.trash-lib-select {
  min-width: 200px;
  padding: 6px 10px;
  border-radius: 8px;
  border: 1px solid #d1d5db;
  font-size: 13px;
}

.trash-clear-btn {
  padding: 6px 14px;
  border-radius: 999px;
  border: 1px solid #dc2626;
  background: #fff;
  color: #dc2626;
  font-size: 13px;
  cursor: pointer;
}

.trash-clear-btn:hover {
  background: #fef2f2;
}

.trash-body {
  flex: 1;
  padding: 20px 24px;
  overflow: auto;
}

.trash-table-card {
  background: #ffffff;
  border-radius: 12px;
  border: 1px solid #e5e7eb;
  overflow: hidden;
}

.trash-table {
  width: 100%;
  border-collapse: collapse;
}

.trash-table thead {
  background: #f9fafb;
  border-bottom: 1px solid #e5e7eb;
}

.trash-table th,
.trash-table td {
  padding: 10px 16px;
  font-size: 13px;
}

.trash-table th {
  text-align: left;
  font-weight: 600;
  color: #6b7280;
  text-transform: uppercase;
  font-size: 12px;
}

.trash-row:hover {
  background: #f9fafb;
}

.trash-cell-name {
  width: 28%;
}

.trash-name-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
}

.trash-file-icon {
  width: 18px;
  height: 18px;
  color: #9ca3af;
}

.trash-file-name {
  font-size: 14px;
  font-weight: 500;
  color: #111827;
}

.trash-cell-path {
  font-size: 13px;
  color: #4b5563;
}

.trash-lib-chain-cell {
  max-width: 520px;
  word-break: break-word;
}

.trash-cell-date {
  font-size: 13px;
  color: #4b5563;
}

.trash-cell-actions {
  text-align: left;
  white-space: nowrap;
}

.trash-btn-secondary,
.trash-btn-danger {
  padding: 4px 10px;
  font-size: 12px;
  border-radius: 999px;
  border: 1px solid transparent;
  cursor: pointer;
  background: #fff;
}

.trash-btn-secondary {
  border-color: #4a90e2;
  color: #4a90e2;
  margin-right: 8px;
}

.trash-btn-secondary:hover {
  background: #eff6ff;
}

.trash-btn-danger {
  border-color: #dc2626;
  color: #dc2626;
}

.trash-btn-danger:hover {
  background: #fef2f2;
}

.trash-btn-disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.trash-empty-card {
  background: #ffffff;
  border-radius: 12px;
  border: 1px solid #e5e7eb;
  padding: 48px 24px;
  text-align: center;
}

.trash-empty-icon {
  width: 56px;
  height: 56px;
  color: #d1d5db;
  margin-bottom: 12px;
}

.trash-empty-text {
  font-size: 16px;
  color: #4b5563;
  margin: 0 0 4px 0;
}

.trash-empty-hint {
  font-size: 13px;
  color: #9ca3af;
  margin: 0;
}

.empty-hint {
  color: var(--text-secondary);
  font-size: 14px;
  margin: 12px 0;
}

.trash-section {
  margin-bottom: 24px;
}

.trash-section:last-child {
  margin-bottom: 0;
}

.trash-section-title {
  margin: 0 0 12px 0;
  font-size: 15px;
  font-weight: 600;
  color: #374151;
}

/* 与 LibraryPage 当前库文件列表分页一致 */
.audit-pagination {
  margin-top: 8px;
  padding: 10px 0 8px;
  border-top: 1px solid #e5e7eb;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
  font-size: 12px;
  color: #6b7280;
  position: sticky;
  bottom: 0;
  z-index: 8;
  background: linear-gradient(to top, #fff 75%, rgba(255, 255, 255, 0.9) 100%);
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

.trash-empty-card-sm {
  padding: 24px;
}
</style>
