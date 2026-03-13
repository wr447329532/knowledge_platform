<template>
  <!-- 文件库 / 部门文件：库列表 或 文件列表 -->
  <div class="app-content">
    <!-- 部门库视图：部门名左侧，无返回键 -->
    <div v-if="activeDeptId" class="card dept-files-card">
      <div class="dept-files-header">
        <div class="dept-files-title-left">
          <Icons name="building" class="dept-files-icon" />
          <h3 class="dept-files-title">{{ activeDeptInfo?.name || '部门库' }}</h3>
        </div>
      </div>
      <div class="dept-files-body">
        <p v-if="activeDeptLoading" class="empty-hint">加载中...</p>
        <p v-else-if="activeDeptErr" class="error-text">{{ activeDeptErr }}</p>
        <template v-else-if="activeDeptInfo && !activeDeptInfo.has_access">
          <div class="dept-lock">
            <Icons name="lock" class="dept-lock-icon" />
            <h4>访问受限</h4>
            <p>您没有权限访问「{{ activeDeptInfo.name }}」，请联系系统管理员或部门负责人。</p>
          </div>
        </template>
        <template v-else>
          <div v-if="activeDeptLibraries.length" class="dept-lib-grid">
            <div
              v-for="lib in activeDeptLibraries"
              :key="lib.id"
              class="lib-card dept-lib-card"
              @click="openDeptLib(lib)"
            >
              <div class="lib-card-icon"><Icons name="folder" /></div>
              <div class="lib-card-name">{{ lib.name }}</div>
              <p v-if="lib.description" class="lib-card-desc">{{ lib.description }}</p>
              <div class="dept-lib-meta">
                <span v-if="lib.is_owner" class="dept-lib-badge">我的</span>
                <span v-else class="dept-lib-badge shared">部门共享</span>
              </div>
            </div>
          </div>
          <div v-else class="dept-empty">
            <Icons name="folder" class="dept-empty-icon" />
            <p class="dept-empty-text">该部门暂无文件库</p>
            <p class="dept-empty-hint">
              点击右上角「新建文件库」，选择所属部门「{{ activeDeptInfo?.name }}」后创建
            </p>
          </div>
        </template>
      </div>
    </div>

    <!-- 我的文件库：库列表（行视图 / 卡片视图） -->
    <div class="lib-grid-wrap" v-else-if="!currentLib">
      <template v-if="libraries.length">
        <!-- 行视图：类 Finder / OneDrive 表格风格 -->
        <div v-if="fileViewMode === 'list'" class="lib-list-container">
          <div class="lib-list-table">
            <div class="lib-list-head">
              <div class="lib-col-name">名称</div>
              <div class="lib-col-desc">描述</div>
              <div class="lib-col-type">类型</div>
              <div class="lib-col-actions">操作</div>
            </div>
            <div
              v-for="lib in libraries"
              :key="lib.id"
              class="lib-list-row"
            >
              <div class="lib-col-name">
                <div class="lib-name-inner">
                  <input
                    type="checkbox"
                    class="lib-checkbox"
                    @click.stop
                  />
                  <Icons name="folder" class="lib-folder-icon" />
                  <a
                    href="#"
                    @click.prevent="selectLib(lib)"
                    class="lib-name-text"
                    :title="lib.name"
                  >
                    {{ lib.name }}
                  </a>
                  <span
                    v-if="!lib.is_owner"
                    class="lib-badge-shared"
                  >共享给我</span>
                </div>
              </div>
              <div class="lib-col-desc">
                {{ lib.description || '-' }}
              </div>
              <div class="lib-col-type">
                {{ lib.is_owner ? '我的库' : '共享库' }}
              </div>
              <div class="lib-col-actions">
                <div class="lib-actions">
                  <button
                    v-if="lib.is_owner"
                    class="btn-icon"
                    title="编辑"
                    @click.stop="openEditLib(lib)"
                  >
                    ⋯
                  </button>
                  <button
                    v-if="lib.is_owner"
                    class="btn-icon danger"
                    title="删除"
                    @click.stop="delLib(lib)"
                  >
                    🗑
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 网格视图：卡片宫格风格 -->
        <div v-else class="lib-grid">
          <div
            v-for="lib in libraries"
            :key="lib.id"
            class="lib-card"
            @click="selectLib(lib)"
          >
            <input
              type="checkbox"
              class="lib-card-checkbox"
              @click.stop
            />
            <button
              class="lib-card-more"
              title="更多操作"
              @click.stop
            >
              ⋯
            </button>
            <div class="lib-card-icon-wrap">
              <Icons name="folder" class="lib-card-icon" />
            </div>
            <div class="lib-card-text">
              <p class="lib-card-name" :title="lib.name">
                {{ lib.name }}
              </p>
              <p v-if="lib.description" class="lib-card-desc">
                {{ lib.description }}
              </p>
            </div>
            <div class="lib-card-meta">
              <span v-if="!lib.is_owner" class="lib-badge-shared">共享给我</span>
              <span v-else class="lib-badge-owner">我的库</span>
            </div>
          </div>
        </div>
      </template>
      <p v-else class="empty-hint">暂无文件库，请点击「新建文件库」。</p>
    </div>

    <!-- 当前库文件视图 -->
    <div
      v-else-if="currentLib"
      class="file-main file-main-dashboard card"
      :class="{ 'drop-zone-active': isDragging }"
      @dragover.prevent="onDragOver"
      @dragleave="onDragLeave"
      @drop.prevent="onFileDrop"
    >
      <div class="file-content-area">
        <p v-if="filesLoading" class="empty-hint">加载中...</p>
        <div v-else-if="searchResults.length" class="search-results-section">
          <div class="search-results-header">
            <span>搜索「{{ searchKeyword }}」共 {{ searchResults.length }} 项</span>
            <button class="btn-small" @click="clearSearch">清除</button>
          </div>
          <!-- 搜索结果行视图：沿用下方 file-grid 的样式和布局 -->
          <template v-if="fileViewMode === 'list'">
            <div class="file-grid">
              <div class="file-grid-header">
                <span>名称</span>
                <span>修改时间</span>
                <span>大小</span>
                <span>操作</span>
              </div>
              <div
                v-for="r in sortedSearchResults"
                :key="r.id"
                class="file-item file-item-row"
              >
                <div class="file-item-name">
                  <input
                    type="checkbox"
                    class="file-checkbox"
                    @click.stop
                  />
                  <a
                    v-if="r.is_dir"
                    href="#"
                    @click.prevent="goToPath(r.path)"
                    class="file-item-link"
                    :title="r.path"
                  >
                    <Icons name="folder" class="file-icon" />
                    <span class="file-name-text">{{ r.path.split('/').pop() }}/</span>
                  </a>
                  <a
                    v-else
                    href="#"
                    @click.prevent="onFileClick(r)"
                    class="file-item-link"
                    :title="r.path"
                  >
                    <Icons name="file" class="file-icon" />
                    <span class="file-name-text">{{ r.path.split('/').pop() }}</span>
                  </a>
                </div>
                <span class="file-meta">{{ formatDate(r.updated_at) }}</span>
                <span class="file-meta">{{ r.is_dir ? '-' : formatSize(r.size) }}</span>
                <span class="file-actions-wrap">
                  <button
                    type="button"
                    class="actions-trigger"
                    @click.stop="toggleActionMenu('s-' + r.id)"
                    title="操作"
                  >⋮</button>
                  <div
                    v-if="openActionMenuId === 's-' + r.id"
                    class="action-dropdown"
                    @click.stop
                  >
                    <button
                      v-if="!r.is_dir && (r.can_download !== false)"
                      class="btn-small"
                      @click="download(r.id); closeActionMenu()"
                    >下载</button>
                    <button
                      v-if="currentLib?.is_owner"
                      class="btn-small"
                      @click="openShare(r); closeActionMenu()"
                    >分享</button>
                    <button
                      v-if="currentLib?.is_writeable"
                      class="btn-small"
                      @click="openRename(r); closeActionMenu()"
                    >重命名</button>
                  </div>
                </span>
              </div>
            </div>
          </template>
          <!-- 搜索结果网格视图：沿用文件卡片样式 -->
          <div v-else class="file-cards-grid">
            <div
              v-for="r in sortedSearchResults"
              :key="r.id"
              class="file-card"
              @click="r.is_dir ? goToPath(r.path) : onFileClick(r)"
            >
              <div class="file-card-icon-wrap">
                <Icons :name="r.is_dir ? 'folder' : 'file'" class="file-card-icon" />
              </div>
              <div class="file-card-text">
                <div class="file-card-name" :title="r.path">
                  {{ r.path.split('/').pop() }}{{ r.is_dir ? '/' : '' }}
                </div>
                <div class="file-card-meta">
                  {{ r.is_dir ? '-' : formatSize(r.size) }} · {{ formatDate(r.updated_at) }}
                </div>
              </div>
              <button
                type="button"
                class="file-card-menu"
                @click.stop="toggleActionMenu('s-' + r.id)"
                title="操作"
              >⋮</button>
              <div
                v-if="openActionMenuId === 's-' + r.id"
                class="action-dropdown file-card-dropdown"
                @click.stop
              >
                <button
                  v-if="!r.is_dir && (r.can_download !== false)"
                  class="btn-small"
                  @click="download(r.id); closeActionMenu()"
                >下载</button>
                <button
                  v-if="currentLib?.is_owner"
                  class="btn-small"
                  @click="openShare(r); closeActionMenu()"
                >分享</button>
                <button
                  v-if="currentLib?.is_writeable"
                  class="btn-small"
                  @click="openRename(r); closeActionMenu()"
                >重命名</button>
              </div>
            </div>
          </div>
        </div>

        <!-- 正常文件列表视图 -->
        <template v-if="fileViewMode === 'list'">
          <div class="file-grid">
            <div class="file-grid-header">
              <span>名称</span>
              <span>修改时间</span>
              <span>大小</span>
              <span>操作</span>
            </div>
            <div
              v-if="pathPrefix"
              class="file-item file-item-row"
            >
              <a
                href="#"
                @click.prevent="goUp"
                class="file-item-link"
              ><Icons name="folder" class="file-icon" /> .. 上一级</a>
              <span class="file-meta">-</span>
              <span class="file-meta">-</span>
              <span class="file-actions-wrap" />
            </div>
            <div
              v-for="f in sortedFiles"
              :key="f.id"
              class="file-item file-item-row"
            >
              <div class="file-item-name">
                <input
                  type="checkbox"
                  class="file-checkbox"
                  @click.stop
                />
                <a
                  v-if="f.is_dir"
                  href="#"
                  @click.prevent="enterDir(f)"
                  class="file-item-link"
                  :title="f.path"
                >
                  <Icons name="folder" class="file-icon" />
                  <span class="file-name-text">{{ f.path.split('/').pop() }}/</span>
                </a>
                <a
                  v-else
                  href="#"
                  @click.prevent="onFileClick(f)"
                  class="file-item-link"
                  :title="f.path"
                >
                  <Icons name="file" class="file-icon" />
                  <span class="file-name-text">{{ f.path.split('/').pop() }}</span>
                </a>
              </div>
              <span class="file-meta">{{ formatDate(f.updated_at) }}</span>
              <span class="file-meta">{{ f.is_dir ? '-' : formatSize(f.size) }}</span>
              <span class="file-actions-wrap">
                <button
                  type="button"
                  class="actions-trigger"
                  @click.stop="toggleActionMenu('f-' + f.id)"
                  title="操作"
                >⋮</button>
                <div
                  v-if="openActionMenuId === 'f-' + f.id"
                  class="action-dropdown"
                  @click.stop
                >
                  <template v-if="!f.is_dir">
                    <button
                      v-if="f.can_download !== false"
                      class="btn-small"
                      @click="download(f.id); closeActionMenu()"
                    >下载</button>
                    <button
                      class="btn-small"
                      @click="openVersions(f); closeActionMenu()"
                    >版本</button>
                    <button
                      v-if="currentLib?.is_owner"
                      class="btn-small"
                      @click="openShare(f); closeActionMenu()"
                    >分享</button>
                  </template>
                  <button
                    v-if="currentLib?.is_writeable"
                    class="btn-small"
                    @click="openRename(f); closeActionMenu()"
                  >重命名</button>
                  <button
                    v-if="currentLib?.is_writeable"
                    class="btn-small danger"
                    @click="delFile(f); closeActionMenu()"
                  >删除</button>
                </div>
              </span>
            </div>
          </div>
        </template>
        <!-- 网格视图：文件卡片宫格 -->
        <div v-else class="file-cards-grid">
          <div
            v-if="pathPrefix"
            class="file-card file-card-up"
            @click="goUp"
          >
            <div class="file-card-icon"><Icons name="folder" /></div>
            <div class="file-card-name">.. 上一级</div>
          </div>
          <div
            v-for="f in sortedFiles"
            :key="f.id"
            class="file-card"
            @click="f.is_dir ? enterDir(f) : onFileClick(f)"
          >
            <div class="file-card-icon-wrap">
              <Icons :name="f.is_dir ? 'folder' : 'file'" class="file-card-icon" />
            </div>
            <div class="file-card-text">
              <div class="file-card-name" :title="f.path">
                {{ f.path.split('/').pop() }}{{ f.is_dir ? '/' : '' }}
              </div>
              <div class="file-card-meta">
                {{ f.is_dir ? '-' : formatSize(f.size) }} · {{ formatDate(f.updated_at) }}
              </div>
            </div>
            <button
              type="button"
              class="file-card-menu"
              @click.stop="toggleActionMenu('f-' + f.id)"
              title="操作"
            >⋮</button>
            <div
              v-if="openActionMenuId === 'f-' + f.id"
              class="action-dropdown file-card-dropdown"
              @click.stop
            >
              <template v-if="!f.is_dir">
                <button
                  v-if="f.can_download !== false"
                  class="btn-small"
                  @click="download(f.id); closeActionMenu()"
                >下载</button>
                <button
                  class="btn-small"
                  @click="openVersions(f); closeActionMenu()"
                >版本</button>
                <button
                  v-if="currentLib?.is_owner"
                  class="btn-small"
                  @click="openShare(f); closeActionMenu()"
                >分享</button>
              </template>
              <button
                v-if="currentLib?.is_writeable"
                class="btn-small"
                @click="openRename(f); closeActionMenu()"
              >重命名</button>
              <button
                v-if="currentLib?.is_writeable"
                class="btn-small danger"
                @click="delFile(f); closeActionMenu()"
              >删除</button>
            </div>
          </div>
        </div>

        <p
          v-if="currentLib && !filesLoading && files.length === 0 && !searchResults.length"
          class="empty-hint"
        >
          当前目录为空，可上传文件或新建目录。
        </p>
      </div>
    </div>
  </div>
