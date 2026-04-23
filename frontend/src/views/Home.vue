<template>
  <div class="app-layout" :class="{ 'app-layout-admin': tab === 'sys' }">

    <!-- 左侧导航 -->
    <AppSidebar
      v-if="tab !== 'sys'"
      :me="me"
      :active-tab="tab"
      :active-dept-id="activeDeptId"
      :trash-mode="trashMode"
      @nav="onSidebarNav"
      @dept-select="handleDeptSelect"
    />

    <!-- 右侧主区域 -->
    <div class="app-main">

      <!-- 顶部工具栏 -->
      <AppTopbar
        v-if="tab !== 'sys'"
        :active-tab="tab"
        :active-dept-id="activeDeptId"
        :active-dept-name="activeDeptInfo?.name || ''"
        :current-lib="currentLib"
        v-model:searchKeyword="searchKeyword"
        v-model:fileSortOrder="fileSortOrder"
        v-model:fileViewMode="fileViewMode"
        :breadcrumb-segments="breadcrumbSegments"
        :notify-count="unreadNotifyCount"
        :me="me"
        @search="doSearchNow"
        @new-lib="openNewLib"
        @new-sub-lib="openNewLibSub"
        @upload="openUploadModal"
        @clear-lib="onTopbarClearLib"
        @set-path="p => pathPrefix = p"
        @toggle-notify="toggleNotifyPanel"
        @go-account="goAccount"
        @go-admin="goAdmin"
        @go-dept-manage="goDeptManage"
        @logout="logout"
      />

      <div class="app-main-scroll">
        <!-- Toast 提示 -->
        <Transition name="toast">
          <div v-if="successMessage" class="success-toast">{{ successMessage }}</div>
        </Transition>
        <Transition name="toast">
          <div v-if="errorMessage" class="error-toast">{{ errorMessage }}</div>
        </Transition>

        <!-- 部门视图：选中部门且未在顶部搜索时显示；有搜索关键词时改显 LibraryPage 以展示全局搜文件/库结果 -->
        <DepartmentFiles
          v-if="showDepartmentFilesPanel"
          :key="deptFilesReloadKey"
          :me="me"
          :active-dept-id="activeDeptId"
          :reload-key="deptFilesReloadKey"
          :file-sort-order="fileSortOrder"
          :file-view-mode="fileViewMode"
          @back="clearDeptView"
          @open-lib="openDeptLib"
          @edit-lib="openEditLib"
          @del-lib="delLib"
          @move-lib="openMoveLib"
        />

        <!-- 我的文件库：未选中部门时显示 -->
        <LibraryPage
          v-else-if="tab === 'lib'"
          :active-dept-id="null"
          :active-dept-info="null"
          :active-dept-libraries="[]"
          :active-dept-loading="false"
          :active-dept-err="''"
          :current-lib="currentLib"
          :libraries="sortedLibraries"
          :file-view-mode="fileViewMode"
          :is-dragging="isDragging"
          :files-loading="filesLoading"
          :files="files"
          :search-results="searchResults"
          :sorted-search-results="sortedSearchResults"
          :sorted-files="sortedFiles"
          :search-keyword="searchKeyword"
          :search-applied="searchApplied"
          :root-search-libraries="rootSearchLibraries"
          :root-search-files="rootSearchFiles"
          :path-prefix="pathPrefix"
          :child-libraries="libChildrenLibraries"
          :open-action-menu-id="openActionMenuId"
          :format-date="formatDate"
          :format-size="formatSize"
          :open-dept-lib="openDeptLib"
          :select-lib="selectLib"
          :open-edit-lib="openEditLib"
          :move-lib="openMoveLib"
          :del-lib="delLib"
          :on-file-drop="onFileDrop"
          :go-to-path="goToPath"
          :on-file-click="onFileClick"
          :open-global-search-file-result="openGlobalSearchFileResult"
          :open-global-search-file-preview="openGlobalSearchFilePreview"
          :toggle-action-menu="toggleActionMenu"
          :download="download"
          :open-share="openShare"
          :open-rename="openRename"
          :go-up="goUp"
          :open-versions="openVersions"
          :del-file="delFile"
          :enter-dir="enterDir"
          :clear-search="clearSearch"
          :close-action-menu="closeActionMenu"
          :on-drag-over="onDragOver"
          :on-drag-leave="onDragLeave"
          :libraries-limit="librariesLimit"
          :libraries-offset="librariesOffset"
          :libraries-has-more="librariesHasMore"
          :files-limit="filesLimit"
          :files-offset="filesOffset"
          :files-has-more="filesHasMore"
          @prev-page="goPrevLibrariesPage"
          @next-page="goNextLibrariesPage"
          @prev-files-page="goPrevFilesPage"
          @next-files-page="goNextFilesPage"
        />

        <!-- 共享文件 -->
        <SharedPage
          v-if="tab === 'shared'"
          :shared-sub-tab="sharedSubTab"
          :my-shares-list="filteredMySharesList"
          :my-shares-loading="mySharesLoading"
          :received-shares-list="filteredReceivedSharesList"
          :received-shares-loading="receivedSharesLoading"
          @tab="onSharedTab"
          @open-shared-lib="openSharedLib"
        />


        <!-- 回收站 -->
        <TrashPage
          v-if="tab === 'trash'"
          :mode="trashMode"
          :trash-items="filteredTrashItems"
          :trash-loading="trashLoading"
          :dept-trash-list="filteredDeptTrashList"
          :dept-trash-loading="deptTrashLoading"
          :libraries="libraries"
          :format-date="formatDate"
          @restore-item="restoreTrashItem"
          @perm-delete-item="permDeleteTrashItem"
          @restore-dept="restoreDeptFile"
          @perm-delete-dept="permDeleteDeptFile"
        />

        <NotificationPanel
          :is-open="showNotifyPanel"
          :notifications="notifications"
          :unread-count="unreadNotifyCount"
          @close="showNotifyPanel = false"
          @mark-all="markAllNotifications"
          @item-click="onNotificationClick"
        />

      </div><!-- /app-main-scroll -->

    </div><!-- /app-main -->

    <!-- ============ 弹窗区 ============ -->

    <!-- 新建文件库 / 子资料库（与上传文件弹窗同一套样式） -->
    <div v-if="showNewLib" class="upload-modal-overlay" @click.self="closeNewLibModal">
      <div class="upload-modal-card new-lib-modal-card">
        <div class="upload-modal-header">
          <div>
            <h2 class="upload-modal-title">{{ newLibParentId ? '新建子资料库' : '新建文件库' }}</h2>
            <p v-if="newLibParentId" class="upload-modal-subtitle">
              子资料库继承一级资料库的访问成员与导出策略，仅可填写名称与描述。
            </p>
          </div>
          <button
            type="button"
            class="upload-modal-close"
            :disabled="newLibCreating"
            aria-label="关闭"
            @click="closeNewLibModal"
          >
            <Icons name="x" class="upload-modal-close-icon" />
          </button>
        </div>
        <div
          class="upload-modal-body new-lib-modal-body"
          :class="{ 'new-lib-body-picker-open': newLibDeptPickerOpen || newLibModePickerOpen }"
        >
          <div class="form-group">
            <label>名称 <span class="label-opt">必填</span></label>
            <input v-model="newLibName" placeholder="文件库名称" />
          </div>
          <div class="form-group">
            <label>描述 <span class="label-opt">选填</span></label>
            <input v-model="newLibDesc" placeholder="简要描述" />
          </div>
          <div v-if="!newLibParentId" class="form-group">
            <label for="new-lib-dept-trigger">所属部门</label>
            <div class="move-target-picker">
              <button
                id="new-lib-dept-trigger"
                type="button"
                class="move-target-picker-trigger"
                :disabled="newLibCreating"
                :aria-expanded="newLibDeptPickerOpen"
                aria-haspopup="listbox"
                @click.stop="
                  newLibModePickerOpen = false;
                  newLibDeptPickerOpen = !newLibDeptPickerOpen
                "
              >
                <span class="move-target-picker-value">{{ selectedNewLibDeptLabel }}</span>
                <span class="move-target-picker-chevron" aria-hidden="true">▾</span>
              </button>
              <div
                v-if="newLibDeptPickerOpen"
                class="move-target-picker-panel"
                role="listbox"
                @click.stop
              >
                <button
                  v-for="opt in newLibDeptOptions"
                  :key="'nd-' + (opt.value == null ? 'x' : opt.value)"
                  type="button"
                  role="option"
                  class="move-target-picker-option"
                  :class="{ selected: newLibDeptOptionSelected(opt) }"
                  @click="selectNewLibDept(opt)"
                >
                  {{ opt.label }}
                </button>
              </div>
            </div>
            <p class="form-hint">选择部门则创建为部门共享库，部门成员均可访问</p>
          </div>
          <template v-if="!newLibParentId">
            <div class="form-group">
              <label for="new-lib-mode-trigger">访问权限</label>
              <div class="move-target-picker">
                <button
                  id="new-lib-mode-trigger"
                  type="button"
                  class="move-target-picker-trigger"
                  :disabled="newLibCreating"
                  :aria-expanded="newLibModePickerOpen"
                  aria-haspopup="listbox"
                  @click.stop="
                    newLibDeptPickerOpen = false;
                    newLibModePickerOpen = !newLibModePickerOpen
                  "
                >
                  <span class="move-target-picker-value">{{ selectedNewLibModeLabel }}</span>
                  <span class="move-target-picker-chevron" aria-hidden="true">▾</span>
                </button>
                <div
                  v-if="newLibModePickerOpen"
                  class="move-target-picker-panel"
                  role="listbox"
                  @click.stop
                >
                  <button
                    v-for="opt in newLibModeOptions"
                    :key="'nm-' + opt.value"
                    type="button"
                    role="option"
                    class="move-target-picker-option"
                    :class="{ selected: newLibModeOptionSelected(opt) }"
                    @click="selectNewLibMode(opt)"
                  >
                    {{ opt.label }}
                  </button>
                </div>
              </div>
              <p class="form-hint">个人库支持「仅自己 / 指定成员 / 公开」；选择所属部门后，将作为部门库对部门成员开放。</p>
            </div>
            <div class="form-group" v-if="['self_plus', 'dept_plus', 'members_only'].includes(newLibMode)">
              <label>指定成员</label>
              <div class="member-selector">
                <p v-if="newLibMembersLoading" class="empty-hint">成员列表加载中...</p>
                <template v-else>
                  <p v-if="!newLibUsers.length" class="empty-hint">暂未获取到用户列表，可能是当前账号无权限查看全部用户，请联系管理员协助配置。</p>
                  <div v-else class="member-multi-dropdown">
                    <div class="member-select-trigger" @click="showNewLibMemberPanel = !showNewLibMemberPanel">
                      <span v-if="!newLibMembers.length">请选择成员</span>
                      <span v-else>已选择 {{ newLibMembers.length }} 位成员</span>
                    </div>
                    <div v-if="showNewLibMemberPanel" class="member-panel">
                      <input v-model="newLibMemberKeyword" placeholder="搜索姓名或邮箱..." class="member-search" />
                      <div class="member-list">
                        <div v-for="u in filteredNewLibUsers" :key="u.id" class="member-option">
                          <input type="checkbox" :value="u.id" v-model="newLibMembers" />
                          <span class="member-name">{{ u.username || u.email }}</span>
                          <span class="member-email" v-if="u.email">（{{ u.email }}）</span>
                        </div>
                      </div>
                      <div class="member-panel-actions">
                        <button type="button" class="btn-small primary" @click="showNewLibMemberPanel = false">确定</button>
                      </div>
                    </div>
                  </div>
                  <p v-if="newLibMembers.length" class="form-hint">已选择 {{ newLibMembers.length }} 位成员。</p>
                </template>
              </div>
            </div>
            <div class="form-group">
              <label>导出权限</label>
              <div class="toggle-row">
                <span class="toggle-label">允许导出原文件（下载）</span>
                <label class="toggle">
                  <input type="checkbox" v-model="newLibAllowDownload" />
                  <span class="toggle-track" aria-hidden="true"></span>
                </label>
              </div>
              <p class="form-hint">关闭后，成员仅可受控预览（带水印），不可下载原文件。</p>
            </div>
          </template>
          <p v-if="err" class="text-danger new-lib-modal-err">{{ err }}</p>
        </div>
        <div class="upload-modal-footer">
          <div class="upload-modal-footer-left" />
          <div class="upload-modal-footer-actions">
            <button type="button" class="upload-btn-secondary" :disabled="newLibCreating" @click="closeNewLibModal">
              取消
            </button>
            <button type="button" class="upload-btn-primary" :disabled="newLibCreating" @click="createLib">
              {{ newLibCreating ? '创建中…' : '确定' }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 删除资料库确认 -->
    <div v-if="showDeleteLibConfirm" class="modal">
      <div class="card">
        <h3>删除资料库</h3>
        <p style="margin-top:8px;">
          确定将资料库「{{ libToDelete?.name }}」移入回收站吗？<br />
          可在回收站中恢复或永久删除。
        </p>
        <div class="modal-actions" style="margin-top:16px;">
          <button class="primary danger" @click="doConfirmDeleteLib">确定删除</button>
          <button @click="showDeleteLibConfirm = false; libToDelete = null">取消</button>
        </div>
      </div>
    </div>

    <!-- 移动资料库 -->
    <div v-if="showMoveLib" class="modal">
      <div class="card move-lib-modal-card">
        <h3>移动资料库</h3>
        <p class="form-hint" style="margin-top:8px;">
          将「{{ libToMove?.name }}」移动到目标位置。个人库与公开库按类型互挂；部门库仅限同一部门内调整，不可挂到其他部门的资料库下；也可先作为一级资料库。子库跨权限树时请先移到一级根目录。
        </p>
        <div v-if="moveTargetsLoading" class="empty-hint" style="margin-top:12px;">加载可选位置…</div>
        <template v-else-if="moveTargets.length">
          <div class="form-group" style="margin-top:12px;">
            <label for="move-target-picker-trigger">目标位置</label>
            <div class="move-target-picker">
              <button
                id="move-target-picker-trigger"
                type="button"
                class="move-target-picker-trigger"
                :disabled="moveTargetsLoading || moveLibSubmitting"
                :aria-expanded="moveTargetPickerOpen"
                aria-haspopup="listbox"
                @click.stop="moveTargetPickerOpen = !moveTargetPickerOpen"
              >
                <span class="move-target-picker-value">{{ selectedMoveTargetLabel }}</span>
                <span class="move-target-picker-chevron" aria-hidden="true">▾</span>
              </button>
              <div
                v-if="moveTargetPickerOpen"
                class="move-target-picker-panel"
                role="listbox"
                @click.stop
              >
                <button
                  v-for="t in moveTargets"
                  :key="moveTargetOptionKey(t)"
                  type="button"
                  role="option"
                  class="move-target-picker-option"
                  :class="{ selected: moveTargetOptionValue(t) === moveTargetKey }"
                  @click="selectMoveTargetOption(t)"
                >
                  {{ t.label }}
                </button>
              </div>
            </div>
          </div>
        </template>
        <p v-else class="empty-hint" style="margin-top:12px;">当前没有可移动的目标位置（名称冲突、层级超限或无写权限）。</p>
        <p v-if="err" class="text-danger">{{ err }}</p>
        <div class="modal-actions" style="margin-top:16px;">
          <button
            class="primary"
            :disabled="moveLibSubmitting || !moveTargets.length || moveTargetsLoading"
            @click="confirmMoveLib"
          >
            {{ moveLibSubmitting ? '移动中…' : '确定' }}
          </button>
          <button :disabled="moveLibSubmitting" @click="closeMoveLibModal">取消</button>
        </div>
      </div>
    </div>

    <!-- 上传文件（新 UI：拖拽、多文件、进度） -->
    <div v-if="showUpload" class="upload-modal-overlay" @click.self="abandonUploadModal">
      <div class="upload-modal-card">
        <div class="upload-modal-header">
          <div>
            <template v-if="uploadStep === 'confirm'">
              <h2 class="upload-modal-title">版本确认</h2>
              <p v-if="vmQueue.length > 1" class="upload-modal-subtitle">
                {{ vmQueue.length }} 个文件待确认
              </p>
            </template>
            <template v-else>
              <h2 class="upload-modal-title">上传文件</h2>
              <p v-if="uploadFiles.length" class="upload-modal-subtitle">
                {{ uploadCompletedCount }} / {{ uploadFiles.length }} 个文件已上传
                <template v-if="uploadPendingNotQueuedCount > 0">
                  · 另有 {{ uploadPendingNotQueuedCount }} 个待上传（请先点「开始上传」）
                </template>
              </p>
            </template>
          </div>
          <button type="button" class="upload-modal-close" @click="abandonUploadModal" aria-label="关闭">
            <Icons name="x" class="upload-modal-close-icon" />
          </button>
        </div>
        <div class="upload-modal-body">
          <template v-if="uploadStep === 'list'">
            <input
              ref="uploadModalInputRef"
              type="file"
              multiple
              class="upload-modal-input-hidden"
              @change="onUploadFileSelect"
            />
            <template v-if="!uploadFiles.length">
            <div
              class="upload-dropzone"
              :class="{ 'upload-dropzone-active': uploadDropzoneActive }"
              @dragenter.prevent="uploadDropzoneActive = true"
              @dragleave.prevent="uploadDropzoneActive = false"
              @dragover.prevent
              @drop.prevent="onUploadDrop"
              @click="triggerUploadInput"
            >
              <Icons name="cloud-up" class="upload-dropzone-icon" />
              <h3 class="upload-dropzone-title">拖拽文件到此处上传</h3>
              <p class="upload-dropzone-hint">或点击此处选择文件</p>
              <p class="upload-dropzone-limit">支持上传任意文件类型，单个文件不超过 500MB</p>
            </div>
          </template>
          <template v-else>
            <div
              class="upload-dropzone upload-dropzone-small"
              :class="{ 'upload-dropzone-active': uploadDropzoneActive }"
              @dragenter.prevent="uploadDropzoneActive = true"
              @dragleave.prevent="uploadDropzoneActive = false"
              @dragover.prevent
              @drop.prevent="onUploadDrop"
              @click="triggerUploadInput"
            >
              <Icons name="cloud-up" class="upload-dropzone-icon-small" />
              <p class="upload-dropzone-hint-small">点击或拖拽添加更多文件</p>
            </div>
            <div class="upload-file-list">
              <div
                v-for="uf in uploadFiles"
                :key="uf.id"
                class="upload-file-item"
              >
                <div class="upload-file-item-icon">
                  <Icons v-if="getUploadFileIcon(uf.file.name) === 'image'" name="file-text" class="icon-purple" />
                  <Icons v-else-if="getUploadFileIcon(uf.file.name) === 'code'" name="file-text" class="icon-blue" />
                  <Icons v-else name="file-text" class="icon-gray" />
                </div>
                <div class="upload-file-item-main">
                  <div class="upload-file-item-row">
                    <p class="upload-file-item-name">{{ uf.file.name }}</p>
                    <div class="upload-file-item-actions">
                      <Icons v-if="uf.status === 'uploading'" name="loader" class="upload-file-loader" />
                      <Icons v-else-if="uf.status === 'success'" name="check-circle" class="upload-file-success" />
                      <Icons v-else-if="uf.status === 'error'" name="x-circle" class="upload-file-error" />
                      <button type="button" class="upload-file-remove" @click.stop="removeUploadFile(uf.id)" aria-label="移除">
                        <Icons name="x" class="upload-file-remove-icon" />
                      </button>
                    </div>
                  </div>
                  <div class="upload-file-item-meta">
                    <span class="upload-file-item-size">{{ formatUploadSize(uf.file.size) }}</span>
                    <span v-if="uf.status === 'pending'" class="upload-file-item-status">等待上传</span>
                    <span v-else-if="uf.status === 'uploading'" class="upload-file-item-progress">{{ uf.progress }}%</span>
                    <span v-else-if="uf.status === 'success'" class="upload-file-item-status success">上传成功</span>
                    <span v-else-if="uf.status === 'error'" class="upload-file-item-status error">{{ uf.error || '上传失败' }}</span>
                  </div>
                  <div v-if="uf.status !== 'pending'" class="upload-file-progress-bar">
                    <div
                      class="upload-file-progress-fill"
                      :class="{ error: uf.status === 'error', success: uf.status === 'success' }"
                      :style="{ width: uf.status === 'error' ? '100%' : uf.progress + '%' }"
                    />
                  </div>
                </div>
              </div>
            </div>
          </template>
          </template>
          <template v-else>
            <div style="display:flex;align-items:center;gap:10px;padding:10px 14px;
              background:var(--bg-page,#f5f6f8);border-radius:8px;margin-bottom:16px">
              <div style="width:32px;height:32px;background:#dbeafe;border-radius:6px;
                display:flex;align-items:center;justify-content:center;flex-shrink:0">
                <Icons name="file-text" style="width:16px;height:16px;color:#2563eb" />
              </div>
              <div style="flex:1;min-width:0">
                <div style="font-size:13px;font-weight:500;overflow:hidden;
                  text-overflow:ellipsis;white-space:nowrap">{{ vmFile?.name }}</div>
                <div style="font-size:11px;color:var(--text-secondary);margin-top:2px;
                  display:flex;align-items:center;gap:6px;flex-wrap:wrap">
                  <span>{{ formatUploadSize(vmFile?.size) }}</span>
                  <span v-if="vmKeyword" style="padding:1px 6px;background:#e6f1fb;color:#185fa5;border-radius:4px">识别关键词：{{ vmKeyword }}</span>
                </div>
              </div>
            </div>
            <div style="margin-bottom:12px">
              <div style="font-size:12px;color:var(--text-secondary);margin-bottom:6px;
                display:flex;align-items:center;justify-content:space-between">
                <span>找到 {{ vmSearchResults.length }} 个可能相关的文件</span>
                <span style="font-size:11px">点击选择，或修改关键词重新搜索</span>
              </div>
              <div style="display:flex;gap:8px;margin-bottom:8px">
                <input v-model="vmKeyword" type="text" placeholder="搜索关键词"
                  style="flex:1;padding:8px 12px;border:1px solid var(--border);border-radius:8px;font-size:13px"
                  @input="vmOnSearchInput" @keydown.enter.prevent="vmDoSearch" />
                <button type="button" @click="vmDoSearch" class="btn-small primary">搜索</button>
              </div>
              <div style="max-height:200px;overflow-y:auto;border:1px solid var(--border);border-radius:8px;background:#fff">
                <div v-for="r in vmSearchResults" :key="r.id"
                  :class="['vm-result-row', { selected: vmSelectedEntry?.id === r.id }]"
                  @click="vmSelectedEntry = r; vmMode = 'version'">
                  <Icons name="file-text" style="width:16px;height:16px;color:#6b7280;flex-shrink:0" />
                  <span style="flex:1;font-size:13px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{{ r.path }}</span>
                  <span v-if="r.size != null" style="font-size:11px;color:var(--text-secondary)">{{ formatSize(r.size) }}</span>
                </div>
                <div v-if="vmSearchResults.length === 0" style="padding:16px;text-align:center;color:var(--text-secondary);font-size:13px">无匹配结果，将作为新文件上传</div>
              </div>
              <p v-if="vmSearchResults.length === 0" style="font-size:12px;color:var(--text-secondary);margin-top:6px">可选择「作为新文件上传」或修改关键词重新搜索</p>
            </div>
            <div v-if="vmQueue.length > 1" style="padding:8px 0;font-size:12px;color:var(--text-secondary);text-align:center">还有 {{ vmQueue.length - 1 }} 个文件需要确认</div>
          </template>
        </div>
        <div class="upload-modal-footer">
          <template v-if="uploadStep === 'list'">
            <div class="upload-modal-footer-left">
              <template v-if="uploadFiles.length">
                共 {{ uploadFiles.length }} 个文件
                <span v-if="uploadFiles.some(f => f.status === 'error')" class="upload-modal-footer-error"> · 部分文件上传失败</span>
              </template>
            </div>
            <div class="upload-modal-footer-actions">
              <button type="button" class="upload-btn-secondary" @click="abandonUploadModal">取消</button>
              <button
                type="button"
                class="upload-btn-primary"
                :disabled="uploadPendingNotQueuedCount === 0 || uploadFiles.some(f => f.status === 'uploading')"
                @click="startPendingDirectUploads"
              >开始上传</button>
              <button type="button" class="upload-btn-primary" :disabled="uploadCompletedCount === 0" @click="finishUploadModal">完成</button>
            </div>
          </template>
          <template v-else>
            <button type="button" @click="vmSkip"
              style="padding:7px 14px;border:none;border-radius:8px;cursor:pointer;font-size:13px;background:transparent;color:var(--text-secondary)">跳过，作为新文件上传</button>
            <button @click="vmDoUpload"
              :disabled="vmMode === 'version' && vmSearchResults.length > 0 && !vmSelectedEntry"
              style="padding:7px 16px;border:none;border-radius:8px;cursor:pointer;font-size:13px;background:#185fa5;color:#fff;font-weight:500"
              :style="(vmMode === 'version' && vmSearchResults.length > 0 && !vmSelectedEntry) ? 'opacity:.5;cursor:not-allowed' : ''">
              {{ vmMode === 'new' || !vmSelectedEntry ? '作为新文件上传' : '确认上传为新版本' }}
            </button>
          </template>
        </div>
      </div>
    </div>

    <!-- 新建目录 -->
    <div v-if="showMkdir" class="modal">
      <div class="card">
        <h3>新建目录</h3>
        <input v-model="mkdirPath" placeholder="目录路径，如 docs/reports" style="width:100%;" />
        <p v-if="err" class="text-danger">{{ err }}</p>
        <div class="modal-actions">
          <button class="primary" @click="doMkdir">确定</button>
          <button @click="showMkdir = false">取消</button>
        </div>
      </div>
    </div>

    <!-- 预览 -->
    <div v-if="showPreview" class="modal" @click.self="closePreview">
      <div class="card preview-card">
        <h3>{{ previewFileName }}</h3>
        <div v-if="previewLoading" class="preview-loading">加载中...</div>
        <div v-else-if="previewErr" class="text-danger">{{ previewErr }}</div>
        <div v-else class="preview-body">
          <img v-if="previewType === 'image'" :src="previewUrl" alt="" class="preview-img" />
          <template v-else-if="previewType === 'pdf'">
            <iframe v-if="previewUrl" :src="previewUrl" class="preview-iframe" title="PDF预览" />
            <a v-if="previewUrl" :href="previewUrl" target="_blank" rel="noopener" class="btn-small" style="margin-top:8px">在新窗口打开</a>
          </template>
          <pre v-else-if="previewType === 'text'" class="preview-text">{{ previewText }}</pre>
        </div>
        <div class="modal-actions"><button @click="closePreview">关闭</button></div>
      </div>
    </div>

    <!-- 版本历史 -->
    <div v-if="showVersions" class="modal">
      <div class="card versions-card">
        <h3>版本历史</h3>
        <div class="versions-fileinfo">
          <span class="versions-fileinfo-label">文件名</span>
          <span class="versions-fileinfo-text">
            {{ versionEntryFilename || versionEntryName || '当前文件' }}
          </span>
        </div>
        <table class="versions-table">
          <thead>
            <tr>
              <th style="width: 60px;">版本</th>
              <th style="width: 90px;">大小</th>
              <th style="width: 120px;">上传者</th>
              <th style="width: 160px;">上传时间</th>
              <th style="width: 240px; text-align: right;">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="v in versions" :key="v.id">
              <td>{{ v.version_no }}</td>
              <td>{{ v.size }}</td>
              <td>{{ v.uploaded_by || '-' }}</td>
              <td>{{ formatDate(v.uploaded_at) }}</td>
              <td style="width: 240px; text-align: right;">
                <button
                  type="button"
                  class="btn-small"
                  @click.stop.prevent="download(versionEntryId, v.version_no)"
                >
                  下载
                </button>
                <button
                  type="button"
                  class="btn-small"
                  style="margin-left: 8px;"
                  @click.stop.prevent="previewVersion(v)"
                >
                  预览
                </button>
                <button
                  type="button"
                  class="btn-small btn-danger"
                  style="margin-left: 8px;"
                  :disabled="!canDeleteVersion()"
                  @click.stop.prevent="deleteVersionRecord(v)"
                >
                  删除版本
                </button>
              </td>
            </tr>
          </tbody>
        </table>
        <div class="modal-actions"><button @click="showVersions = false">关闭</button></div>
      </div>
    </div>

    <!-- 修改密码 -->
    <div v-if="showChangePw" class="modal">
      <div class="card">
        <h3>修改密码</h3>
        <div style="margin-bottom: 8px;">
          <input v-model="oldPassword" type="password" placeholder="原密码" style="width:100%;" />
        </div>
        <div style="margin-bottom: 8px;">
          <input v-model="newPassword" type="password" placeholder="新密码（8位以上，含大小写、数字、特殊字符）" style="width:100%;" />
        </div>
        <div style="margin-bottom: 8px;">
          <input v-model="newPassword2" type="password" placeholder="再次输入新密码" style="width:100%;" />
        </div>
        <p v-if="err" class="text-danger">{{ err }}</p>
        <div class="modal-actions">
          <button class="primary" @click="doChangePassword">确定</button>
          <button @click="showChangePw = false; err = ''">取消</button>
        </div>
      </div>
    </div>

    <!-- 新建根部门 -->
    <div v-if="showAddRootDept" class="modal">
      <div class="card">
        <h3>新建根部门</h3>
        <input v-model="newRootDeptName" placeholder="部门名称" style="width:100%; margin-bottom:12px;" />
        <p v-if="err" class="text-danger">{{ err }}</p>
        <div class="modal-actions">
          <button class="primary" @click="doAddRootDept">确定</button>
          <button @click="showAddRootDept = false; err = ''">取消</button>
        </div>
      </div>
    </div>

    <!-- 新建子部门 -->
    <div v-if="showAddSubDept" class="modal">
      <div class="card">
        <h3>新建子部门</h3>
        <p v-if="addSubDeptParent" style="margin-bottom:12px; color:#6b7280; font-size:14px;">上级部门：{{ addSubDeptParent.name }}</p>
        <input v-model="addSubDeptName" placeholder="部门名称" style="width:100%; margin-bottom:12px;" />
        <p v-if="err" class="text-danger">{{ err }}</p>
        <div class="modal-actions">
          <button class="primary" @click="doAddSubDept">确定</button>
          <button @click="showAddSubDept = false; addSubDeptParent = null; err = ''">取消</button>
        </div>
      </div>
    </div>

    <!-- 编辑部门 -->
    <div v-if="showEditDept" class="modal">
      <div class="card">
        <h3>编辑部门</h3>
        <input v-model="editDeptName" placeholder="部门名称" style="width:100%; margin-bottom:12px;" />
        <p v-if="err" class="text-danger">{{ err }}</p>
        <div class="modal-actions">
          <button class="primary" @click="doSaveEditDept">保存</button>
          <button @click="showEditDept = false; err = ''">取消</button>
        </div>
      </div>
    </div>

    <!-- 创建用户 -->
    <div v-if="showCreateUser" class="modal">
      <div class="card user-modal-card">
        <h3>添加新用户</h3>
        <div class="user-modal-grid">
          <div class="form-group">
            <label>姓名 / 用户名 <span class="label-opt">必填</span></label>
            <input v-model="newUserUsername" placeholder="如 张三" />
          </div>
          <div class="form-group">
            <label>邮箱（用于登录） <span class="label-opt">必填</span></label>
            <input v-model="newUserEmail" type="email" placeholder="如 user@example.com" />
          </div>
          <div class="form-group">
            <label>密码 <span class="label-opt">必填</span></label>
            <input v-model="newUserPassword" type="password" placeholder="8+ 位，含大小写、数字、特殊字符" />
          </div>
          <div class="form-group">
            <label>部门 <span class="label-opt">选填</span></label>
            <select v-model="newUserDeptId" class="admin-select">
              <option :value="null">未分配部门</option>
              <option v-for="opt in deptOptionsForUser" :key="opt.id" :value="opt.id">
                {{ '　'.repeat(opt.level) + opt.name }}
              </option>
            </select>
          </div>
          <div class="form-group">
            <label>角色 <span class="label-opt">选填</span></label>
            <select v-model="newUserRole" class="admin-select">
              <option value="user">普通用户</option>
              <option value="admin">管理员</option>
            </select>
          </div>
        </div>
        <p v-if="err" class="text-danger">{{ err }}</p>
        <div class="modal-actions">
          <button class="primary" @click="doCreateUserModal">创建用户</button>
          <button @click="closeCreateUser">取消</button>
        </div>
      </div>
    </div>

    <!-- 重命名 -->
    <div v-if="showRename" class="modal">
      <div class="card">
        <h3>重命名</h3>
        <div class="form-group">
          <label>新路径</label>
          <input v-model="renameNewPath" placeholder="如 docs/readme.txt" />
        </div>
        <p v-if="err" class="text-danger">{{ err }}</p>
        <div class="modal-actions">
          <button class="primary" @click="doRename">确定</button>
          <button @click="closeRename">取消</button>
        </div>
      </div>
    </div>

    <!-- 文件分享 -->
    <div v-if="showShare" class="modal">
      <div class="card" style="min-width: 420px;">
        <h3>分享文件 - {{ shareFile?.path?.split('/').pop() }}</h3>
        <div class="add-member-row">
          <select v-model="shareAddUserId" style="min-width: 140px;">
            <option value="">选择用户</option>
            <option v-for="u in shareAddableUsers" :key="u.id" :value="u.id">{{ u.username }}</option>
          </select>
          <select v-model="sharePermission" style="width: 140px;">
            <option value="read">只读（可预览）</option>
            <option value="download">可下载</option>
          </select>
          <button class="primary btn-small" @click="doAddShare">添加</button>
        </div>
        <table class="members-table">
          <thead><tr><th>用户</th><th>权限</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="s in shareList" :key="s.id">
              <td>{{ s.username }}</td>
              <td>
                <span class="badge badge-user">
                  {{ s.permission === 'download' ? '可下载' : '只读' }}
                </span>
              </td>
              <td><button class="btn-small danger" @click="doRemoveShare(s)">移除</button></td>
            </tr>
          </tbody>
        </table>
        <p v-if="shareList.length === 0" class="empty-hint">暂无分享</p>
        <p v-if="err" class="text-danger" style="margin-top: 12px;">{{ err }}</p>
        <div class="modal-actions" style="margin-top: 16px;">
          <button @click="closeShare">关闭</button>
        </div>
      </div>
    </div>

    <!-- 编辑资料库 -->
    <div v-if="showEditLib" class="modal">
      <div class="card">
        <h3>编辑资料库</h3>
        <div style="margin-bottom: 8px;">
          <input v-model="editLibName" placeholder="名称" style="width:100%;" />
        </div>
        <div style="margin-bottom: 8px;">
          <input v-model="editLibDesc" placeholder="描述（选填）" style="width:100%;" />
        </div>
        <p v-if="editLibDepth > 1" class="form-hint" style="margin-bottom:10px;">
          子资料库的访问成员与导出策略继承一级资料库，请在一级资料库中修改；此处仅可修改名称与描述。
        </p>
        <div v-if="editLibDepth <= 1" class="form-group" style="margin-bottom: 8px;">
          <label>访问权限</label>
          <select v-model="editLibMode" class="admin-select" style="width:100%;" @change="onEditLibModeChange">
            <option v-if="!editLibDepartmentId" value="self">仅自己</option>
            <option v-if="!editLibDepartmentId" value="self_plus">仅自己 + 指定成员</option>
            <option v-if="!editLibDepartmentId" value="members_only">仅指定成员</option>
            <option v-if="!editLibDepartmentId" value="public">公开（所有用户）</option>
            <option v-if="editLibDepartmentId" value="dept">所属部门</option>
            <option v-if="editLibDepartmentId" value="dept_plus">所属部门 + 指定成员</option>
          </select>
          <p class="form-hint">个人库可控制是否公开或仅指定成员；部门库始终对所在部门成员开放，可额外指定跨部门成员。</p>
        </div>
        <div class="form-group" v-if="editLibDepth <= 1 && ['self_plus', 'dept_plus', 'members_only'].includes(editLibMode)">
          <label>指定成员</label>
          <div class="member-selector">
            <p v-if="editLibMembersLoading" class="empty-hint">成员列表加载中...</p>
            <template v-else>
              <p v-if="!editLibUsers.length" class="empty-hint">暂未获取到用户列表，可能是当前账号无权限查看全部用户，请联系管理员协助配置。</p>
              <div v-else class="member-multi-dropdown">
                <div class="member-select-trigger" @click="showEditLibMemberPanel = !showEditLibMemberPanel">
                  <span v-if="!editLibMembers.length">请选择成员</span>
                  <span v-else>已选择 {{ editLibMembers.length }} 位成员</span>
                </div>
                <div v-if="showEditLibMemberPanel" class="member-panel">
                  <input v-model="editLibMemberKeyword" placeholder="搜索姓名或邮箱..." class="member-search" />
                  <div class="member-list">
                    <div v-for="u in filteredEditLibUsers" :key="u.id" class="member-option">
                      <input type="checkbox" :value="u.id" v-model="editLibMembers" />
                      <span class="member-name">{{ u.username || u.email }}</span>
                      <span class="member-email" v-if="u.email">（{{ u.email }}）</span>
                    </div>
                  </div>
                  <div class="member-panel-actions">
                    <button type="button" class="btn-small primary" @click="showEditLibMemberPanel = false">确定</button>
                  </div>
                </div>
              </div>
              <p v-if="editLibMembers.length" class="form-hint">已选择 {{ editLibMembers.length }} 位成员。</p>
            </template>
          </div>
        </div>
        <div v-if="editLibDepth <= 1" class="form-group" style="margin-bottom: 8px;">
          <label>导出权限</label>
          <div class="toggle-row">
            <span class="toggle-label">允许导出原文件（下载）</span>
            <label class="toggle">
              <input type="checkbox" v-model="editLibAllowDownload" />
              <span class="toggle-track" aria-hidden="true"></span>
            </label>
          </div>
          <p class="form-hint">关闭后，成员仅可受控预览（带水印），不可下载原文件。</p>
        </div>
        <p v-if="err" class="text-danger">{{ err }}</p>
        <div class="modal-actions">
          <button class="primary" @click="saveEditLib">保存</button>
          <button @click="showEditLib = false">取消</button>
        </div>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import * as api from '../api/client'
import Icons from '../components/Icons.vue'
import DepartmentTree from '../components/DepartmentTree.vue'
import DepartmentTableRow from '../components/DepartmentTableRow.vue'
import LibraryPage from '../components/LibraryPage.vue'
import DepartmentFiles from '../components/DepartmentFiles.vue'
import AppSidebar from '../components/AppSidebar.vue'
import AppTopbar from '../components/AppTopbar.vue'
import SharedPage from '../components/SharedPage.vue'
import TrashPage from '../components/TrashPage.vue'
import NotificationPanel from '../components/NotificationPanel.vue'

const router = useRouter()
const route = useRoute()
const me = ref(null)
const tab = ref('lib')
const subTab = ref('users')
const sysSearchKeyword = ref('')
const showNewDropdown = ref(false)
const newDropdownRef = ref(null)
const deptTreeRefreshKey = ref(0)
const libraries = ref([])
const librariesLimit = ref(20)
const librariesOffset = ref(0)
const librariesHasMore = ref(false)
const filesLimit = ref(20)
const filesOffset = ref(0)
const filesHasMore = ref(false)
/** 防止多次 loadLibraries 乱序返回把列表覆盖成空或过期的页 */
let librariesLoadSeq = 0
const currentLib = ref(null)
/** 创建子库时的父库 id；一级新建时为 null */
const newLibParentId = ref(null)
/** 当前打开库的直接子库（用于库内列表上方展示） */
const libChildrenLibraries = ref([])
const pathPrefix = ref('')
const fileSortOrder = ref('modified')
const fileViewMode = ref('list')
const files = ref([])
const filesLoading = ref(false)
const successMessage = ref('')
const errorMessage = ref('')
const showNewLib = ref(false)
const newLibName = ref('')
const newLibDesc = ref('')
const newLibDepartmentId = ref(null)
const newLibVisibility = ref('private')
const newLibMode = ref('self')
const newLibAllowDownload = ref(false)
const newLibUsers = ref([])
const newLibMembers = ref([])
const newLibMembersLoading = ref(false)
const showNewLibMemberPanel = ref(false)
const newLibMemberKeyword = ref('')
const newLibCreating = ref(false)
const showUpload = ref(false)
const uploadPath = ref('')
const selectedFile = ref(null)
const showDeleteLibConfirm = ref(false)
const libToDelete = ref(null)
const showMoveLib = ref(false)
const libToMove = ref(null)
const moveTargets = ref([])
const moveTargetKey = ref('')
const moveTargetsLoading = ref(false)
const moveLibSubmitting = ref(false)
const moveTargetPickerOpen = ref(false)
const newLibDeptPickerOpen = ref(false)
const newLibModePickerOpen = ref(false)
const uploadFiles = ref([])
const uploadDropzoneActive = ref(false)
const uploadModalInputRef = ref(null)
const showMkdir = ref(false)
const mkdirPath = ref('')
const err = ref('')
const trashItems = ref([])
const trashLoading = ref(false)
const trashMode = ref('personal')
const deptTrashList = ref([])
const deptTrashLoading = ref(false)
const mySharesList = ref([])
const mySharesLoading = ref(false)
const sharedSubTab = ref('mine')
const receivedSharesList = ref([])
const receivedSharesLoading = ref(false)
const auditList = ref([])
const showVersions = ref(false)
const versions = ref([])
const versionEntryId = ref(null)
const versionEntryName = ref('')
const versionEntryFilename = ref('')
const fileInput = ref(null)
const newUserEmail = ref('')
const newUserUsername = ref('')
const newUserPassword = ref('')
const showCreateUser = ref(false)
const newUserIsSuperuser = ref(false)
const newUserDeptId = ref(null)
const newUserRole = ref('user')
const userCreateSuccess = ref('')
const userList = ref([])
const showChangePw = ref(false)
const oldPassword = ref('')
const newPassword = ref('')
const newPassword2 = ref('')
const showEditLib = ref(false)
/** 1=一级库；>1 为子库，编辑时不展示成员与导出等继承项 */
const editLibDepth = ref(1)
const editLibId = ref(null)
const editLibName = ref('')
const editLibDesc = ref('')
const editLibDepartmentId = ref(null)
const editLibMode = ref('self')
const editLibAllowDownload = ref(true)
const editLibUsers = ref([])
const editLibMembers = ref([])
const editLibMembersLoading = ref(false)
const editLibInitialMembers = ref([])
const showEditLibMemberPanel = ref(false)
const editLibMemberKeyword = ref('')
const auditUsername = ref('')
const auditAction = ref('')
const auditStartDate = ref('')
const auditEndDate = ref('')
const searchKeyword = ref('')
const searchResults = ref([])
const searchApplied = ref(false)
const rootSearchLibraries = ref([])
const rootSearchFiles = ref([])
const showRename = ref(false)
const renameEntry = ref(null)
const renameNewPath = ref('')
const isDragging = ref(false)
const showShare = ref(false)
const shareFile = ref(null)
const showPreview = ref(false)
const openActionMenuId = ref(null)
const previewUrl = ref('')
const previewFileName = ref('')
const previewType = ref('')
const previewText = ref('')
const previewErr = ref('')
const previewLoading = ref(false)
const shareList = ref([])
const shareAddableUsers = ref([])
const shareAddUserId = ref('')
const sharePermission = ref('read')
const showAddRootDept = ref(false)
const newRootDeptName = ref('')
const userFilterStatus = ref('')
const userFilterRole = ref('')
const deptTreeForTable = ref([])
const showEditDept = ref(false)
const editDeptNode = ref(null)
const editDeptName = ref('')
const showAddSubDept = ref(false)
const addSubDeptParent = ref(null)
const addSubDeptName = ref('')
const activeDeptId = ref(null)
const activeDeptInfo = ref(null)
const activeDeptLibraries = ref([])
const activeDeptLoading = ref(false)
const activeDeptErr = ref('')
const deptFilesReloadKey = ref(0)
const uploadErr = ref('')
let searchDebounceTimer = null

const uploadStep = ref('list')  // 'list' | 'confirm'
const vmQueue = ref([])        // 待确认队列：{ file, ufId, searchResults }
const vmUfId = ref(null)       // 当前弹窗对应的 uploadFiles 条目 id
const vmFile = ref(null)
const vmMode = ref('version')  // 'version' | 'new'
const vmComment = ref('')
const vmSelectedEntry = ref(null)
const vmSearchResults = ref([])
const vmKeyword = ref('')

const notifications = ref([])
const showNotifyPanel = ref(false)
const unreadNotifyCount = ref(0)

const uploadCompletedCount = computed(() => uploadFiles.value.filter(f => f.status === 'success').length)
/** 未排进版本确认队列的待上传文件（需用户点「开始上传」） */
const uploadPendingNotQueuedCount = computed(() => {
  const queued = new Set((vmQueue.value || []).map(q => q.ufId))
  return uploadFiles.value.filter(f => f.status === 'pending' && !queued.has(f.id)).length
})

// ---- computed ----

/** 左侧选中部门后的「部门文件库」页；顶部搜索框有内容时让位给 LibraryPage 做全局搜索 */
const showDepartmentFilesPanel = computed(
  () =>
    tab.value === 'lib' &&
    activeDeptId.value != null &&
    !currentLib.value &&
    !String(searchKeyword.value || '').trim()
)

const filteredNewLibUsers = computed(() => {
  const kw = newLibMemberKeyword.value?.trim().toLowerCase()
  if (!kw) return newLibUsers.value
  return newLibUsers.value.filter(u =>
    (u.username || '').toLowerCase().includes(kw) || (u.email || '').toLowerCase().includes(kw)
  )
})

const filteredEditLibUsers = computed(() => {
  const kw = editLibMemberKeyword.value?.trim().toLowerCase()
  if (!kw) return editLibUsers.value
  return editLibUsers.value.filter(u =>
    (u.username || '').toLowerCase().includes(kw) || (u.email || '').toLowerCase().includes(kw)
  )
})

const filteredUserList = computed(() => {
  let list = userList.value
  const kw = sysSearchKeyword.value?.trim().toLowerCase()
  if (kw) list = list.filter(u => (u.username || '').toLowerCase().includes(kw) || (u.email || '').toLowerCase().includes(kw))
  if (userFilterStatus.value === 'active') list = list.filter(u => u.is_active)
  if (userFilterStatus.value === 'inactive') list = list.filter(u => !u.is_active)
  if (userFilterRole.value === 'admin') list = list.filter(u => u.is_superuser)
  if (userFilterRole.value === 'user') list = list.filter(u => !u.is_superuser)
  return list
})

function _flattenDepts(nodes, level = 0) {
  const out = []
  if (!nodes) return out
  for (const n of nodes) {
    out.push({ id: n.id, name: n.name, level })
    if (n.children?.length) out.push(..._flattenDepts(n.children, level + 1))
  }
  return out
}

const deptOptionsForUser = computed(() => _flattenDepts(deptTreeForTable.value))

/** 新建文件库：访问权限下拉选项（随是否选择部门切换） */
function _newLibModeRows(isDept) {
  if (!isDept) {
    return [
      { value: 'self', label: '仅自己' },
      { value: 'self_plus', label: '仅自己 + 指定成员' },
      { value: 'members_only', label: '仅指定成员' },
      { value: 'public', label: '公开（所有用户）' },
    ]
  }
  return [
    { value: 'dept', label: '所属部门' },
    { value: 'dept_plus', label: '所属部门 + 指定成员' },
  ]
}

const newLibDeptOptions = computed(() => {
  const opts = [{ value: null, label: '无（个人库）' }]
  for (const opt of deptOptionsForUser.value || []) {
    opts.push({ value: opt.id, label: '\u3000'.repeat(opt.level) + opt.name })
  }
  return opts
})

const newLibModeOptions = computed(() => _newLibModeRows(!!newLibDepartmentId.value))

const selectedNewLibDeptLabel = computed(() => {
  const id = newLibDepartmentId.value
  const hit = newLibDeptOptions.value.find(
    o =>
      (o.value == null && (id == null || id === '')) ||
      (o.value != null && Number(o.value) === Number(id)),
  )
  return hit?.label ?? '无（个人库）'
})

const selectedNewLibModeLabel = computed(() => {
  const rows = newLibModeOptions.value
  const hit = rows.find(r => r.value === newLibMode.value)
  return hit?.label ?? '请选择'
})

const sortedLibraries = computed(() => {
  const list = libraries.value || []
  if (!list.length) return list
  const arr = [...list]
  if (fileSortOrder.value === 'name') arr.sort((a, b) => (a.name || '').localeCompare(b.name || ''))
  else if (fileSortOrder.value === 'size') arr.sort((a, b) => (b.member_count || 0) - (a.member_count || 0))
  else if (fileSortOrder.value === 'created') arr.sort((a, b) => (a.id || 0) - (b.id || 0))
  return arr
})

/** 移动资料库弹窗：当前选中目标的展示文案（配合自定义下拉） */
const selectedMoveTargetLabel = computed(() => {
  const key = moveTargetKey.value
  const list = moveTargets.value || []
  const t = list.find(x => (x.parent_id == null ? key === 'root' : String(x.parent_id) === key))
  const lab = t?.label != null ? String(t.label).trim() : ''
  return lab || '请选择目标位置'
})

const sortedFiles = computed(() => _sortFileList(files.value || []))
const sortedSearchResults = computed(() => _sortFileList(searchResults.value || []))
const normalizedSearchKeyword = computed(() => String(searchKeyword.value || '').trim().toLowerCase())

function _includesKeyword(value, kw) {
  if (!kw) return true
  return String(value || '').toLowerCase().includes(kw)
}

const filteredMySharesList = computed(() => {
  const kw = normalizedSearchKeyword.value
  const list = mySharesList.value || []
  if (!kw) return list
  return list.filter(row =>
    _includesKeyword(row?.name, kw) ||
    _includesKeyword(row?.share_scope, kw) ||
    _includesKeyword(row?.description, kw) ||
    _includesKeyword(row?.department_name, kw)
  )
})

const filteredReceivedSharesList = computed(() => {
  const kw = normalizedSearchKeyword.value
  const list = receivedSharesList.value || []
  if (!kw) return list
  return list.filter(row =>
    _includesKeyword(row?.name, kw) ||
    _includesKeyword(row?.owner_username, kw) ||
    _includesKeyword(row?.share_scope, kw) ||
    _includesKeyword(row?.description, kw) ||
    _includesKeyword(row?.department_name, kw)
  )
})

const filteredTrashItems = computed(() => {
  const kw = normalizedSearchKeyword.value
  const list = trashItems.value || []
  if (!kw) return list
  return list.filter(item =>
    _includesKeyword(item?.name, kw) ||
    _includesKeyword(item?.library_name, kw) ||
    _includesKeyword(item?.path, kw) ||
    _includesKeyword(item?.type, kw) ||
    _includesKeyword(item?.username, kw)
  )
})

const filteredDeptTrashList = computed(() => {
  const kw = normalizedSearchKeyword.value
  const list = deptTrashList.value || []
  if (!kw) return list
  return list.filter(item =>
    _includesKeyword(item?.name, kw) ||
    _includesKeyword(item?.library_name, kw) ||
    _includesKeyword(item?.path, kw) ||
    _includesKeyword(item?.type, kw) ||
    _includesKeyword(item?.username, kw)
  )
})

const breadcrumbSegments = computed(() => {
  const p = (pathPrefix.value || '').replace(/\/$/, '')
  if (!p) return [{ label: '全部文件' }]
  const parts = p.split('/').filter(Boolean)
  return parts.map((name, i) => {
    const path = parts.slice(0, i + 1).join('/') + '/'
    const isLast = i === parts.length - 1
    return { label: name, path: isLast ? undefined : path }
  })
})

function _sortFileList(list) {
  if (!list?.length) return list
  const arr = [...list]
  if (fileSortOrder.value === 'name') {
    arr.sort((a, b) => {
      if (a.is_dir && !b.is_dir) return -1
      if (!a.is_dir && b.is_dir) return 1
      return (a.path || '').toLowerCase().localeCompare((b.path || '').toLowerCase())
    })
  } else if (fileSortOrder.value === 'size') {
    arr.sort((a, b) => {
      if (a.is_dir && !b.is_dir) return -1
      if (!a.is_dir && b.is_dir) return 1
      return (b.size || 0) - (a.size || 0)
    })
  } else if (fileSortOrder.value === 'created') {
    arr.sort((a, b) => new Date(a.updated_at || 0) - new Date(b.updated_at || 0))
  } else {
    arr.sort((a, b) => new Date(b.updated_at || 0) - new Date(a.updated_at || 0))
  }
  return arr
}

async function onSidebarNav(tabName) {
  tab.value = tabName
  if (tabName === 'lib') {
    clearDeptView()
    currentLib.value = null
    pathPrefix.value = ''
    clearSearch()
    err.value = ''
    await loadLibraries()
  }
  if (tabName === 'shared') { sharedSubTab.value = 'mine'; err.value = ''; loadMyShares() }
  if (tabName === 'trash') {
    trashMode.value = 'personal'
    err.value = ''
    if (me.value?.is_department_leader) {
      await loadDeptTrash()
    }
    loadTrash()
  }
}

function onSharedTab(subtab) {
  sharedSubTab.value = subtab
  if (subtab === 'mine') loadMyShares()
  else if (subtab === 'tome') loadReceivedShares()
}

// ---- 工具函数 ----

function logout() { api.logout() }
function goAdmin() { router.push('/admin') }
function goAccount() { router.push('/account') }
function goDeptManage() {
  router.push({ path: '/admin', query: { tab: 'departments' } })
}
function formatDate(s) {
  if (!s) return '-'
  try {
    let raw = String(s)
    // 后端历史数据可能是 “YYYY-MM-DD HH:MM:SS” 或不带时区的 ISO，按 UTC 处理
    if (!raw.endsWith('Z') && !raw.includes('+')) {
      raw = raw.replace(' ', 'T') + 'Z'
    }
    const d = new Date(raw)
    if (Number.isNaN(d.getTime())) return String(s)
    return d.toLocaleString('zh-CN', {
      timeZone: 'Asia/Shanghai',
      hour12: false,
    })
  } catch {
    return String(s)
  }
}
function formatSize(bytes) {
  if (bytes == null) return '-'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}
function showSuccess(msg) {
  successMessage.value = msg; errorMessage.value = ''; err.value = ''
  setTimeout(() => { successMessage.value = '' }, 3000)
}
function showError(msg) {
  errorMessage.value = msg
  setTimeout(() => { errorMessage.value = '' }, 4000)
}

async function restorePreviewReturnContext() {
  const q = route.query || {}
  if (q.return_to !== 'lib' || q.return_lib_id == null) return

  const libId = Number(q.return_lib_id)
  if (!Number.isFinite(libId) || libId <= 0) return

  const deptIdRaw = q.return_dept_id
  const deptId = deptIdRaw != null ? Number(deptIdRaw) : null
  if (Number.isFinite(deptId) && deptId > 0) {
    activeDeptId.value = deptId
    await loadDeptFiles(deptId)
  } else {
    clearDeptView()
  }

  let lib = libraries.value.find(l => l.id === libId)
  if (!lib) {
    try {
      lib = await api.getLibrary(libId)
    } catch {
      return
    }
  }
  if (!lib) return

  tab.value = 'lib'
  currentLib.value = lib
  pathPrefix.value = typeof q.return_path === 'string' ? q.return_path : ''
  filesOffset.value = 0
  searchResults.value = []
  rootSearchLibraries.value = []
  rootSearchFiles.value = []
  searchApplied.value = false
  await loadFiles()
  // 一次性上下文，用完即清理，避免刷新后重复执行
  router.replace({ path: '/', query: {} })
}

// ---- 生命周期 ----

onMounted(async () => {
  // 并行拉取用户信息、库列表、部门树，减少首屏总等待（原先串行会叠加延迟）
  await Promise.all([
    api.getMe().then((m) => { me.value = m }),
    loadLibraries(),
    loadDepartments(),
  ])
  await restorePreviewReturnContext()
  // 通知不阻塞首屏；失败时静默忽略
  loadNotifications(true).catch(() => {})
})

onUnmounted(() => {
  if (searchDebounceTimer) {
    clearTimeout(searchDebounceTimer)
    searchDebounceTimer = null
  }
})

async function loadLibraries() {
  const seq = ++librariesLoadSeq
  try {
    const pageSize = librariesLimit.value
    let off = librariesOffset.value
    let arr = []
    for (;;) {
      const list = await api.listLibraries({
        limit: pageSize + 1,
        offset: off,
        include_department: false,
      })
      if (seq !== librariesLoadSeq) return
      arr = Array.isArray(list) ? list : []
      if (arr.length > 0 || off <= 0) break
      off = Math.max(0, off - pageSize)
    }
    if (seq !== librariesLoadSeq) return
    librariesOffset.value = off
    librariesHasMore.value = arr.length > pageSize
    libraries.value = arr.slice(0, pageSize)
  } catch (e) {
    if (seq !== librariesLoadSeq) return
    err.value = e.message || '加载文件库失败'
    libraries.value = []
    librariesHasMore.value = false
  }
}

async function refreshLibrariesKeepPage() {
  await loadLibraries()
}

watch(subTab, val => { if (val === 'departments') loadDepartments() })
watch(searchKeyword, () => {
  if (tab.value !== 'lib') return
  if (searchDebounceTimer) {
    clearTimeout(searchDebounceTimer)
    searchDebounceTimer = null
  }
  const kw = searchKeyword.value?.trim()
  if (!kw) {
    clearSearch()
    return
  }
  searchDebounceTimer = setTimeout(() => {
    doSearch()
  }, 300)
})
watch([currentLib, pathPrefix], () => {
  if (currentLib.value) loadFiles()
  searchResults.value = []
  rootSearchLibraries.value = []
  rootSearchFiles.value = []
  searchApplied.value = false
})
watch(showNewDropdown, open => {
  if (!open) return
  const onDocClick = () => { showNewDropdown.value = false; document.removeEventListener('click', onDocClick) }
  setTimeout(() => document.addEventListener('click', onDocClick), 0)
})
watch(moveTargetPickerOpen, open => {
  if (!open) return
  const onDocClick = () => {
    moveTargetPickerOpen.value = false
    document.removeEventListener('click', onDocClick)
  }
  setTimeout(() => document.addEventListener('click', onDocClick), 0)
})
watch(newLibDeptPickerOpen, open => {
  if (!open) return
  const onDocClick = () => {
    newLibDeptPickerOpen.value = false
    document.removeEventListener('click', onDocClick)
  }
  setTimeout(() => document.addEventListener('click', onDocClick), 0)
})
watch(newLibModePickerOpen, open => {
  if (!open) return
  const onDocClick = () => {
    newLibModePickerOpen.value = false
    document.removeEventListener('click', onDocClick)
  }
  setTimeout(() => document.addEventListener('click', onDocClick), 0)
})
watch(openActionMenuId, id => {
  if (!id) return
  const onDocClick = () => { openActionMenuId.value = null; document.removeEventListener('click', onDocClick) }
  setTimeout(() => document.addEventListener('click', onDocClick), 0)
})
watch(newLibDepartmentId, val => {
  if (val) { if (!['dept', 'dept_plus'].includes(newLibMode.value)) newLibMode.value = 'dept' }
  else { if (!['self', 'self_plus', 'members_only', 'public'].includes(newLibMode.value)) newLibMode.value = 'self' }
})
watch(currentLib, lib => {
  if (!lib) libChildrenLibraries.value = []
})
watch(pathPrefix, async p => {
  if (currentLib.value?.id && p === '') await loadChildLibrariesForCurrent()
})

// ---- 搜索 ----

function clearSearch() {
  searchResults.value = []
  rootSearchLibraries.value = []
  rootSearchFiles.value = []
  searchKeyword.value = ''
  searchApplied.value = false
}

function onTopbarClearLib() {
  currentLib.value = null
  pathPrefix.value = ''
  if (activeDeptId.value != null) {
    clearSearch()
  }
}

async function doSearch() {
  if (!currentLib.value || !searchKeyword.value?.trim()) {
    if (!searchKeyword.value?.trim()) {
      clearSearch()
      return
    }
  }

  const kw = searchKeyword.value.trim()
  if (currentLib.value) {
    try {
      searchResults.value = await api.searchFiles(currentLib.value.id, kw)
      rootSearchLibraries.value = []
      rootSearchFiles.value = []
      searchApplied.value = true
    }
    catch (e) {
      err.value = e.message
      searchResults.value = []
      rootSearchLibraries.value = []
      rootSearchFiles.value = []
      searchApplied.value = true
    }
    return
  }

  try {
    const inDeptView = activeDeptId.value != null
    const [libs, files] = await Promise.all([
      searchLibrariesGlobal(kw, { includeDepartment: inDeptView, departmentId: activeDeptId.value }),
      api.searchFilesGlobal(kw, null, { includeDepartment: inDeptView }),
    ])
    rootSearchLibraries.value = libs
    rootSearchFiles.value = files || []
    searchResults.value = []
    searchApplied.value = true
  } catch (e) {
    err.value = e.message
    rootSearchLibraries.value = []
    rootSearchFiles.value = []
    searchResults.value = []
    searchApplied.value = true
  }
}

function doSearchNow() {
  if (searchDebounceTimer) {
    clearTimeout(searchDebounceTimer)
    searchDebounceTimer = null
  }
  doSearch()
}

async function searchLibrariesGlobal(keyword, options = {}) {
  const includeDepartment = options?.includeDepartment === true
  const departmentId = Number(options?.departmentId)
  const limit = 200
  let offset = 0
  const all = []
  // 逐页拉取可访问库，避免仅搜索当前分页数据
  while (offset <= 2000) {
    let rows = []
    if (Number.isFinite(departmentId) && departmentId > 0) {
      rows = await api.listDepartmentLibraries(departmentId, {
        limit,
        offset,
        roots_only: false,
      })
    } else {
      rows = await api.listLibraries({
        limit,
        offset,
        include_department: includeDepartment,
        roots_only: false,
      })
    }
    const list = rows || []
    all.push(...list)
    if (list.length < limit) break
    offset += limit
  }
  const kw = String(keyword || '').trim().toLowerCase()
  if (!kw) return []
  return all.filter(lib =>
    (lib?.name || '').toLowerCase().includes(kw) ||
    (lib?.description || '').toLowerCase().includes(kw)
  )
}

async function openGlobalSearchFileResult(file) {
  if (!file?.library_id) return
  let lib = (libraries.value || []).find(l => Number(l.id) === Number(file.library_id))
  if (!lib) {
    lib = await api.getLibrary(file.library_id)
  }
  currentLib.value = lib
  const fullPath = String(file.path || '')
  const idx = fullPath.lastIndexOf('/')
  pathPrefix.value = idx >= 0 ? fullPath.slice(0, idx + 1) : ''
  filesOffset.value = 0
  searchResults.value = []
  rootSearchLibraries.value = []
  rootSearchFiles.value = []
  searchApplied.value = false
  await loadFiles()
}

async function openGlobalSearchFilePreview(file) {
  if (!file || file.is_dir) return
  await openPreview(file)
}
function goToPath(path) {
  const dir = path.endsWith('/') ? path.slice(0, -1) : path
  const i = dir.lastIndexOf('/')
  pathPrefix.value = i >= 0 ? dir.slice(0, i + 1) : ''
  filesOffset.value = 0
  searchResults.value = []
  searchKeyword.value = ''
  searchApplied.value = false
}

// ---- 文件操作 ----

async function loadFiles() {
  if (!currentLib.value) return
  filesLoading.value = true
  try {
    const pageSize = filesLimit.value
    let off = filesOffset.value
    let arr = []
    for (;;) {
      const list = await api.listFiles(
        currentLib.value.id,
        pathPrefix.value,
        true,
        { limit: pageSize + 1, offset: off }
      )
      arr = Array.isArray(list) ? list : []
      if (arr.length > 0 || off <= 0) break
      off = Math.max(0, off - pageSize)
    }
    filesOffset.value = off
    filesHasMore.value = arr.length > pageSize
    files.value = arr.slice(0, pageSize)
  }
  catch (e) { err.value = e.message }
  finally { filesLoading.value = false }
}
async function loadChildLibrariesForCurrent() {
  if (!currentLib.value?.id) {
    libChildrenLibraries.value = []
    return
  }
  try {
    const rows = await api.listLibraryChildren(currentLib.value.id)
    libChildrenLibraries.value = Array.isArray(rows) ? rows : []
  } catch {
    libChildrenLibraries.value = []
  }
}

async function selectLib(lib) {
  if (!lib?.id) return
  pathPrefix.value = ''
  filesOffset.value = 0
  err.value = ''
  try {
    currentLib.value = await api.getLibrary(lib.id)
  } catch (e) {
    err.value = e?.message || ''
    currentLib.value = lib
  }
  await loadChildLibrariesForCurrent()
  loadFiles()
}
function goUp() {
  const p = pathPrefix.value.replace(/\/$/, '')
  const i = p.lastIndexOf('/')
  pathPrefix.value = i >= 0 ? p.slice(0, i) : ''
  filesOffset.value = 0
}
function enterDir(entry) {
  if (!entry?.is_dir) return
  pathPrefix.value = entry.path + '/'
  filesOffset.value = 0
  searchResults.value = []
  searchKeyword.value = ''
  searchApplied.value = false
}
function toggleActionMenu(id) { openActionMenuId.value = openActionMenuId.value === id ? null : id }
function closeActionMenu() { openActionMenuId.value = null }

function goPrevLibrariesPage() {
  if (librariesOffset.value <= 0) return
  librariesOffset.value = Math.max(0, librariesOffset.value - librariesLimit.value)
  loadLibraries()
}

function goNextLibrariesPage() {
  if (!librariesHasMore.value) return
  librariesOffset.value = librariesOffset.value + librariesLimit.value
  loadLibraries()
}

function goPrevFilesPage() {
  if (filesOffset.value <= 0) return
  filesOffset.value = Math.max(0, filesOffset.value - filesLimit.value)
  loadFiles()
}

function goNextFilesPage() {
  if (!filesHasMore.value) return
  filesOffset.value = filesOffset.value + filesLimit.value
  loadFiles()
}

async function delFile(f) {
  if (!confirm('确定删除到回收站？')) return
  err.value = ''
  try { await api.deleteFile(f.id); loadFiles(); showSuccess('删除成功') }
  catch (e) { err.value = e.message }
}
async function download(entryId, versionNo = null) {
  err.value = ''
  try {
    await api.downloadFile(entryId, versionNo)
    showSuccess('下载已开始')
  } catch (e) {
    const m = e?.message || '下载失败'
    err.value = m
    showError(m)
  }
}
async function openVersions(f) {
  versionEntryId.value = f.id
  versionEntryName.value = f.path || f.name || ''
  versionEntryFilename.value = (versionEntryName.value || '').split('/').pop()
  versions.value = await api.listVersions(f.id)
  showVersions.value = true
}
function canDeleteVersion() {
  return Array.isArray(versions.value) && versions.value.length > 1
}
async function deleteVersionRecord(v) {
  if (!versionEntryId.value || !v) return
  if (!canDeleteVersion()) {
    err.value = '至少保留一个版本，无法删除'
    return
  }
  if (!confirm(`确定删除版本 v${v.version_no} 吗？`)) return
  err.value = ''
  try {
    await api.deleteVersion(versionEntryId.value, v.version_no)
    versions.value = await api.listVersions(versionEntryId.value)
    showSuccess(`版本 v${v.version_no} 已删除`)
  } catch (e) {
    err.value = e.message || '删除版本失败'
  }
}
function onFileClick(file) { if (file.is_dir) return; openPreview(file) }

const IMG_EXT = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.bmp']
const TEXT_EXT = ['.txt', '.md', '.json', '.xml', '.html', '.htm', '.css', '.js', '.yaml', '.yml']
function previewTypeOf(path) {
  const ext = '.' + (path || '').split('.').pop().toLowerCase()
  if (IMG_EXT.includes(ext)) return 'image'
  if (ext === '.pdf') return 'pdf'
  if (TEXT_EXT.includes(ext)) return 'text'
  return ''
}
async function openPreview(f) {
  err.value = ''
  if (!previewTypeOf(f.path)) { err.value = '该文件类型暂不支持预览'; return }
  try {
    // 受控预览：站内预览页通过鉴权接口获取“渲染产物”，不直接打开原文件直链
    const q = {
      entry_id: String(f.id),
      return_to: 'lib',
    }
    if (currentLib.value?.id != null) q.return_lib_id = String(currentLib.value.id)
    if (pathPrefix.value) q.return_path = pathPrefix.value
    if (activeDeptId.value != null) q.return_dept_id = String(activeDeptId.value)
    router.push({ path: '/preview', query: q })
  } catch (e) { err.value = e.message || '预览失败' }
}
function closePreview() { previewUrl.value = ''; showPreview.value = false; previewText.value = ''; previewErr.value = '' }

async function previewVersion(v) {
  if (!versionEntryId.value) return
  // 版本之间扩展名一致，直接按当前文件路径判断是否支持预览
  if (!previewTypeOf(versionEntryName.value)) {
    err.value = '该文件类型暂不支持预览'
    return
  }
  try {
    // 受控预览：带版本号跳转
    const q = {
      entry_id: String(versionEntryId.value),
      version_no: String(v.version_no),
      return_to: 'lib',
    }
    if (currentLib.value?.id != null) q.return_lib_id = String(currentLib.value.id)
    if (pathPrefix.value) q.return_path = pathPrefix.value
    if (activeDeptId.value != null) q.return_dept_id = String(activeDeptId.value)
    router.push({ path: '/preview', query: q })
  } catch (e) {
    err.value = e.message || '预览失败'
  }
}

function openRename(f) { renameEntry.value = f; renameNewPath.value = f.path; showRename.value = true; err.value = '' }
function closeRename() { showRename.value = false; renameEntry.value = null; renameNewPath.value = ''; err.value = '' }
async function doRename() {
  if (!renameEntry.value) return
  const newPath = renameNewPath.value?.trim()
  if (!newPath) { err.value = '请输入新路径'; return }
  err.value = ''
  try {
    await api.renameFile(renameEntry.value.id, newPath)
    loadFiles(); if (searchResults.value.length) doSearch(); closeRename(); showSuccess('重命名成功')
  } catch (e) { err.value = e.message }
}

function onFileSelect() { uploadErr.value = '' }

function openUploadModal() {
  showUpload.value = true
  uploadErr.value = ''
  uploadFiles.value = []
  uploadDropzoneActive.value = false
  uploadStep.value = 'list'
  vmQueue.value = []
  vmFile.value = null
  vmUfId.value = null
  vmMode.value = 'version'
  vmComment.value = ''
  vmSelectedEntry.value = null
  vmSearchResults.value = []
  vmKeyword.value = ''
}

function resetUploadModal() {
  showUpload.value = false
  uploadFiles.value = []
  uploadDropzoneActive.value = false
  uploadStep.value = 'list'
  vmQueue.value = []
  vmFile.value = null
  vmUfId.value = null
  vmMode.value = 'version'
  vmComment.value = ''
  vmSelectedEntry.value = null
  vmSearchResults.value = []
  vmKeyword.value = ''
}
/** 撤销本会话中已成功写入服务端的上传（新文件整文件进回收站；已有文件则删除刚上传的最新版本） */
async function rollbackUploadSessionEntry(entryId) {
  if (entryId == null) return
  try {
    const vers = await api.listVersions(entryId)
    if (!vers?.length) return
    if (vers.length === 1) {
      await api.deleteFile(entryId)
    } else {
      const maxNo = Math.max(...vers.map(v => v.version_no))
      await api.deleteVersion(entryId, maxNo)
    }
  } catch {
    // 忽略：例如已手动删除或网络失败
  }
}
async function rollbackSuccessfulUploadsFromList(filesList) {
  const items = filesList.filter(f => f.status === 'success' && f.entryId != null)
  for (const f of items) {
    await rollbackUploadSessionEntry(f.entryId)
  }
}
async function abandonUploadModal() {
  const snapshot = uploadFiles.value.slice()
  await rollbackSuccessfulUploadsFromList(snapshot)
  resetUploadModal()
  await loadFiles()
}
function startPendingDirectUploads() {
  const queued = new Set((vmQueue.value || []).map(q => q.ufId))
  uploadFiles.value
    .filter(f => f.status === 'pending' && !queued.has(f.id))
    .forEach(f => { startUploadOne(f.id) })
}
function vmExtractKeyword(filename) {
  if (!filename || typeof filename !== 'string') return ''
  // 第一步：去扩展名
  let name = filename.replace(/\.[^.]+$/, '').trim()
  const original = name

  // 第二步：去末尾括号数字（中英文括号，括号前可能有空格，支持多重）
  name = name.replace(/\s*[（(]\d+[)）]/g, '').trim()

  // 第三步：去13/14位时间戳（微信/系统保存格式）
  name = name.replace(/[_\- ]?\d{13,14}$/, '').trim()

  // 第四步：去日期相关后缀（循环去除）
  let prevName = ''
  while (prevName !== name) {
    prevName = name
    name = name.replace(/[_\- ]?\d{6}$/, '').trim()
    name = name.replace(/[_\- ]?\d{4}[-]\d{2}[-]\d{2}$/, '').trim()
    name = name.replace(/[_\- ]?\d{8}$/, '').trim()
    name = name.replace(/[_\- ]?\d{6}$/, '').trim()
  }

  // 第五步：去版本号
  name = name.replace(/[_\- ]?[vV]\d+(\.\d+)?$/, '').trim()
  name = name.replace(/[_\- ]?[rR][eE][vV]\d+$/, '').trim()
  name = name.replace(/[vV]\d+(\.\d+)?$/, '').trim()

  // 第六步：去版本标记文字
  const versionTokens = [
    '终稿','定版','最终版','修改版','修改稿','送审版','报批版','报审版',
    '讨论稿','征求意见稿','初稿','第一稿','第二稿','第三稿','第四稿',
    '评审稿','审查稿','完善版','更新版','final','FINAL',
  ]
  versionTokens.forEach(t => {
    name = name.replace(new RegExp(`[_\\-]?${t}$`, 'i'), '').trim()
  })

  // 第七步：去人名后缀
  name = name.replace(/[_\- ]?[\u4e00-\u9fa5]{1,2}工[\u4e00-\u9fa5]{0,2}$/, '').trim()
  name = name.replace(/\s*[（(][\u4e00-\u9fa5]{1,3}[)）]$/, '').trim()

  // 第八步：去末尾多余的分隔符
  name = name.replace(/[_\- ]+$/, '').trim()

  if (!name) return original

  // 第九步：长前缀工程命名处理
  const parts = name.split('_').map(p => p.trim()).filter(p => p.length > 0)
  if (parts.length >= 3) return parts.slice(1).join(' ')
  if (parts.length === 2) return parts[1]

  return name
}

function vmBuildCandidateKeywords(filename) {
  if (!filename || typeof filename !== 'string') return []
  const stem = filename.replace(/\.[^.]+$/, '').trim()
  const out = []
  const seen = new Set()
  const pushKw = (kw) => {
    const s = String(kw || '').trim()
    if (!s || s.length < 2 || seen.has(s)) return
    seen.add(s)
    out.push(s)
  }

  // 1) 主关键词：沿用既有规则（日期/版本号/终稿等）
  const primary = vmExtractKeyword(filename)
  pushKw(primary)

  // 2) 兼容“文件名后缀加数字/字母”的常见版本命名
  let relaxed = stem
  // 例如：报告(1)、报告（A1）
  relaxed = relaxed.replace(/\s*[（(][A-Za-z0-9一二三四五六七八九十]{1,4}[)）]\s*$/, '').trim()
  // 例如：报告_1、报告-A、报告 A1
  relaxed = relaxed.replace(/[_\- ]+[A-Za-z]?\d{1,4}$/, '').trim()
  relaxed = relaxed.replace(/[_\- ]+[A-Za-z]{1,3}$/, '').trim()
  // 例如：报告1、报告A（仅去掉很短的结尾，避免过度截断）
  relaxed = relaxed.replace(/([\u4e00-\u9fa5A-Za-z]{2,})[A-Za-z]?\d{1,2}$/, '$1').trim()
  relaxed = relaxed.replace(/([\u4e00-\u9fa5]{2,})[A-Za-z]{1,2}$/, '$1').trim()

  pushKw(relaxed)
  pushKw(vmExtractKeyword(relaxed))
  return out
}

const UPLOAD_BLOCKED_EXT = new Set([
  'exe', 'bat', 'cmd', 'com', 'msi', 'dll', 'scr',
  'ps1', 'vbs', 'js', 'jar', 'sh',
])
function isBlockedUploadFileName(name) {
  const n = String(name || '')
  const ext = n.includes('.') ? n.split('.').pop().toLowerCase() : ''
  return UPLOAD_BLOCKED_EXT.has(ext)
}
function blockedUploadMessage(name) {
  const n = String(name || '')
  const ext = n.includes('.') ? '.' + n.split('.').pop().toLowerCase() : ''
  return `不支持上传此文件类型：${ext || '未知'}`
}
// 测试用例：
// vmExtractKeyword('XXXX（1）.pdf')           → 'XXXX'
// vmExtractKeyword('XXXX(1).pdf')             → 'XXXX'
// vmExtractKeyword('XXXX （1）（2）.pdf')     → 'XXXX'
// vmExtractKeyword('环评报告_20260101.pdf')   → '环评报告'
// vmExtractKeyword('环评报告_20260101_v2.pdf')→ '环评报告'
// vmExtractKeyword('环评报告_v2.pdf')         → '环评报告'
// vmExtractKeyword('环评报告_终稿.pdf')       → '环评报告'
// vmExtractKeyword('报告_王工.pdf')           → '报告'
// vmExtractKeyword('报告_王工审查.pdf')       → '报告'
// vmExtractKeyword('报告_1709123456789.pdf')  → '报告'
// vmExtractKeyword('报告_20260101_143022.pdf')→ '报告'
// vmExtractKeyword('报告_终稿_20260101_v2（1）.pdf') → '报告'
// vmExtractKeyword('乌兰察布市_可行性研究报告_专家评审意见_终稿.docx') → '可行性研究报告 专家评审意见'
// vmExtractKeyword('新的.pdf')                → '新的'
// vmExtractKeyword('修改后.pdf')              → '修改后'

async function addUploadFiles(files) {
  if (!files?.length || !currentLib.value?.id) return
  const all = Array.from(files)
  const blocked = all.filter(f => isBlockedUploadFileName(f?.name))
  if (blocked.length) {
    showError(blocked.length === 1 ? blockedUploadMessage(blocked[0].name) : `包含不支持上传的文件类型（如 .exe/.bat），已拦截 ${blocked.length} 个文件`)
  }
  const arr = all.filter(f => !isBlockedUploadFileName(f?.name))
  if (!arr.length) return

  const list = arr.map(file => ({
    id: `${file.name}-${Date.now()}-${Math.random()}`,
    file,
    progress: 0,
    status: 'pending',
    error: undefined,
  }))
  uploadFiles.value = uploadFiles.value.concat(list)
  showUpload.value = true

  const searchPromises = arr.map(async (file, i) => {
    const candidates = vmBuildCandidateKeywords(file.name)
    if (!candidates.length) return { file, ufId: list[i].id, results: [], matchedKeyword: '' }
    for (const kw of candidates) {
      try {
        const results = await api.searchFilesGlobal(kw, currentLib.value?.id ?? null)
        if (results?.length) {
          return { file, ufId: list[i].id, results, matchedKeyword: kw }
        }
      } catch {
        // ignore and try next candidate keyword
      }
    }
    return { file, ufId: list[i].id, results: [], matchedKeyword: candidates[0] || '' }
  })

  const searched = await Promise.all(searchPromises)
  const toQueue = searched.filter(s => s.results.length > 0)

  if (toQueue.length > 0) {
    vmQueue.value = toQueue.map(s => ({
      file: s.file,
      ufId: s.ufId,
      searchResults: s.results,
      matchedKeyword: s.matchedKeyword || '',
    }))
    vmOpenFromQueue()
  }
}

function vmOpenFromQueue() {
  if (!vmQueue.value.length) return
  const item = vmQueue.value[0]
  vmFile.value = item.file
  vmUfId.value = item.ufId
  vmMode.value = 'version'
  vmComment.value = ''
  vmSelectedEntry.value = null
  vmSearchResults.value = item.searchResults
  vmKeyword.value = item.matchedKeyword || vmExtractKeyword(item.file.name)
  uploadStep.value = 'confirm'
}

async function vmDoSearch() {
  if (!vmKeyword.value?.trim() || !currentLib.value?.id) return
  try {
    vmSearchResults.value = await api.searchFiles(currentLib.value.id, vmKeyword.value.trim())
  } catch {
    vmSearchResults.value = []
  }
}

let vmSearchDebounceTimer = null
function vmOnSearchInput() {
  vmSelectedEntry.value = null
  if (vmSearchDebounceTimer) clearTimeout(vmSearchDebounceTimer)
  vmSearchDebounceTimer = setTimeout(() => vmDoSearch(), 300)
}

async function vmDoUpload() {
  if (!vmFile.value) return
  const ufId = vmUfId.value

  vmQueue.value = vmQueue.value.slice(1)

  if (vmMode.value === 'new' || !vmSelectedEntry.value) {
    await startUploadOne(ufId)
  } else {
    uploadFiles.value = uploadFiles.value.map(f =>
      f.id === ufId ? { ...f, status: 'uploading' } : f
    )
    try {
      await api.uploadVersionWithProgress(
        vmSelectedEntry.value,
        vmComment.value,
        vmFile.value,
        p => {
          uploadFiles.value = uploadFiles.value.map(f =>
            f.id === ufId ? { ...f, progress: p } : f
          )
        }
      )
      const vid = vmSelectedEntry.value?.id
      uploadFiles.value = uploadFiles.value.map(f =>
        f.id === ufId ? { ...f, progress: 100, status: 'success', entryId: vid } : f
      )
      loadFiles()
    } catch (e) {
      let errMsg = e.message
      if (e.message?.includes('SAME_AS_LATEST')) {
        errMsg = '文件内容与最新版本完全相同，无需重复上传'
      }
      uploadFiles.value = uploadFiles.value.map(f =>
        f.id === ufId ? { ...f, status: 'error', error: errMsg } : f
      )
    }
  }

  if (vmQueue.value.length > 0) {
    vmOpenFromQueue()
  } else {
    uploadStep.value = 'list'
  }
}

async function vmSkip() {
  const ufId = vmUfId.value
  vmQueue.value = vmQueue.value.slice(1)
  await startUploadOne(ufId)
  if (vmQueue.value.length > 0) {
    vmOpenFromQueue()
  } else {
    uploadStep.value = 'list'
  }
}
function onUploadDrop(e) {
  uploadDropzoneActive.value = false
  const files = e.dataTransfer?.files
  if (files?.length) addUploadFiles(Array.from(files))
}
function triggerUploadInput() {
  uploadModalInputRef.value?.click()
}
function onUploadFileSelect(e) {
  const files = e.target?.files
  if (files?.length) addUploadFiles(Array.from(files))
  e.target.value = ''
}
async function removeUploadFile(id) {
  const uf = uploadFiles.value.find(f => f.id === id)
  if (uf?.status === 'success' && uf.entryId != null) {
    await rollbackUploadSessionEntry(uf.entryId)
    await loadFiles()
  }
  uploadFiles.value = uploadFiles.value.filter(f => f.id !== id)
}
function formatUploadSize(bytes) {
  if (bytes == null || bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return (bytes / Math.pow(k, i)).toFixed(1).replace(/\.0$/, '') + ' ' + sizes[i]
}
function getUploadFileIcon(fileName) {
  const ext = (fileName || '').split('.').pop()?.toLowerCase()
  if (['jpg', 'jpeg', 'png', 'gif', 'webp', 'svg'].includes(ext || '')) return 'image'
  if (['js', 'jsx', 'ts', 'tsx', 'css', 'html', 'json'].includes(ext || '')) return 'code'
  return 'file'
}
async function startUploadOne(id) {
  const uf = uploadFiles.value.find(f => f.id === id)
  if (!uf || uf.status !== 'pending') return
  const fullPath = pathPrefix.value ? pathPrefix.value + uf.file.name : uf.file.name
  uploadFiles.value = uploadFiles.value.map(f => f.id === id ? { ...f, status: 'uploading' } : f)
  try {
    const data = await api.uploadFileWithProgress(currentLib.value.id, fullPath, uf.file, (p) => {
      uploadFiles.value = uploadFiles.value.map(f => f.id === id ? { ...f, progress: p } : f)
    })
    const entryId = data?.id
    uploadFiles.value = uploadFiles.value.map(f => f.id === id ? { ...f, progress: 100, status: 'success', entryId } : f)
    if (currentLib.value?.id) {
      await loadFiles()
    }
  } catch (e) {
    uploadFiles.value = uploadFiles.value.map(f => f.id === id ? { ...f, status: 'error', error: e.message } : f)
  }
}
function finishUploadModal() {
  const n = uploadCompletedCount.value
  resetUploadModal()
  loadFiles()
  if (n > 0) showSuccess(n === 1 ? '上传成功' : `已上传 ${n} 个文件`)
}
async function onFileDrop(e) {
  isDragging.value = false
  if (!currentLib.value?.is_writeable) return
  const items = e.dataTransfer?.files
  if (!items?.length) return
  uploadErr.value = ''; let ok = 0; let fail = 0
  for (let i = 0; i < items.length; i++) {
    const file = items[i]
    if (file?.name) {
      try {
        const fullPath = pathPrefix.value ? pathPrefix.value + file.name : file.name
        await api.uploadFile(currentLib.value.id, fullPath, file); ok++
      } catch (e) { uploadErr.value = e.message; fail++ }
    }
  }
  if (ok) { loadFiles(); showSuccess(fail ? `已上传 ${ok} 个，失败 ${fail} 个` : `已上传 ${ok} 个文件`) }
}
function onDragOver() { isDragging.value = true }
function onDragLeave() { isDragging.value = false }
async function doMkdir() {
  const path = (pathPrefix.value ? pathPrefix.value + mkdirPath.value : mkdirPath.value).replace(/\/+/g, '/')
  err.value = ''
  try {
    await api.createDir(currentLib.value.id, path)
    showMkdir.value = false; mkdirPath.value = ''; loadFiles(); showSuccess('目录已创建')
  } catch (e) { err.value = e.message }
}

// ---- 分享 ----

function openShare(f) {
  if (f.is_dir) return
  shareFile.value = f; showShare.value = true; shareAddUserId.value = ''; sharePermission.value = 'read'; err.value = ''
  loadShareList(); loadShareAddableUsers()
}
function closeShare() { showShare.value = false; shareFile.value = null; shareList.value = []; shareAddableUsers.value = [] }
async function loadShareList() {
  if (!shareFile.value) return
  try { shareList.value = await api.listFileShares(shareFile.value.id) }
  catch (e) { err.value = e.message }
}
async function loadShareAddableUsers() {
  if (!shareFile.value) return
  try { shareAddableUsers.value = await api.listFileShareAddableUsers(shareFile.value.id) }
  catch { shareAddableUsers.value = [] }
}
async function doAddShare() {
  const uid = shareAddUserId.value
  if (!uid || !shareFile.value) return
  err.value = ''
  try {
    await api.addFileShare(shareFile.value.id, Number(uid), sharePermission.value)
    loadShareList(); loadShareAddableUsers(); shareAddUserId.value = ''; showSuccess('已添加分享')
  } catch (e) { err.value = e.message }
}
async function doRemoveShare(s) {
  if (!confirm('确定移除此分享？')) return
  if (!shareFile.value) return
  err.value = ''
  try { await api.removeFileShare(shareFile.value.id, s.user_id); loadShareList(); loadShareAddableUsers(); showSuccess('已移除分享') }
  catch (e) { err.value = e.message }
}
async function loadMyShares() {
  if (tab.value !== 'shared') return
  mySharesLoading.value = true
  try { mySharesList.value = await api.listMyShares() }
  catch (e) { err.value = e.message; mySharesList.value = [] }
  finally { mySharesLoading.value = false }
}
async function loadReceivedShares() {
  if (tab.value !== 'shared' || sharedSubTab.value !== 'tome') return
  receivedSharesLoading.value = true
  try { receivedSharesList.value = await api.listSharesToMe() }
  catch (e) { err.value = e.message; receivedSharesList.value = [] }
  finally { receivedSharesLoading.value = false }
}
async function openSharedLib(row) {
  let lib = libraries.value.find(l => l.id === row.id)
  if (!lib && row?.id != null) {
    try {
      lib = await api.getLibrary(row.id)
    } catch (e) {
      err.value = e?.message || '未找到该文件库，请刷新页面后重试'
      return
    }
  }
  if (lib) {
    tab.value = 'lib'
    selectLib(lib)
  } else {
    err.value = '未找到该文件库，请刷新页面后重试'
  }
}

// ---- 回收站 ----

// 单独的 loadLibraryTrash 已不再直接使用，统一由 loadTrash 聚合库+文件

async function loadTrash() {
  if (tab.value !== 'trash' || trashMode.value !== 'personal') return
  trashLoading.value = true
  err.value = ''
  try {
    // 统一改为后端聚合接口：我的回收站（库 + 文件）
    trashItems.value = await api.listMyTrash()
  } catch (e) {
    err.value = e.message
    trashItems.value = []
  } finally {
    trashLoading.value = false
  }
}

async function loadDeptTrash() {
  if (!me.value?.department_id) return
  deptTrashLoading.value = true
  err.value = ''
  try {
    deptTrashList.value = await api.listDeptTrash(me.value.department_id)
  } catch (e) {
    err.value = e?.message || '加载失败'
    deptTrashList.value = []
  } finally {
    deptTrashLoading.value = false
  }
}

async function restoreDeptFile(item) {
  err.value = ''
  try {
    if (item?.type === 'library') {
      await api.restoreLibrary(item.id)
      await refreshLibrariesKeepPage()
      showSuccess('资料库已恢复')
    } else if (item?.type === 'file_version') {
      await api.restoreVersionTrash(item.id)
      showSuccess('历史版本已恢复')
    } else {
      await api.restoreFile(item.id)
      showSuccess('文件已恢复')
    }
    await loadDeptTrash()
  } catch (e) {
    err.value = e?.message || '恢复失败'
  }
}

async function permDeleteDeptFile(item) {
  if (!confirm('确定从回收站彻底删除？此操作不可恢复。')) return
  err.value = ''
  try {
    if (item?.type === 'library') {
      await api.permanentDeleteLibrary(item.id)
      await refreshLibrariesKeepPage()
      showSuccess('资料库已彻底删除')
    } else if (item?.type === 'file_version') {
      await api.permanentDeleteVersionTrash(item.id)
      showSuccess('历史版本已彻底删除')
    } else {
      await api.permanentDelete(item.id)
      showSuccess('文件已彻底删除')
    }
    await loadDeptTrash()
  } catch (e) {
    err.value = e?.message || '删除失败'
  }
}

async function restoreTrashItem(item) {
  err.value = ''
  try {
    if (item.type === 'library') {
      await api.restoreLibrary(item.id)
      libraries.value = await api.listLibraries({ include_department: false })
      showSuccess('资料库已恢复')
    } else if (item.type === 'file_version') {
      await api.restoreVersionTrash(item.id)
      showSuccess('历史版本已恢复')
    } else {
      await api.restoreFile(item.id)
      showSuccess('文件已恢复')
    }
    await loadTrash()
  } catch (e) {
    err.value = e.message
  }
}

async function permDeleteTrashItem(item) {
  if (!confirm('确定从回收站彻底删除？此操作不可恢复。')) return
  err.value = ''
  try {
    if (item.type === 'library') {
      await api.permanentDeleteLibrary(item.id)
      libraries.value = await api.listLibraries({ include_department: false })
      if (currentLib.value?.id === item.id) currentLib.value = null
      showSuccess('资料库已彻底删除')
    } else if (item.type === 'file_version') {
      await api.permanentDeleteVersionTrash(item.id)
      showSuccess('历史版本已彻底删除')
    } else {
      await api.permanentDelete(item.id)
      showSuccess('文件已彻底删除')
    }
    await loadTrash()
  } catch (e) {
    err.value = e.message
  }
}

// ---- 通知 ----

async function loadNotifications(unreadOnly = false) {
  try {
    const list = await api.listNotifications(unreadOnly)
    notifications.value = Array.isArray(list) ? list : []
    // unreadOnly=true 时后端已过滤未读，直接用长度避免 is_read 类型差异造成误判
    if (unreadOnly) {
      unreadNotifyCount.value = notifications.value.length
      return
    }

    // 容错：兼容 is_read 可能为 0/1 或字符串等情况
    unreadNotifyCount.value = notifications.value.filter(n => {
      const v = n?.is_read ?? n?.isRead
      if (v === false || v === 0 || v === '0') return true
      if (v === true || v === 1 || v === '1') return false
      // 兜底：null/undefined 当已读处理；其他值按 JS 真值判断
      if (v === null || v === undefined) return false
      return !Boolean(v)
    }).length
  } catch (e) {
    // 通知失败不影响主流程，仅在控制台输出
    // eslint-disable-next-line no-console
    console.error('loadNotifications error', e)
  }
}

async function onNotificationClick(n) {
  if (!n?.id) return
  try {
    await api.markNotificationRead(n.id)
    await loadNotifications(false)
  } catch (e) {
    // eslint-disable-next-line no-console
    console.error('onNotificationClick error', e)
  }
}

function toggleNotifyPanel() {
  showNotifyPanel.value = !showNotifyPanel.value
  if (showNotifyPanel.value) loadNotifications(false)
}

async function markAllNotifications() {
  try {
    await api.markAllNotificationsRead()
    await loadNotifications(false)
  } catch (e) {
    err.value = e.message
  }
}

// ---- 资料库 ----

async function loadNewLibUsers() {
  if (newLibUsers.value.length || newLibMembersLoading.value) return
  newLibMembersLoading.value = true
  try {
    const users = await api.listUsersForLibrary()
    newLibUsers.value = Array.isArray(users) ? users.filter(u => u.id !== me.value?.id) : []
  } catch (e) { err.value = e.message; newLibUsers.value = [] }
  finally { newLibMembersLoading.value = false }
}
function onNewLibModeChange() {
  if (['self_plus', 'dept_plus', 'members_only'].includes(newLibMode.value)) loadNewLibUsers()
}
function openNewLib() {
  newLibCreating.value = false
  newLibParentId.value = null
  newLibName.value = ''; newLibDesc.value = ''; err.value = ''
  newLibAllowDownload.value = false
  newLibDepartmentId.value = activeDeptId.value || null
  newLibMode.value = newLibDepartmentId.value ? 'dept' : 'self'
  newLibMembers.value = []
  if (['self_plus', 'dept_plus', 'members_only'].includes(newLibMode.value)) loadNewLibUsers()
  newLibDeptPickerOpen.value = false
  newLibModePickerOpen.value = false
  showNewLib.value = true
}
function openNewLibSub() {
  const d = currentLib.value?.depth ?? 1
  if (Number(d) >= 3) {
    showError('最多三级资料库，无法在第三级下再创建子库')
    return
  }
  if (!currentLib.value?.is_writeable) {
    showError('您没有权限在此创建子资料库')
    return
  }
  newLibCreating.value = false
  newLibParentId.value = currentLib.value.id
  newLibName.value = ''
  newLibDesc.value = ''
  err.value = ''
  newLibDeptPickerOpen.value = false
  newLibModePickerOpen.value = false
  showNewLib.value = true
}

function closeNewLibModal() {
  if (newLibCreating.value) return
  showNewLib.value = false
  newLibDepartmentId.value = null
  newLibParentId.value = null
  err.value = ''
  showNewLibMemberPanel.value = false
  newLibDeptPickerOpen.value = false
  newLibModePickerOpen.value = false
}

function selectNewLibDept(opt) {
  newLibDepartmentId.value = opt.value == null ? null : opt.value
  newLibDeptPickerOpen.value = false
}

function selectNewLibMode(opt) {
  newLibMode.value = opt.value
  newLibModePickerOpen.value = false
  onNewLibModeChange()
}

function newLibDeptOptionSelected(opt) {
  const id = newLibDepartmentId.value
  return (
    (opt.value == null && (id == null || id === '')) ||
    (opt.value != null && Number(opt.value) === Number(id))
  )
}

function newLibModeOptionSelected(opt) {
  return opt.value === newLibMode.value
}
async function createLib() {
  if (newLibCreating.value) return
  err.value = ''
  const name = (newLibName.value || '').trim()
  if (!name) { err.value = '请填写文件库名称'; return }
  if (newLibParentId.value != null) {
    newLibCreating.value = true
    try {
      const created = await api.createLibrary(
        name,
        (newLibDesc.value || '').trim(),
        null,
        'private',
        [],
        false,
        newLibParentId.value
      )
      const parentWas = Number(newLibParentId.value)
      newLibParentId.value = null
      showNewLib.value = false
      newLibName.value = ''
      newLibDesc.value = ''
      newLibDepartmentId.value = null
      newLibMembers.value = []
      newLibUsers.value = []
      const stillOnParent = Number(currentLib.value?.id) === parentWas
      // 停留在父资料库视图并刷新「子资料库」列表（不要自动进入新建库，否则只看到空文件区，误以为未创建）
      if (stillOnParent) {
        await loadChildLibrariesForCurrent()
      } else {
        await loadLibraries()
      }
      showSuccess('子资料库已创建')
    } catch (e) {
      err.value = e.message || '创建失败'
    } finally {
      newLibCreating.value = false
    }
    return
  }
  const raw = newLibDepartmentId.value
  const deptId = raw === '' || raw === null || raw === undefined ? null : Number(raw)
  const mode = newLibMode.value || 'self'
  const isDeptLib = !!deptId
  let visibility = 'private'
  if (!isDeptLib) {
    if (['dept', 'dept_plus'].includes(mode)) { err.value = '个人库不支持部门访问模式，请取消所属部门或调整访问权限'; return }
    visibility = mode === 'public' ? 'public' : 'private'
  } else {
    if (!['dept', 'dept_plus'].includes(mode)) { err.value = '部门库仅支持「所属部门」或「所属部门 + 指定成员」模式'; return }
    visibility = 'department'
  }
  const memberIds = (newLibMembers.value || []).map(id => Number(id)).filter(id => !Number.isNaN(id))
  if (['self_plus', 'dept_plus', 'members_only'].includes(mode) && memberIds.length === 0) { err.value = '请选择至少一位指定成员'; return }
  newLibCreating.value = true
  try {
    const created = await api.createLibrary(name, (newLibDesc.value || '').trim(), deptId, visibility, memberIds, newLibAllowDownload.value)
    if (created?.id != null) {
      libraries.value = [created, ...libraries.value.filter(l => l.id !== created.id)]
    } else {
      libraries.value = await api.listLibraries({ include_department: false })
    }
    showNewLib.value = false
    newLibParentId.value = null
    newLibName.value = ''
    newLibDesc.value = ''
    newLibDepartmentId.value = null
    newLibVisibility.value = 'private'
    newLibMembers.value = []
    newLibUsers.value = []
    if (deptId != null && Number(activeDeptId.value) === Number(deptId)) {
      // 触发 DepartmentFiles 重新拉取部门文件库列表
      deptFilesReloadKey.value += 1
      activeDeptLibraries.value = await api.listDepartmentLibraries(deptId)
    }
    else if (!deptId) clearDeptView()
    showSuccess(deptId ? '部门文件库已创建' : '文件库已创建')
  } catch (e) { err.value = e.message || '创建失败' }
  finally { newLibCreating.value = false }
}
function delLib(lib) {
  libToDelete.value = lib
  showDeleteLibConfirm.value = true
}
async function doConfirmDeleteLib() {
  const lib = libToDelete.value
  if (!lib) { showDeleteLibConfirm.value = false; return }
  err.value = ''; errorMessage.value = ''
  try {
    await api.deleteLibrary(lib.id)
    libraries.value = await api.listLibraries({ include_department: false })
    if (currentLib.value?.id === lib.id) {
      currentLib.value = null
      libChildrenLibraries.value = []
    } else {
      await loadChildLibrariesForCurrent()
    }
    if (tab.value === 'trash') trashLibraryList.value = await api.listLibraryTrash()
    showSuccess('已移入回收站')
  } catch (e) { err.value = e.message; showError(e.message) }
  finally {
    showDeleteLibConfirm.value = false
    libToDelete.value = null
  }
}

function moveTargetOptionValue(t) {
  return t.parent_id == null ? 'root' : String(t.parent_id)
}

function moveTargetOptionKey(t) {
  return t.parent_id == null ? 'root' : `p-${t.parent_id}`
}

function selectMoveTargetOption(t) {
  moveTargetKey.value = moveTargetOptionValue(t)
  moveTargetPickerOpen.value = false
}

async function openMoveLib(lib) {
  if (!lib?.id) return
  libToMove.value = lib
  err.value = ''
  moveTargetKey.value = ''
  moveTargets.value = []
  moveTargetPickerOpen.value = false
  moveTargetsLoading.value = true
  showMoveLib.value = true
  try {
    const rows = await api.listLibraryMoveTargets(lib.id)
    moveTargets.value = Array.isArray(rows) ? rows : []
    if (moveTargets.value.length) {
      moveTargetKey.value = moveTargetOptionValue(moveTargets.value[0])
    }
  } catch (e) {
    err.value = e?.message || '无法加载可移动位置'
    moveTargets.value = []
  } finally {
    moveTargetsLoading.value = false
  }
}

function closeMoveLibModal() {
  showMoveLib.value = false
  libToMove.value = null
  moveTargets.value = []
  moveTargetKey.value = ''
  moveTargetPickerOpen.value = false
  err.value = ''
}

async function confirmMoveLib() {
  const lib = libToMove.value
  if (!lib?.id || moveLibSubmitting.value) return
  const key = moveTargetKey.value
  const parentId = key === 'root' ? null : Number(key)
  if (key !== 'root' && !Number.isFinite(parentId)) {
    err.value = '请选择目标位置'
    return
  }
  err.value = ''
  moveLibSubmitting.value = true
  try {
    const updated = await api.moveLibrary(lib.id, parentId)
    await loadLibraries()
    if (currentLib.value?.id === lib.id) {
      try {
        currentLib.value = await api.getLibrary(lib.id)
      } catch {
        currentLib.value = updated
      }
    }
    await loadChildLibrariesForCurrent()
    if (Number(activeDeptId.value) > 0) {
      deptFilesReloadKey.value += 1
      try {
        activeDeptLibraries.value = await api.listDepartmentLibraries(activeDeptId.value)
      } catch {
        /* 列表由 DepartmentFiles 的 reloadKey 同步拉取 */
      }
    }
    closeMoveLibModal()
    showSuccess('资料库已移动')
  } catch (e) {
    err.value = e?.message || '移动失败'
    showError(err.value)
  } finally {
    moveLibSubmitting.value = false
  }
}

async function openEditLib(lib) {
  let full = lib
  try {
    full = await api.getLibrary(lib.id)
  } catch {
    /* 使用列表项 */
  }
  editLibDepth.value = Number(full.depth) || 1
  editLibId.value = full.id
  editLibName.value = full.name
  editLibDesc.value = full.description || ''
  editLibAllowDownload.value = full.allow_download !== false
  editLibDepartmentId.value = full.department_id || null
  const vis = full.visibility || 'private'
  const hasMembers = (full.member_count || 0) > 0
  const isDeptLib = !!editLibDepartmentId.value
  if (isDeptLib) editLibMode.value = hasMembers ? 'dept_plus' : 'dept'
  else if (vis === 'public') editLibMode.value = 'public'
  else editLibMode.value = hasMembers ? 'self_plus' : 'self'
  editLibUsers.value = []; editLibMembers.value = []; editLibInitialMembers.value = []
  if (editLibDepth.value <= 1 && ['self_plus', 'dept_plus', 'members_only'].includes(editLibMode.value)) {
    await loadEditLibUsersAndMembers(full.id)
  }
  showEditLib.value = true; err.value = ''
}
async function loadEditLibUsersAndMembers(libraryId) {
  if (editLibMembersLoading.value) return
  editLibMembersLoading.value = true
  try {
    const [users, members] = await Promise.all([api.listUsersForLibrary(), api.listLibraryMembers(libraryId)])
    editLibUsers.value = Array.isArray(users) ? users.filter(u => u.id !== me.value?.id) : []
    const ids = Array.isArray(members) ? members.map(m => m.user_id) : []
    editLibMembers.value = ids; editLibInitialMembers.value = [...ids]
  } catch (e) { err.value = e.message; editLibUsers.value = []; editLibMembers.value = []; editLibInitialMembers.value = [] }
  finally { editLibMembersLoading.value = false }
}
function onEditLibModeChange() {
  if (!editLibId.value) return
  if (['self_plus', 'dept_plus', 'members_only'].includes(editLibMode.value)) loadEditLibUsersAndMembers(editLibId.value)
}
async function saveEditLib() {
  err.value = ''
  try {
    if (editLibDepth.value > 1) {
      const saved = await api.updateLibrary(
        editLibId.value,
        editLibName.value.trim(),
        editLibDesc.value.trim(),
        undefined,
        undefined
      )
      libraries.value = await api.listLibraries({ include_department: false })
      if (currentLib.value?.id === editLibId.value) {
        currentLib.value = saved
      }
      await loadChildLibrariesForCurrent()
      showEditLib.value = false
      showSuccess('资料库已更新')
      return
    }
    const mode = editLibMode.value || 'self'
    const isDeptLib = !!editLibDepartmentId.value
    let visibility = 'private'
    if (!isDeptLib) {
      if (['dept', 'dept_plus'].includes(mode)) { err.value = '个人库不支持部门访问模式'; return }
      visibility = mode === 'public' ? 'public' : 'private'
    } else {
      if (!['dept', 'dept_plus'].includes(mode)) { err.value = '部门库仅支持「所属部门」或「所属部门 + 指定成员」模式'; return }
      visibility = 'department'
    }
    const memberIds = (editLibMembers.value || []).map(id => Number(id)).filter(id => !Number.isNaN(id))
    if (['self_plus', 'dept_plus', 'members_only'].includes(mode) && memberIds.length === 0) { err.value = '请选择至少一位指定成员'; return }
    const saved = await api.updateLibrary(
      editLibId.value,
      editLibName.value.trim(),
      editLibDesc.value.trim(),
      visibility,
      editLibAllowDownload.value
    )
    libraries.value = await api.listLibraries({ include_department: false })
    // 部门库不在「我的文件库」列表里，不能用 find 更新 currentLib，否则会变成 undefined，界面仍显示旧名称
    if (currentLib.value?.id === editLibId.value) {
      currentLib.value = saved
    }
    if (
      editLibDepartmentId.value != null &&
      activeDeptId.value != null &&
      Number(editLibDepartmentId.value) === Number(activeDeptId.value)
    ) {
      deptFilesReloadKey.value += 1
      await loadDeptFiles(activeDeptId.value)
    }
    if (editLibId.value) {
      const libId = editLibId.value
      const oldSet = new Set((editLibInitialMembers.value || []).map(id => Number(id)))
      if (['self_plus', 'dept_plus', 'members_only'].includes(mode)) {
        const newSet = new Set(memberIds)
        for (const id of oldSet) { if (!newSet.has(id)) await api.removeLibraryMember(libId, id) }
        for (const id of newSet) { if (!oldSet.has(id)) await api.addLibraryMember(libId, id, 'read') }
      } else {
        for (const id of oldSet) await api.removeLibraryMember(libId, id)
      }
    }
    // 成员变更后补拉一次，保证 member_count 等与后端一致
    if (currentLib.value?.id === editLibId.value) {
      try {
        currentLib.value = await api.getLibrary(editLibId.value)
      } catch {
        /* 保留 saved */
      }
    }
    showEditLib.value = false; showSuccess('资料库已更新')
  } catch (e) { err.value = e.message }
}

// ---- 部门 ----

async function handleDeptSelect(node) {
  tab.value = 'lib'; currentLib.value = null; pathPrefix.value = ''; activeDeptId.value = node.id
  await loadDeptFiles(node.id)
}
function clearDeptView() { activeDeptId.value = null; activeDeptInfo.value = null; activeDeptLibraries.value = []; activeDeptErr.value = '' }
async function loadDeptFiles(deptId) {
  activeDeptLoading.value = true; activeDeptErr.value = ''
  try {
    activeDeptInfo.value = await api.getDepartmentInfo(deptId)
    if (!activeDeptInfo.value?.has_access) { activeDeptLibraries.value = []; return }
    activeDeptLibraries.value = await api.listDepartmentLibraries(deptId)
  } catch (e) { activeDeptErr.value = e.message || '加载部门库失败'; activeDeptLibraries.value = [] }
  finally { activeDeptLoading.value = false }
}
function openDeptLib(lib) { selectLib(lib) }
async function loadDepartments() {
  deptTreeRefreshKey.value++
  try { deptTreeForTable.value = await api.getDepartmentTree() }
  catch { deptTreeForTable.value = [] }
}
function openAddRootDept() { newRootDeptName.value = ''; err.value = ''; showAddRootDept.value = true }
async function doAddRootDept() {
  err.value = ''; const name = newRootDeptName.value?.trim()
  if (!name) { err.value = '请输入部门名称'; return }
  try { await api.createDepartment(name, null, 0); showAddRootDept.value = false; newRootDeptName.value = ''; deptTreeRefreshKey.value++; await loadDepartments(); showSuccess('根部门已创建') }
  catch (e) { err.value = e.message }
}
function openAddSubDept(node) { addSubDeptParent.value = node; addSubDeptName.value = ''; err.value = ''; showAddSubDept.value = true }
async function doAddSubDept() {
  if (!addSubDeptParent.value) return
  err.value = ''; const name = addSubDeptName.value?.trim()
  if (!name) { err.value = '请输入部门名称'; return }
  try { await api.createDepartment(name, addSubDeptParent.value.id, 0); showAddSubDept.value = false; addSubDeptParent.value = null; addSubDeptName.value = ''; await loadDepartments(); showSuccess('子部门已创建') }
  catch (e) { err.value = e.message }
}
function openEditDept(node) { editDeptNode.value = node; editDeptName.value = node.name; showEditDept.value = true; err.value = '' }
async function doSaveEditDept() {
  if (!editDeptNode.value) return
  err.value = ''; const name = editDeptName.value?.trim()
  if (!name) { err.value = '请输入部门名称'; return }
  try { await api.updateDepartment(editDeptNode.value.id, { name }); showEditDept.value = false; editDeptNode.value = null; await loadDepartments(); showSuccess('部门已更新') }
  catch (e) { err.value = e.message }
}
async function doDeleteDept(node) {
  if (!confirm('确定删除部门「' + node.name + '」？其子部门将一并删除。')) return
  try { await api.deleteDepartment(node.id); await loadDepartments(); showSuccess('已删除') }
  catch (e) { showError(e.message || '删除失败') }
}

// ---- 用户管理 ----

async function loadUsers() {
  try {
    const params = {}
    const kw = sysSearchKeyword.value?.trim()
    if (kw) params.search = kw
    if (userFilterStatus.value === 'active') params.is_active = true
    if (userFilterStatus.value === 'inactive') params.is_active = false
    userList.value = await api.listUsers(params)
  } catch (e) { err.value = e.message }
}

// 部门成员管理逻辑现已迁移到 Admin.vue
async function loadAudit() {
  if (tab.value !== 'sys') return
  try {
    const params = { limit: 200 }
    if (auditUsername.value.trim()) params.username = auditUsername.value.trim()
    if (auditAction.value.trim()) params.action = auditAction.value.trim()
    if (auditStartDate.value) params.start_date = auditStartDate.value
    if (auditEndDate.value) params.end_date = auditEndDate.value
    auditList.value = await api.listAuditLogs(params)
  } catch (e) { err.value = e.message }
}
async function doChangePassword() {
  err.value = ''
  if (!newPassword.value) { err.value = '请输入新密码'; return }
  const pwdErr = _checkStrongPassword(newPassword.value)
  if (pwdErr) { err.value = pwdErr; return }
  if (newPassword.value !== newPassword2.value) { err.value = '两次输入的新密码不一致'; return }
  try {
    await api.changePassword(oldPassword.value, newPassword.value)
    showChangePw.value = false; oldPassword.value = ''; newPassword.value = ''; newPassword2.value = ''; showSuccess('密码已修改')
  } catch (e) { err.value = e.message }
}
function closeCreateUser() { showCreateUser.value = false; newUserEmail.value = ''; newUserUsername.value = ''; newUserPassword.value = ''; newUserIsSuperuser.value = false; err.value = '' }
function _checkStrongPassword(pwd) {
  if (pwd.length < 8) return '密码至少8位'
  if (!/[A-Z]/.test(pwd)) return '密码须包含至少1个大写字母'
  if (!/[a-z]/.test(pwd)) return '密码须包含至少1个小写字母'
  if (!/\d/.test(pwd)) return '密码须包含至少1个数字'
  if (!/[!@#$%^&*()_+\-=[\]{};':"\\|,.<>/?`~]/.test(pwd)) return '密码须包含至少1个特殊字符'
  return ''
}
async function doCreateUserModal() {
  err.value = ''
  if (!newUserEmail.value.trim()) { err.value = '请填写邮箱（用于登录）'; return }
  if (!newUserUsername.value.trim()) { err.value = '请填写用户名（用于显示）'; return }
  if (!newUserPassword.value) { err.value = '请填写密码'; return }
  const pwdErr = _checkStrongPassword(newUserPassword.value)
  if (pwdErr) { err.value = pwdErr; return }
  try {
    const isSuper = newUserRole.value === 'admin' || newUserIsSuperuser.value
    const deptId = newUserDeptId.value ? Number(newUserDeptId.value) : null
    await api.createUser(newUserEmail.value.trim(), newUserUsername.value.trim(), newUserPassword.value, isSuper, deptId, 'staff')
    showSuccess('用户已创建：' + newUserUsername.value); closeCreateUser(); loadUsers()
  } catch (e) { err.value = e.message }
}
async function toggleUserActive(u) {
  if (u.id === me.value?.id) return
  const action = u.is_active ? '禁用' : '启用'
  if (!confirm('确定' + action + '用户「' + u.username + '」？')) return
  err.value = ''
  try { await api.updateUser(u.id, { is_active: !u.is_active }); await loadUsers() }
  catch (e) { err.value = e.message }
}
async function resetUserPassword(u) {
  const newPw = prompt('请输入新密码（8位以上，含大小写、数字、特殊字符）：', '')
  if (newPw == null || newPw === '') return
  const pwdErr = _checkStrongPassword(newPw)
  if (pwdErr) { err.value = pwdErr; return }
  err.value = ''
  try { await api.updateUser(u.id, { new_password: newPw }); showSuccess('已重置「' + u.username + '」的密码') }
  catch (e) { err.value = e.message }
}
</script>

<style scoped>
.app-layout {
  display: flex;
  height: 100vh;
  min-height: 100vh;
  overflow: hidden;
  background: #fff;
}
.app-layout-admin .app-main { width: 100%; }
.app-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  background: var(--bg-page);
}
.app-main-scroll {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  -webkit-overflow-scrolling: touch;
  position: relative;
}
.success-toast {
  position: fixed; top: 20px; left: 50%; transform: translateX(-50%); z-index: 9999;
  background: var(--success-bg, #e8f5e9); color: var(--success, #2e7d32);
  padding: 12px 24px; border-radius: var(--radius, 8px); font-size: 14px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.15);
}
.error-toast {
  position: fixed; top: 20px; left: 50%; transform: translateX(-50%); z-index: 9999;
  background: #ffebee; color: #c62828;
  padding: 12px 24px; border-radius: var(--radius, 8px); font-size: 14px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.15);
}
.toast-enter-active { animation: toast-in 0.3s ease-out; }
.toast-leave-active { animation: toast-out 0.3s ease-in; }
@keyframes toast-in { from { opacity: 0; transform: translate(-50%, -20px); } to { opacity: 1; transform: translate(-50%, 0); } }
@keyframes toast-out { from { opacity: 1; transform: translate(-50%, 0); } to { opacity: 0; transform: translate(-50%, -20px); } }
.text-danger { color: var(--danger); font-size: 14px; margin: 0 0 8px 0; }
.app-content .card { background: #fff; }
.empty-hint { color: var(--text-secondary); font-size: 14px; margin: 12px 0; }
.modal {
  position: fixed; inset: 0; background: rgba(0,0,0,0.45);
  display: flex; align-items: center; justify-content: center; z-index: 10;
}
.modal .card { max-width: 440px; width: 90%; max-height: 90vh; overflow: auto; background: #fff; }
.modal .card.move-lib-modal-card { overflow: visible; }
.modal .card h3 { margin-top: 0; }
.modal .form-group { margin-bottom: 16px; }
.modal .form-group label { display: block; font-size: 14px; font-weight: 500; color: var(--text); margin-bottom: 6px; }
.modal .form-group input { width: 100%; box-sizing: border-box; padding: 8px 12px; }
.modal .form-hint { margin: 6px 0 0 0; font-size: 12px; color: #9ca3af; }
.modal-actions { margin-top: 16px; display: flex; gap: 10px; flex-wrap: wrap; }
.label-opt { font-weight: normal; color: var(--text-secondary); font-size: 12px; }
.preview-card { min-width: 50vw; min-height: 50vh; width: 92vw; height: 90vh; max-width: 95vw; max-height: 92vh; display: flex; flex-direction: column; overflow: hidden; }
.preview-loading { padding: 40px; text-align: center; color: var(--text-secondary); }
.preview-body { flex: 1; overflow: auto; min-height: 50vh; display: flex; justify-content: center; align-items: flex-start; padding: 12px; }
.preview-img { max-width: 100%; min-height: 50vh; max-height: 82vh; object-fit: contain; }
.preview-iframe { width: 88vw; min-width: 50vw; min-height: 50vh; height: 82vh; border: 1px solid var(--border); border-radius: 6px; }
.preview-text { margin: 0; padding: 12px; font-family: inherit; font-size: 13px; white-space: pre-wrap; word-break: break-all; min-width: 50vw; min-height: 50vh; max-width: 85vw; max-height: 82vh; overflow: auto; background: #f8f9fa; border-radius: 6px; border: 1px solid var(--border); text-align: left; }
.versions-card {
  width: 560px;
  max-width: 92vw;
  max-height: 80vh;
  overflow-y: auto;
  overflow-x: hidden;
}
.versions-fileinfo {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 10px 12px;
  background: #f3f4f6;
  border-radius: 6px;
  margin-bottom: 16px;
  font-size: 13px;
  line-height: 1.6;
}
.versions-fileinfo-label {
  color: #9ca3af;
  white-space: nowrap;
  flex-shrink: 0;
}
.versions-fileinfo-text {
  color: #374151;
  word-break: break-all;
}
.versions-card .versions-table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
}
.versions-card th,
.versions-card td {
  padding: 8px 10px;
  white-space: nowrap; /* 单行显示，内容本身较短，不做截断 */
}
.versions-card thead {
  position: sticky;
  top: 0;
  background: #f9fafb;
  z-index: 1;
}
.add-member-row { display: flex; gap: 10px; align-items: center; margin-bottom: 16px; }
.members-table { width: 100%; border-collapse: collapse; margin-top: 12px; }
.members-table th, .members-table td { padding: 8px 12px; text-align: left; border-bottom: 1px solid var(--border); }
.badge { padding: 2px 8px; border-radius: 4px; font-size: 12px; }
.badge-user { background: #f3f4f6; color: var(--text-secondary); }
.btn-small { font-size: 12px; padding: 4px 10px; }
.admin-select { padding: 8px 12px; border: 1px solid var(--border); border-radius: 8px; font-size: 14px; min-width: 120px; }

/* 移动资料库：自定义目标位置下拉（替代原生 select） */
.move-target-picker { position: relative; width: 100%; }
.move-target-picker-trigger {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-height: 40px;
  padding: 8px 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  font-size: 14px;
  cursor: pointer;
  background: #fff;
  color: var(--text, #111827);
  text-align: left;
  box-sizing: border-box;
}
.move-target-picker-trigger:hover:not(:disabled) {
  border-color: var(--primary);
}
.move-target-picker-trigger:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.move-target-picker-value {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.move-target-picker-chevron {
  flex-shrink: 0;
  color: var(--text-secondary, #6b7280);
  font-size: 12px;
  line-height: 1;
  transition: transform 0.15s ease;
}
.move-target-picker-trigger[aria-expanded="true"] .move-target-picker-chevron {
  transform: rotate(180deg);
}
.move-target-picker-panel {
  position: absolute;
  left: 0;
  right: 0;
  top: calc(100% + 4px);
  z-index: 30;
  max-height: 240px;
  overflow-y: auto;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 10px 28px rgba(15, 23, 42, 0.14);
  padding: 4px 0;
}
.move-target-picker-option {
  display: block;
  width: 100%;
  padding: 8px 12px;
  border: none;
  background: transparent;
  font-size: 14px;
  text-align: left;
  cursor: pointer;
  color: var(--text, #111827);
}
.move-target-picker-option:hover {
  background: #f3f4f6;
}
.move-target-picker-option.selected {
  background: #eef2ff;
  color: var(--primary);
  font-weight: 500;
}

.member-multi-dropdown { position: relative; }
.member-select-trigger { width: 100%; min-height: 32px; border: 1px solid var(--border); border-radius: var(--radius); padding: 6px 10px; font-size: 13px; cursor: pointer; background: #fff; }
.member-select-trigger:hover { border-color: var(--primary); }
.member-panel { margin-top: 8px; border: 1px solid var(--border); border-radius: var(--radius); padding: 8px; max-height: 220px; overflow: hidden; background: #fff; }
.member-search { width: 100%; padding: 4px 8px; font-size: 13px; margin-bottom: 8px; border: 1px solid var(--border); border-radius: var(--radius); }
.member-list { max-height: 140px; overflow-y: auto; padding-right: 4px; text-align: left; }
.member-option { display: flex; align-items: center; justify-content: flex-start; gap: 6px; font-size: 13px; margin-bottom: 4px; padding: 2px 0; }
.member-option input[type="checkbox"] { flex: 0 0 auto !important; display: inline-block !important; margin: 0 !important; width: 16px !important; height: 16px !important; }
.member-name { font-weight: 500; }
.member-email { font-size: 12px; color: var(--text-secondary); }
.member-panel-actions { margin-top: 6px; text-align: right; }

/* Toggle switch (导出权限开关) */
.toggle-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: #fff;
}
.toggle-label {
  font-size: 13px;
  color: #111827;
  font-weight: 500;
}
.toggle {
  position: relative;
  width: 46px;
  height: 26px;
  flex-shrink: 0;
}
.toggle input {
  opacity: 0;
  width: 0;
  height: 0;
}
.toggle-track {
  position: absolute;
  inset: 0;
  border-radius: 999px;
  background: #e5e7eb;
  transition: background-color 0.15s ease;
  box-shadow: inset 0 0 0 1px rgba(0,0,0,0.06);
}
.toggle-track::after {
  content: '';
  position: absolute;
  top: 3px;
  left: 3px;
  width: 20px;
  height: 20px;
  border-radius: 999px;
  background: #ffffff;
  box-shadow: 0 2px 6px rgba(15, 23, 42, 0.18);
  transition: transform 0.15s ease;
}
.toggle input:checked + .toggle-track {
  background: var(--primary);
}
.toggle input:checked + .toggle-track::after {
  transform: translateX(20px);
}
.toggle input:focus-visible + .toggle-track {
  box-shadow: 0 0 0 3px rgba(26, 86, 176, 0.18);
}
.toggle input:disabled + .toggle-track {
  opacity: 0.6;
  cursor: not-allowed;
}
.user-modal-card { max-width: 520px; }
.user-modal-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px 16px; margin-top: 12px; }
@media (max-width: 640px) { .user-modal-grid { grid-template-columns: 1fr; } }

/* 上传文件弹窗（新 UI） */
.upload-modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 50;
  padding: 16px;
}
.upload-modal-card {
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
  width: 100%;
  max-width: 32rem;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
}
.upload-modal-card.new-lib-modal-card {
  max-width: 34rem;
}
.new-lib-modal-body .form-group {
  margin-bottom: 16px;
}
.new-lib-modal-body .form-group:last-of-type {
  margin-bottom: 0;
}
.new-lib-modal-body .form-group label {
  display: block;
  font-size: 14px;
  font-weight: 500;
  color: #111827;
  margin-bottom: 6px;
}
.new-lib-modal-body .form-group input:not([type='checkbox']),
.new-lib-modal-body .form-group select.admin-select {
  width: 100%;
  box-sizing: border-box;
}
.new-lib-modal-body .form-hint {
  margin: 6px 0 0 0;
  font-size: 12px;
  color: #6b7280;
}
.new-lib-modal-err {
  margin-top: 12px;
}
.upload-modal-close:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
/* 打开自定义下拉时避免被 upload-modal-body 裁切 */
.upload-modal-card.new-lib-modal-card .upload-modal-body.new-lib-modal-body.new-lib-body-picker-open {
  overflow: visible;
}
.upload-modal-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  padding: 20px 24px;
  border-bottom: 1px solid #e5e7eb;
}
.upload-modal-title {
  font-size: 1.25rem;
  font-weight: 600;
  color: #111827;
  margin: 0;
}
.upload-modal-subtitle {
  font-size: 0.875rem;
  color: #6b7280;
  margin: 4px 0 0 0;
}
.upload-modal-close {
  padding: 8px;
  border: none;
  background: transparent;
  border-radius: 8px;
  cursor: pointer;
  color: #6b7280;
}
.upload-modal-close:hover {
  background: #f3f4f6;
  color: #111827;
}
.upload-modal-close-icon {
  width: 20px;
  height: 20px;
}
.upload-modal-body {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
}
.upload-dropzone {
  border: 2px dashed #d1d5db;
  border-radius: 12px;
  padding: 48px 24px;
  text-align: center;
  cursor: pointer;
  transition: border-color 0.2s, background 0.2s;
}
.upload-dropzone:hover,
.upload-dropzone-active {
  border-color: #4a90e2;
  background: #eff6ff;
}
.upload-dropzone-small {
  padding: 16px;
  margin-bottom: 12px;
}
.upload-dropzone-icon {
  width: 64px;
  height: 64px;
  color: #9ca3af;
  margin: 0 auto 16px;
  display: block;
}
.upload-dropzone-icon-small {
  width: 32px;
  height: 32px;
  color: #9ca3af;
  margin: 0 auto 8px;
  display: block;
}
.upload-dropzone-title {
  font-size: 1.125rem;
  font-weight: 600;
  color: #111827;
  margin: 0 0 8px 0;
}
.upload-dropzone-hint {
  font-size: 0.875rem;
  color: #6b7280;
  margin: 0 0 16px 0;
}
.upload-dropzone-hint-small {
  font-size: 0.875rem;
  color: #4b5563;
  margin: 0;
}
.upload-dropzone-limit {
  font-size: 0.75rem;
  color: #9ca3af;
  margin: 0;
}
.upload-modal-input-hidden {
  position: absolute;
  width: 0;
  height: 0;
  opacity: 0;
  pointer-events: none;
}
.upload-file-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.upload-file-item {
  background: #f9fafb;
  border-radius: 8px;
  padding: 16px;
  border: 1px solid #e5e7eb;
  display: flex;
  align-items: flex-start;
  gap: 12px;
}
.upload-file-item-icon {
  flex-shrink: 0;
  margin-top: 2px;
}
.upload-file-item-icon .icon {
  width: 20px;
  height: 20px;
}
.icon-purple { color: #a855f7; }
.icon-blue { color: #3b82f6; }
.icon-gray { color: #6b7280; }
.upload-file-item-main {
  flex: 1;
  min-width: 0;
}
.upload-file-item-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 4px;
}
.upload-file-item-name {
  font-size: 0.875rem;
  font-weight: 500;
  color: #111827;
  margin: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  padding-right: 8px;
}
.upload-file-item-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.upload-file-loader { width: 16px; height: 16px; color: #4a90e2; }
.upload-file-success { width: 20px; height: 20px; color: #22c55e; }
.upload-file-error { width: 20px; height: 20px; color: #ef4444; }
.upload-file-remove {
  padding: 4px;
  border: none;
  background: transparent;
  border-radius: 4px;
  cursor: pointer;
  color: #6b7280;
}
.upload-file-remove:hover {
  background: #e5e7eb;
  color: #111827;
}
.upload-file-remove-icon { width: 16px; height: 16px; }
.upload-file-item-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.upload-file-item-size {
  font-size: 0.75rem;
  color: #6b7280;
}
.upload-file-item-progress {
  font-size: 0.75rem;
  color: #4a90e2;
}
.upload-file-item-status {
  font-size: 0.75rem;
}
.upload-file-item-status.success { color: #16a34a; }
.upload-file-item-status.error { color: #dc2626; }
.upload-file-progress-bar {
  width: 100%;
  height: 6px;
  background: #e5e7eb;
  border-radius: 999px;
  overflow: hidden;
}
.upload-file-progress-fill {
  height: 100%;
  border-radius: 999px;
  background: #4a90e2;
  transition: width 0.3s ease;
}
.upload-file-progress-fill.success { background: #22c55e; }
.upload-file-progress-fill.error { background: #ef4444; }
.upload-modal-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 24px;
  border-top: 1px solid #e5e7eb;
  background: #f9fafb;
}
.upload-modal-footer-left {
  font-size: 0.875rem;
  color: #4b5563;
}
.upload-modal-footer-error { color: #dc2626; }
.upload-modal-footer-actions {
  display: flex;
  gap: 12px;
}
.upload-btn-secondary {
  padding: 8px 16px;
  font-size: 0.875rem;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  background: #fff;
  color: #374151;
  cursor: pointer;
}
.upload-btn-secondary:hover {
  background: #f9fafb;
  border-color: #9ca3af;
}
.upload-btn-primary {
  padding: 8px 16px;
  font-size: 0.875rem;
  border: none;
  border-radius: 8px;
  background: #4a90e2;
  color: #fff;
  cursor: pointer;
}
.upload-btn-primary:hover:not(:disabled) {
  background: #357abd;
}
.upload-btn-primary:disabled {
  background: #d1d5db;
  cursor: not-allowed;
}
.vm-result-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  cursor: pointer;
  border-bottom: 1px solid #e5e7eb;
  transition: background 0.15s;
}
.vm-result-row:last-child {
  border-bottom: none;
}
.vm-result-row:hover {
  background: #f3f4f6;
}
.vm-result-row.selected {
  background: #e8f0fa;
}
</style>
