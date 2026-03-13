<template>
  <div v-if="isOpen">
    <!-- Backdrop -->
    <div class="notify-backdrop" @click="$emit('close')" />

    <!-- Panel -->
    <div class="notify-panel">
      <!-- Header -->
      <div class="notify-header">
        <div class="notify-header-main">
          <h3 class="notify-title">通知</h3>
          <p class="notify-subtitle">您有 {{ unreadCount }} 条未读通知</p>
        </div>
        <span v-if="unreadCount > 0" class="notify-badge">{{ unreadCount }} 条未读</span>
      </div>

      <!-- List -->
      <div class="notify-list">
        <div v-if="!notifications || !notifications.length" class="notify-empty">
          <Icons name="bell" class="notify-empty-icon" />
          <p class="notify-empty-text">暂无通知</p>
        </div>
        <div v-else class="notify-items">
          <div
            v-for="n in notifications"
            :key="n.id"
            class="notify-item"
            :class="{ 'notify-item-unread': !n.is_read }"
            @click="$emit('item-click', n)"
          >
            <div class="notify-icon-wrap">
              <Icons :name="iconName(n.type)" :class="['notify-icon', iconClass(n.type)]" />
            </div>
            <div class="notify-content">
              <div class="notify-title-row">
                <h4 class="notify-item-title" :class="{ 'unread': !n.is_read }">
                  {{ n.title }}
                </h4>
                <div v-if="!n.is_read" class="notify-dot" />
              </div>
              <p class="notify-message">{{ n.message }}</p>
              <div class="notify-time-row">
                <Icons name="clock" class="notify-time-icon" />
                <span class="notify-time-text">{{ formatTime(n.created_at) }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Footer -->
      <div class="notify-footer">
        <button class="notify-mark-all" type="button" @click="$emit('mark-all')">
          标记全部为已读
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import Icons from './Icons.vue'

const props = defineProps({
  isOpen: { type: Boolean, default: false },
  notifications: { type: Array, default: () => [] },
  unreadCount: { type: Number, default: 0 },
})

const emit = defineEmits(['close', 'mark-all', 'item-click'])

function iconName(type) {
  // 业务类型优先：文件分享 / 新文件 / 新版本
  if (type === 'file_share_to_me') return 'share-2'
  if (type === 'file_upload') return 'file-plus'
  if (type === 'file_new_version') return 'history'

  // 兼容通用级别
  if (type === 'success') return 'check-circle'
  if (type === 'error') return 'x-circle'
  if (type === 'warning') return 'bell'
  return 'file-text'
}

function iconClass(type) {
  if (type === 'file_share_to_me') return 'notify-icon-share'
  if (type === 'file_upload') return 'notify-icon-upload'
  if (type === 'file_new_version') return 'notify-icon-version'

  if (type === 'success') return 'notify-icon-success'
  if (type === 'error') return 'notify-icon-error'
  if (type === 'warning') return 'notify-icon-warning'
  return 'notify-icon-info'
}

function formatTime(s) {
  if (!s) return ''
  try {
    const d = new Date(s)
    return d.toLocaleString('zh-CN')
  } catch {
    return String(s)
  }
}
</script>

<style scoped>
.notify-backdrop {
  position: fixed;
  inset: 0;
  z-index: 40;
}

.notify-panel {
  position: fixed;
  top: 64px;
  right: 24px;
  width: 380px;
  max-height: calc(100vh - 96px);
  background: #ffffff;
  border-radius: 12px;
  box-shadow: 0 25px 50px -12px rgba(15, 23, 42, 0.45);
  border: 1px solid #e5e7eb;
  z-index: 50;
  display: flex;
  flex-direction: column;
}

.notify-header {
  padding: 12px 16px;
  border-bottom: 1px solid #e5e7eb;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.notify-header-main {
  display: flex;
  flex-direction: column;
}

.notify-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #111827;
}

.notify-subtitle {
  margin: 4px 0 0 0;
  font-size: 12px;
  color: #6b7280;
}

.notify-badge {
  padding: 2px 8px;
  border-radius: 999px;
  background: #fee2e2;
  color: #b91c1c;
  font-size: 11px;
  font-weight: 500;
}

.notify-list {
  flex: 1;
  overflow-y: auto;
}

.notify-empty {
  padding: 32px 16px 28px;
  text-align: center;
}

.notify-empty-icon {
  width: 40px;
  height: 40px;
  color: #d1d5db;
  margin: 0 auto 8px;
}

.notify-empty-text {
  font-size: 13px;
  color: #6b7280;
  margin: 0;
}

.notify-items {
  display: flex;
  flex-direction: column;
}

.notify-item {
  padding: 12px 16px;
  display: flex;
  gap: 10px;
  cursor: pointer;
  transition: background 0.15s ease;
}

.notify-item:hover {
  background: #f9fafb;
}

.notify-item-unread {
  background: #eff6ff;
}

.notify-icon-wrap {
  flex-shrink: 0;
  margin-top: 2px;
}

.notify-icon {
  width: 20px;
  height: 20px;
}

.notify-icon-success { color: #22c55e; }
.notify-icon-error { color: #ef4444; }
.notify-icon-warning { color: #f59e0b; }
.notify-icon-info { color: #3b82f6; }
.notify-icon-share { color: #8b5cf6; }   /* 文件被分享给你 */
.notify-icon-upload { color: #0ea5e9; }  /* 新文件上传 */
.notify-icon-version { color: #10b981; } /* 新版本上传 */

.notify-content {
  flex: 1;
  min-width: 0;
}

.notify-title-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 2px;
}

.notify-item-title {
  margin: 0;
  font-size: 14px;
  font-weight: 500;
  color: #374151;
}

.notify-item-title.unread {
  color: #111827;
}

.notify-dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: #4a90e2;
  flex-shrink: 0;
  margin-top: 4px;
}

.notify-message {
  margin: 2px 0 4px 0;
  font-size: 13px;
  color: #4b5563;
}

.notify-time-row {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: #9ca3af;
}

.notify-time-icon {
  width: 12px;
  height: 12px;
}

.notify-footer {
  padding: 8px 16px 10px;
  border-top: 1px solid #e5e7eb;
  background: #f9fafb;
}

.notify-mark-all {
  width: 100%;
  border: none;
  background: transparent;
  color: #4a90e2;
  font-size: 13px;
  cursor: pointer;
}

.notify-mark-all:hover {
  color: #357abd;
}
</style>

