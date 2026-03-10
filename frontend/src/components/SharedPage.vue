<template>
  <div class="app-content shared-page">
    <div class="shared-page-header">
      <div class="shared-page-icon-wrap">
        <Icons name="share" class="shared-page-icon" />
      </div>
      <div class="shared-page-header-text">
        <h1 class="shared-page-title">共享文件</h1>
        <p class="shared-page-desc">管理我分享的权限，或查看他人分享给我的文件</p>
      </div>
    </div>

    <div class="shared-tabs">
      <button :class="['shared-tab', { active: sharedSubTab === 'mine' }]" @click="emit('tab', 'mine')">我分享的</button>
      <button :class="['shared-tab', { active: sharedSubTab === 'tome' }]" @click="emit('tab', 'tome')">分享给我的</button>
    </div>

    <div class="shared-page-body">
      <!-- 我分享的 -->
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
          <div class="shared-list-grid">
            <div class="shared-list-header">
              <span class="shared-col-name">名称</span>
              <span class="shared-col-to">共享给</span>
              <span class="shared-col-lib">所属资料库</span>
              <span class="shared-col-perm">权限</span>
              <span class="shared-col-action">操作</span>
            </div>
            <div v-for="row in mySharesList" :key="row.id" class="shared-list-row">
              <div class="shared-td-name">
                <div class="shared-file-name" :title="row.file_path">
                  <Icons name="file" class="shared-file-icon" />
                  <span class="shared-file-path">{{ row.file_path }}</span>
                </div>
              </div>
              <div class="shared-td-to">
                <span class="shared-user">{{ row.username }}</span>
                <span v-if="row.department_name" class="shared-dept">{{ row.department_name }}</span>
              </div>
              <div class="shared-td-lib">
                <span class="shared-cell">{{ row.library_name }}</span>
              </div>
              <div class="shared-td-perm">
                <span :class="['shared-permission', row.permission === 'download' ? 'perm-download' : 'perm-read']">
                  {{ row.permission === 'download' ? '可下载' : '只读' }}
                </span>
              </div>
              <div class="shared-td-action shared-td-action-last">
                <button type="button" class="btn-small danger" @click="emit('remove-share', row)">取消分享</button>
              </div>
            </div>
          </div>
        </div>
        <div v-else class="shared-empty">
          <div class="shared-empty-icon-wrap"><Icons name="share" class="shared-empty-icon" /></div>
          <p class="shared-empty-title">暂无分享记录</p>
          <p class="shared-empty-desc">在文件列表中点击「分享」，将文件共享给部门成员后，会在此显示</p>
        </div>
      </template>

      <!-- 分享给我的 -->
      <template v-else>
        <div v-if="receivedSharesLoading" class="shared-loading">
          <div class="shared-loading-dots">
            <span class="shared-loading-dot"></span>
            <span class="shared-loading-dot"></span>
            <span class="shared-loading-dot"></span>
          </div>
          <p class="shared-loading-text">加载中...</p>
        </div>
        <div v-else-if="receivedSharesList.length > 0" class="shared-table-card">
          <div class="shared-list-grid">
            <div class="shared-list-header">
              <span class="shared-col-name">名称</span>
              <span class="shared-col-to">分享者</span>
              <span class="shared-col-lib">所属资料库</span>
              <span class="shared-col-perm">权限</span>
              <span class="shared-col-action">操作</span>
            </div>
            <div v-for="row in receivedSharesList" :key="row.id" class="shared-list-row">
              <div class="shared-td-name">
                <div class="shared-file-name" :title="row.file_path">
                  <Icons name="file" class="shared-file-icon" />
                  <span class="shared-file-path">{{ row.file_path }}</span>
                </div>
              </div>
              <div class="shared-td-to">
                <span class="shared-user">{{ row.owner_username }}</span>
              </div>
              <div class="shared-td-lib">
                <span class="shared-cell">{{ row.library_name }}</span>
              </div>
              <div class="shared-td-perm">
                <span :class="['shared-permission', row.permission === 'download' ? 'perm-download' : 'perm-read']">
                  {{ row.permission === 'download' ? '可下载' : '只读' }}
                </span>
              </div>
              <div class="shared-td-action shared-td-action-last">
                <button type="button" class="shared-open-btn" @click="emit('open-shared-lib', row)">打开</button>
              </div>
            </div>
          </div>
        </div>
        <div v-else class="shared-empty">
          <div class="shared-empty-icon-wrap"><Icons name="share" class="shared-empty-icon" /></div>
          <p class="shared-empty-title">暂无他人分享给您的文件</p>
          <p class="shared-empty-desc">当同事将文件分享给您后，会在此显示</p>
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

const emit = defineEmits(['tab', 'remove-share', 'open-shared-lib'])
</script>

<style scoped>
.shared-page { display: flex; flex-direction: column; min-height: 0; padding: 0; }
.shared-page-header {
  background: #fff;
  border-bottom: 1px solid var(--border);
  padding: 20px 32px;
  display: flex;
  align-items: center;
  gap: 16px;
  flex-shrink: 0;
}
.shared-page-icon-wrap {
  width: 44px; height: 44px; border-radius: 10px;
  background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.shared-page-icon { width: 22px; height: 22px; color: #4a90e2; }
.shared-page-header-text { min-width: 0; }
.shared-page-title { margin: 0; font-size: 22px; font-weight: 600; color: #111; letter-spacing: -0.02em; }
.shared-page-desc { margin: 6px 0 0 0; font-size: 13px; color: #6b7280; line-height: 1.4; }
.shared-tabs {
  flex-shrink: 0; display: flex; gap: 4px;
  padding: 12px 32px 0; background: #fff; border-bottom: 1px solid var(--border);
}
.shared-tab {
  padding: 10px 20px; border: none; background: none; font-size: 14px; font-weight: 500;
  color: #6b7280; cursor: pointer; border-radius: 8px 8px 0 0; margin-bottom: -1px;
  transition: color 0.2s, background 0.2s;
}
.shared-tab:hover { color: #111; background: #f9fafb; }
.shared-tab.active { color: #4a90e2; background: #f3f4f6; border-bottom: 2px solid #4a90e2; }
.shared-page-body { flex: 1; overflow: auto; background: #f3f4f6; padding: 24px 32px; }
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
.shared-table-card { background: transparent; border-radius: 0; box-shadow: none; border: none; overflow: visible; }
.shared-list-grid { display: flex; flex-direction: column; width: 100%; }
.shared-list-header,
.shared-list-row {
  display: grid;
  grid-template-columns: 2.4fr 2fr 1.8fr 1.4fr 1.2fr;
  gap: 12px; padding: 10px 12px; align-items: center;
}
.shared-list-header {
  background: #f7f8fa; font-size: 13px; font-weight: 600;
  color: var(--text); border-bottom: 1px solid var(--border);
}
.shared-list-row { border-bottom: 1px solid #f3f4f6; }
.shared-list-row:hover { background: #fafafa; }
.shared-td-name { min-width: 0; }
.shared-col-perm, .shared-td-perm { text-align: center; }
.shared-col-action { text-align: right; }
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
.shared-td-action { text-align: left; padding-left: 20px; vertical-align: middle; }
.shared-open-btn {
  padding: 6px 14px; border: none; background: #4a90e2; color: #fff;
  font-size: 13px; font-weight: 500; cursor: pointer; border-radius: 6px; transition: background 0.2s;
}
.shared-open-btn:hover { background: #357abd; }
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