</template>

<script setup>
import Icons from './Icons.vue'

const props = defineProps({
  activeDeptId: Number,
  activeDeptInfo: Object,
  activeDeptLibraries: { type: Array, default: () => [] },
  activeDeptLoading: Boolean,
  activeDeptErr: String,
  currentLib: Object,
  libraries: { type: Array, default: () => [] },
  fileViewMode: { type: String, default: 'list' },
  isDragging: Boolean,
  filesLoading: Boolean,
  files: { type: Array, default: () => [] },
  searchResults: { type: Array, default: () => [] },
  sortedSearchResults: { type: Array, default: () => [] },
  sortedFiles: { type: Array, default: () => [] },
  searchKeyword: { type: String, default: '' },
  pathPrefix: { type: String, default: '' },
  openActionMenuId: [String, Number, null],
  formatDate: { type: Function, required: true },
  formatSize: { type: Function, required: true },
  // 行为回调（由父组件 Home 提供）
  openDeptLib: { type: Function, required: true },
  selectLib: { type: Function, required: true },
  openEditLib: { type: Function, required: true },
  delLib: { type: Function, required: true },
  onFileDrop: { type: Function, required: true },
  goToPath: { type: Function, required: true },
  onFileClick: { type: Function, required: true },
  toggleActionMenu: { type: Function, required: true },
  download: { type: Function, required: true },
  openShare: { type: Function, required: true },
  openRename: { type: Function, required: true },
  goUp: { type: Function, required: true },
  openVersions: { type: Function, required: true },
  delFile: { type: Function, required: true },
  enterDir: { type: Function, required: true },
  clearSearch: { type: Function, required: true },
  closeActionMenu: { type: Function, required: true },
  onDragOver: { type: Function, required: true },
  onDragLeave: { type: Function, required: true },
})
</script>

