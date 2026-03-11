<template>
  <div class="trash-page">
    <!-- Header -->
    <div class="trash-header">
      <div class="trash-header-left">
        <Icons name="trash" class="trash-header-icon" />
        <div>
          <h1 class="trash-title">回收站</h1>
          <p class="trash-subtitle">资料库与文件可恢复，30 天后自动彻底删除</p>
        </div>
      </div>
      <div class="trash-header-right">
        <select
          class="trash-lib-select"
          :value="trashLibId"
          @change="emit('lib-change', $event.target.value)"
        >
          <option value="">选择资料库（查看文件回收站）</option>
          <option v-for="lib in libraries" :key="lib.id" :value="lib.id">{{ lib.name }}</option>
        </select>
        <button
          v-if="trashList?.length"
          class="trash-clear-btn"
          type="button"
          @click="onClear"
        >
          清空文件回收站
        </button>
      </div>
    </div>

    <!-- Body -->
    <div class="trash-body">
      <!-- 已删除的资料库 -->
      <section class="trash-section">
        <h2 class="trash-section-title">已删除的资料库</h2>
        <p v-if="trashLibraryLoading" class="empty-hint">加载中...</p>
        <div v-else-if="trashLibraryList?.length" class="trash-table-card">
          <table class="trash-table">
            <thead>
              <tr>
                <th>资料库名称</th>
                <th>删除时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="lib in trashLibraryList"
                :key="lib.id"
                class="trash-row"
              >
                <td class="trash-cell-name">
                  <div class="trash-name-wrap">
                    <Icons name="folder" class="trash-file-icon" />
                    <span class="trash-file-name">{{ lib.name }}</span>
                  </div>
                </td>
                <td class="trash-cell-date">{{ formatDate(lib.deleted_at) }}</td>
                <td class="trash-cell-actions">
                  <button type="button" class="trash-btn-secondary" @click="emit('restore-lib', lib.id)">
                    恢复
                  </button>
                  <button type="button" class="trash-btn-danger" @click="emit('perm-delete-lib', lib.id)">
                    永久删除
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-else class="trash-empty-card trash-empty-card-sm">
          <p class="trash-empty-text">无已删除的资料库</p>
        </div>
      </section>

      <!-- 文件回收站 -->
      <section class="trash-section">
        <h2 class="trash-section-title">已删除的文件</h2>
        <p v-if="trashLoading" class="empty-hint">加载中...</p>
      <template v-else>
        <template v-if="trashLibId">
          <div v-if="trashList?.length" class="trash-table-card">
            <table class="trash-table">
              <thead>
                <tr>
                  <th>名称</th>
                  <th>原始位置</th>
                  <th>删除时间</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="f in trashList"
                  :key="f.id"
                  class="trash-row"
                >
                  <td class="trash-cell-name">
                    <div class="trash-name-wrap">
                      <Icons :name="f.is_dir ? 'folder' : 'file-text'" class="trash-file-icon" />
                      <span class="trash-file-name">{{ f.path.split('/').pop() }}</span>
                    </div>
                  </td>
                  <td class="trash-cell-path">
                    {{ f.path.replace(/\\/g, '/') }}
                  </td>
                  <td class="trash-cell-date">
                    {{ formatDate(f.deleted_at) }}
                  </td>
                  <td class="trash-cell-actions">
                    <button type="button" class="trash-btn-secondary" @click="emit('restore', f.id)">
                      恢复
                    </button>
                    <button type="button" class="trash-btn-danger" @click="emit('perm-delete', f.id)">
                      永久删除
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-else class="trash-empty-card">
            <Icons name="trash" class="trash-empty-icon" />
            <p class="trash-empty-text">该资料库回收站为空</p>
            <p class="trash-empty-hint">删除的文件会显示在这里，30 天后自动清理</p>
          </div>
        </template>
        <p v-else class="empty-hint">请选择资料库查看文件回收站。</p>
      </template>
      </section>
    </div>
  </div>
</template>

<script setup>
import Icons from './Icons.vue'

defineProps({
  libraries: Array,
  trashLibId: [String, Number],
  trashList: Array,
  trashLoading: Boolean,
  trashLibraryList: Array,
  trashLibraryLoading: Boolean,
  formatDate: Function,
})

const emit = defineEmits(['lib-change', 'restore', 'perm-delete', 'clear', 'restore-lib', 'perm-delete-lib'])

function onClear() {
  emit('clear')
}
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

.trash-cell-date {
  font-size: 13px;
  color: #4b5563;
}

.trash-cell-actions {
  text-align: right;
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

.trash-empty-card-sm {
  padding: 24px;
}
</style>
