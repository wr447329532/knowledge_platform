<template>
  <div class="app-content shared-page">
    <!-- Header，风格对齐回收站 -->
    <div class="shared-header">
      <div class="shared-header-left">
        <Icons name="share" class="shared-header-icon" />
        <div>
          <h1 class="shared-title">共享文件库</h1>
          <p class="shared-subtitle">查看我创建并共享的文件库，或他人共享给我的文件库</p>
        </div>
      </div>
    </div>

    <!-- Tabs -->
    <div class="shared-tabs">
      <button :class="['shared-tab', { active: sharedSubTab === 'mine' }]" @click="emit('tab', 'mine')">我的分享</button>
      <button :class="['shared-tab', { active: sharedSubTab === 'tome' }]" @click="emit('tab', 'tome')">分享给我</button>
    </div>

    <!-- Body，列表卡片风格对齐回收站 -->
    <div class="shared-page-body">
      <!-- 我的分享（文件库） -->
      <template v-if="sharedSubTab === 'mine'">
        <div v-if="mySharesLoading" class="shared-loading">
          <div class="shared-loading-dots">
            <span class="shared-loading-dot"></span>
            <span class="shared-loading-dot"></span>
            <span class="shared-loading-dot"></span>
          </div>
          <p class="shared-loading-text">加载中...</p>
        </div>
        <div v-else-if="mySharesList.length > 0" class="shared-table-card">
          <table class="shared-table">
            <thead>
              <tr>
                <th>文件库名称</th>
                <th>共享范围</th>
                <th>创建时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in mySharesList" :key="row.id">
                <td class="shared-td-name">
                  <div class="shared-file-name" :title="row.name">
                    <Icons name="folder" class="shared-file-icon" />
                    <span class="shared-file-path">{{ row.name }}</span>
                  </div>
                </td>
                <td class="shared-td-to">
                  <span class="shared-user">{{ row.share_scope }}</span>
                </td>
                <td class="shared-td-time">
                  {{ formatDateStr(row.created_at) }}
                </td>
                <td class="shared-td-action-last">
                  <button type="button" class="shared-link-btn" @click="emit('open-shared-lib', row)">查看</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-else class="shared-empty">
          <div class="shared-empty-icon-wrap"><Icons name="share" class="shared-empty-icon" /></div>
          <p class="shared-empty-title">暂无共享文件库</p>
          <p class="shared-empty-desc">创建文件库并设置为公开、部门可见或添加成员后，会在此显示</p>
        </div>
      </template>

      <!-- 分享给我（文件库） -->
      <template v-else-if="sharedSubTab === 'tome'">
        <div v-if="receivedSharesLoading" class="shared-loading">
          <div class="shared-loading-dots">
            <span class="shared-loading-dot"></span>
            <span class="shared-loading-dot"></span>
            <span class="shared-loading-dot"></span>
          </div>
          <p class="shared-loading-text">加载中...</p>
        </div>
        <div v-else-if="receivedSharesList.length > 0" class="shared-table-card">
          <table class="shared-table">
            <thead>
              <tr>
                <th>文件库名称</th>
                <th>所有者</th>
                <th>共享范围</th>
                <th>我的权限</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in receivedSharesList" :key="row.id">
                <td class="shared-td-name">
                  <div class="shared-file-name" :title="row.name">
                    <Icons name="folder" class="shared-file-icon" />
                    <span class="shared-file-path">{{ row.name }}</span>
                  </div>
                </td>
                <td class="shared-td-to">
                  <span class="shared-user">{{ row.owner_username }}</span>
                </td>
                <td>
                  <span class="shared-cell">{{ row.share_scope }}</span>
                </td>
                <td>
                  <span
                    class="shared-permission"
                    :class="row.can_write ? 'perm-download' : 'perm-read'"
                  >
                    {{ row.can_write ? '读写' : '只读' }}
                  </span>
                </td>
                <td class="shared-td-action-last">
                  <button type="button" class="shared-link-btn" @click="emit('open-shared-lib', row)">查看</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-else class="shared-empty">
          <div class="shared-empty-icon-wrap"><Icons name="share" class="shared-empty-icon" /></div>
          <p class="shared-empty-title">暂无他人共享给您的文件库</p>
          <p class="shared-empty-desc">当同事将文件库共享给您后，会在此显示</p>
        </div>
      </template>

      <!-- 兜底：默认为「我的分享」空状态 -->
      <template v-else>
        <div class="shared-empty">
          <div class="shared-empty-icon-wrap"><Icons name="share" class="shared-empty-icon" /></div>
          <p class="shared-empty-title">暂无共享文件库</p>
          <p class="shared-empty-desc">创建文件库并设置为公开、部门可见或添加成员后，会在此显示</p>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import Icons from './Icons.vue'

defineProps({
  sharedSubTab: String,
  mySharesList: Array,
  mySharesLoading: Boolean,
  receivedSharesList: Array,
  receivedSharesLoading: Boolean,
})