<style scoped>
.lib-grid-wrap {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.lib-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 4px 0;
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
  grid-template-columns: minmax(0, 3fr) minmax(0, 3fr) minmax(0, 1.5fr) 120px;
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
  grid-template-columns: minmax(0, 3fr) minmax(0, 3fr) minmax(0, 1.5fr) 120px;
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

.lib-checkbox {
  width: 14px;
  height: 14px;
  border-radius: 4px;
  border: 1px solid #d1d5db;
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

.lib-badge-shared,
.lib-badge-owner {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 500;
}

.lib-badge-shared {
  background-color: #eff6ff;
  color: #1d4ed8;
}

.lib-badge-owner {
  background-color: #ecfdf5;
  color: #15803d;
}

.lib-grid {
  margin-top: 4px;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 12px;
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

.lib-card-checkbox {
  position: absolute;
  top: 8px;
  left: 8px;
  width: 14px;
  height: 14px;
  border-radius: 4px;
  border: 1px solid #d1d5db;
  opacity: 0;
  transition: opacity 0.15s ease;
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

.lib-card:hover .lib-card-checkbox,
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

/* 文件列表（当前库「全部文件」） */
.file-content-area {
  padding: 12px 0 8px;
}

.file-grid {
  background: #ffffff;
  border-radius: 10px;
  border: 1px solid #e5e7eb;
  /* 允许操作菜单在容器外浮出，否则会被裁掉 */
  overflow: visible;
}

.file-grid-header {
  display: grid;
  grid-template-columns: minmax(0, 4fr) minmax(0, 2fr) minmax(0, 1.5fr) 170px;
  padding: 10px 20px;
  background: #f9fafb;
  border-bottom: 1px solid #e5e7eb;
  font-size: 12px;
  font-weight: 600;
  color: #6b7280;
  text-transform: uppercase;
}

.file-grid-header span:nth-child(4) {
  text-align: right;
  padding-right: 8px;
}

.file-item-row {
  display: grid;
  grid-template-columns: minmax(0, 4fr) minmax(0, 2fr) minmax(0, 1.5fr) 170px;
  padding: 9px 20px;
  align-items: center;
  font-size: 14px;
  border-bottom: 1px solid #f3f4f6;
  transition: background-color 0.12s ease;
}

.file-item-row:hover {
  background-color: #f9fafb;
}

.file-item-name {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  overflow: hidden;
}

.file-checkbox {
  width: 14px;
  height: 14px;
  border-radius: 4px;
  border: 1px solid #d1d5db;
}

.file-item-link {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  flex: 1 1 auto;
  max-width: 100%;
  min-width: 0;
  overflow: hidden;
  text-decoration: none;
  color: #111827;
}

.file-icon {
  width: 18px;
  height: 18px;
  color: #4b5563;
  flex-shrink: 0;
}

.file-name-text {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-weight: 500;
}

.file-meta {
  color: #6b7280;
  font-size: 13px;
}

.file-actions-wrap {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  position: relative;
}

.file-cards-grid {
  margin-top: 8px;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 12px;
}

.file-card {
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

.file-card:hover {
  border-color: #4a90e2;
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.08);
  transform: translateY(-1px);
}

.file-card-icon-wrap {
  width: 48px;
  height: 48px;
  border-radius: 14px;
  background: #eff6ff;
  display: flex;
  align-items: center;
  justify-content: center;
}

.file-card-icon {
  width: 28px;
  height: 28px;
  color: #4a90e2;
}

.file-card-text {
  width: 100%;
  text-align: center;
}

.file-card-name {
  font-size: 13px;
  font-weight: 500;
  color: #111827;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.file-card-meta {
  margin-top: 2px;
  font-size: 12px;
  color: #6b7280;
}

.file-card-menu {
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

.file-card:hover .file-card-menu {
  opacity: 1;
}

.file-card-menu:hover {
  background-color: #e5e7eb;
  color: #111827;
}

/* 文件操作下拉菜单：竖排卡片样式 */
.actions-trigger {
  border: none;
  background: transparent;
  width: 28px;
  height: 28px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: #6b7280;
  font-size: 18px;
}

.actions-trigger:hover {
  background-color: #e5e7eb;
  color: #111827;
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

.file-card-dropdown {
  right: 4px;
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
</style>