const emit = defineEmits(['tab', 'open-shared-lib'])

function formatDateStr(s) {
  if (!s) return ''
  return String(s).slice(0, 10)
}
</script>

<style scoped>
.shared-page {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: #f9fafb;
}

.shared-header {
  background: #ffffff;
  border-bottom: 1px solid #e5e7eb;
  padding: 12px 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.shared-header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.shared-header-icon {
  width: 24px;
  height: 24px;
  color: #4b5563;
}

.shared-title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
}

.shared-subtitle {
  margin: 2px 0 0;
  font-size: 12px;
  color: #6b7280;
}

.shared-tabs {
  flex-shrink: 0;
  display: flex;
  gap: 4px;
  padding: 8px 24px 0;
  background: #fff;
  border-bottom: 1px solid #e5e7eb;
}

.shared-tab {
  padding: 8px 16px;
  border: none;
  background: none;
  font-size: 14px;
  font-weight: 500;
  color: #6b7280;
  cursor: pointer;
  border-radius: 8px 8px 0 0;
  margin-bottom: -1px;
  transition: color 0.2s, background 0.2s;
}

.shared-tab:hover {
  color: #111827;
  background: #f9fafb;
}

.shared-tab.active {
  color: #111827;
  background: #ffffff;
  border-bottom: 2px solid #111827;
}

.shared-page-body {
  flex: 1;
  overflow: auto;
  padding: 16px 24px 24px;
}
.shared-loading {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 20px; padding: 64px 24px; color: #6b7280; font-size: 14px;
}
.shared-loading-dots { display: flex; align-items: center; justify-content: center; gap: 6px; }
.shared-loading-dot {
  width: 8px; height: 8px; border-radius: 50%; background: #4a90e2;
  animation: shared-dot 1.4s ease-in-out infinite both;
}
.shared-loading-dot:nth-child(1) { animation-delay: 0s; }
.shared-loading-dot:nth-child(2) { animation-delay: 0.16s; }
.shared-loading-dot:nth-child(3) { animation-delay: 0.32s; }
@keyframes shared-dot {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.5; }
  40% { transform: scale(1); opacity: 1; }
}
.shared-loading-text { margin: 0; }
.shared-table-card {
  background: #ffffff;
  border-radius: 8px;
  border: 1px solid #e5e7eb;
  overflow: hidden;
}
.shared-table {
  width: 100%;
  border-collapse: collapse;
  background: #fff;
}
.shared-table thead {
  background: #f9fafb;
}
.shared-table th,
.shared-table td {
  padding: 10px 16px;
  font-size: 13px;
  border-bottom: 1px solid #e5e7eb;
  text-align: left;
}
.shared-table th {
  font-weight: 600;
  color: #6b7280;
}
.shared-table tbody tr:hover {
  background: #f9fafb;
}
.shared-td-name { min-width: 0; }
.shared-td-action-last { text-align: right; white-space: nowrap; }
.shared-file-name { display: flex; align-items: center; gap: 10px; min-width: 0; }
.shared-file-icon { width: 18px; height: 18px; color: #4a90e2; flex-shrink: 0; }
.shared-file-path { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #111; font-weight: 500; }
.shared-td-to { color: #374151; }
.shared-user { font-weight: 500; color: #111; }
.shared-dept {
  display: inline-block; margin-left: 6px; padding: 0 6px;
  font-size: 12px; color: #6b7280; background: #f3f4f6; border-radius: 4px;
}
.shared-permission { display: inline-block; padding: 2px 8px; font-size: 12px; font-weight: 500; border-radius: 6px; }
.shared-permission.perm-read { background: #f3f4f6; color: #4b5563; }
.shared-permission.perm-download { background: #dbeafe; color: #1d4ed8; }
.shared-link-btn {
  padding: 4px 8px;
  border: none;
  background: none;
  font-size: 12px;
  color: #4a90e2;
  cursor: pointer;
}
.shared-link-btn:hover {
  text-decoration: underline;
}
.shared-link-btn.danger {
  color: #dc2626;
}
.shared-empty {
  max-width: 400px; margin: 0 auto; text-align: center; padding: 56px 32px;
  background: #fff; border-radius: 12px; border: 1px dashed var(--border);
}
.shared-empty-icon-wrap {
  width: 72px; height: 72px; margin: 0 auto 20px; border-radius: 50%;
  background: #f9fafb; display: flex; align-items: center; justify-content: center;
}
.shared-empty-icon { width: 32px; height: 32px; color: #d1d5db; }
.shared-empty-title { margin: 0 0 8px 0; font-size: 17px; font-weight: 600; color: #374151; }
.shared-empty-desc { margin: 0; font-size: 14px; color: #9ca3af; line-height: 1.5; }
.btn-small { font-size: 12px; padding: 4px 10px; }
</style>
