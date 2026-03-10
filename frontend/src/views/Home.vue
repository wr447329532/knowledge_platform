<template>
  <div class="app-layout" :class="{ 'app-layout-admin': tab === 'sys' }">

    <!-- 左侧导航 -->
    <AppSidebar
      v-if="tab !== 'sys'"
      :me="me"
      :active-tab="tab"
      :active-dept-id="activeDeptId"
      :storage-stats="storageStats"
      @nav="onNav"
      @dept-select="handleDeptSelect"
      @go-admin="goAdmin"
      @change-password="showChangePw = true"
      @logout="logout"
    />

    <!-- 右侧主区域 -->
    <div class="app-main">

      <!-- 顶部工具栏 -->
      <AppTopbar
        v-if="tab !== 'sys'"
        :active-tab="tab"
        :active-dept-id="activeDeptId"
        :current-lib="currentLib"
        v-model:searchKeyword="searchKeyword"
        v-model:fileSortOrder="fileSortOrder"
        v-model:fileViewMode="fileViewMode"
        :breadcrumb-segments="breadcrumbSegments"
        @search="doSearch"
        @new-lib="openNewLib"
        @upload="showUpload = true; uploadErr = ''"
        @clear-lib="currentLib = null; pathPrefix = ''"
        @set-path="p => pathPrefix = p"
      />

      <!-- Toast 提示 -->
      <Transition name="toast">
        <div v-if="successMessage" class="success-toast">{{ successMessage }}</div>
      </Transition>
      <Transition name="toast">
        <div v-if="errorMessage" class="error-toast">{{ errorMessage }}</div>
      </Transition>

      <!-- 我的文件库 -->
      <LibraryPage
        v-if="tab === 'lib'"
        :active-dept-id="activeDeptId"
        :active-dept-info="activeDeptInfo"
        :active-dept-libraries="activeDeptLibraries"
        :active-dept-loading="activeDeptLoading"
        :active-dept-err="activeDeptErr"
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
        :path-prefix="pathPrefix"
        :open-action-menu-id="openActionMenuId"
        :format-date="formatDate"
        :format-size="formatSize"
        :open-dept-lib="openDeptLib"
        :select-lib="selectLib"
        :open-edit-lib="openEditLib"
        :del-lib="delLib"
        :on-file-drop="onFileDrop"
        :go-to-path="goToPath"
        :on-file-click="onFileClick"
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
      />

      <!-- 共享文件 -->
      <SharedPage
        v-if="tab === 'shared'"
        :shared-sub-tab="sharedSubTab"
        :my-shares-list="mySharesList"
        :my-shares-loading="mySharesLoading"
        :received-shares-list="receivedSharesList"
        :received-shares-loading="receivedSharesLoading"
        @tab="onSharedTab"
        @remove-share="removeShare"
        @open-shared-lib="openSharedLib"
      />

      <!-- 回收站 -->
      <TrashPage
        v-if="tab === 'trash'"
        :libraries="libraries"
        :trash-lib-id="trashLibId"
        :trash-list="trashList"
        :trash-loading="trashLoading"
        :format-date="formatDate"
        @lib-change="v => { trashLibId = v; loadTrash() }"
        @restore="restore"
        @perm-delete="permDelete"
      />

    </div><!-- /app-main -->

    <!-- ============ 弹窗区 ============ -->

    <!-- 新建资料库 -->
    <div v-if="showNewLib" class="modal">
      <div class="card">
        <h3>新建资料库</h3>
        <div class="form-group">
          <label>名称 <span class="label-opt">必填</span></label>
          <input v-model="newLibName" placeholder="资料库名称" />
        </div>
        <div class="form-group">
          <label>描述 <span class="label-opt">选填</span></label>
          <input v-model="newLibDesc" placeholder="简要描述" />
        </div>
        <div class="form-group">
          <label>所属部门</label>
          <select v-model="newLibDepartmentId" class="admin-select" style="width:100%;">
            <option :value="null">无（个人库）</option>
            <option v-for="opt in deptOptionsForUser" :key="opt.id" :value="opt.id">
              {{ '　'.repeat(opt.level) + opt.name }}
            </option>
          </select>
          <p class="form-hint">选择部门则创建为部门共享库，部门成员均可访问</p>
        </div>
        <div class="form-group">
          <label>访问权限</label>
          <select v-model="newLibMode" class="admin-select" style="width:100%;" @change="onNewLibModeChange">
            <option v-if="!newLibDepartmentId" value="self">仅自己</option>
            <option v-if="!newLibDepartmentId" value="self_plus">仅自己 + 指定成员</option>
            <option v-if="!newLibDepartmentId" value="members_only">仅指定成员</option>
            <option v-if="!newLibDepartmentId" value="public">公开（所有用户）</option>
            <option v-if="newLibDepartmentId" value="dept">所属部门</option>
            <option v-if="newLibDepartmentId" value="dept_plus">所属部门 + 指定成员</option>
          </select>
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
        <p v-if="err" class="text-danger">{{ err }}</p>
        <div class="modal-actions">
          <button class="primary" @click="createLib">确定</button>
          <button @click="showNewLib = false; newLibDepartmentId = null">取消</button>
        </div>
      </div>
    </div>

    <!-- 上传文件 -->
    <div v-if="showUpload" class="modal">
      <div class="card">
        <h3>上传文件</h3>
        <p>路径前缀: {{ pathPrefix || '/' }}</p>
        <input type="file" ref="fileInput" @change="onFileSelect" />
        <input v-model="uploadPath" placeholder="相对路径，如 readme.txt（留空则用文件名）" style="width:100%; margin-top:8px;" />
        <p v-if="uploadErr" class="text-danger" style="margin-top:12px; font-weight:600;">{{ uploadErr }}</p>
        <div class="modal-actions">
          <button class="primary" @click="upload">上传</button>
          <button @click="showUpload = false">取消</button>
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
      <div class="card">
        <h3>版本历史</h3>
        <table>
          <thead><tr><th>版本</th><th>大小</th><th>时间</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="v in versions" :key="v.id">
              <td>{{ v.version_no }}</td>
              <td>{{ v.size }}</td>
              <td>{{ formatDate(v.uploaded_at) }}</td>
              <td><button @click="download(versionEntryId, v.version_no)">下载</button></td>
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
          <select v-model="sharePermission" style="width: 120px;">
            <option value="read">只读（可预览）</option>
          </select>
          <button class="primary btn-small" @click="doAddShare">添加</button>
        </div>
        <table class="members-table">
          <thead><tr><th>用户</th><th>权限</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="s in shareList" :key="s.id">
              <td>{{ s.username }}</td>
              <td><span class="badge badge-user">只读</span></td>
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
        <div class="form-group" style="margin-bottom: 8px;">
          <label>访问权限</label>
          <select v-model="editLibMode" class="admin-select" style="width:100%;" @change="onEditLibModeChange">
            <option v-if="!currentLib?.department_id" value="self">仅自己</option>
            <option v-if="!currentLib?.department_id" value="self_plus">仅自己 + 指定成员</option>
            <option v-if="!currentLib?.department_id" value="members_only">仅指定成员</option>
            <option v-if="!currentLib?.department_id" value="public">公开（所有用户）</option>
            <option v-if="currentLib?.department_id" value="dept">所属部门</option>
            <option v-if="currentLib?.department_id" value="dept_plus">所属部门 + 指定成员</option>
          </select>
          <p class="form-hint">个人库可控制是否公开或仅指定成员；部门库始终对所在部门成员开放，可额外指定跨部门成员。</p>
        </div>
        <div class="form-group" v-if="['self_plus', 'dept_plus', 'members_only'].includes(editLibMode)">
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
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import * as api from '../api/client'
import Icons from '../components/Icons.vue'
import DepartmentTree from '../components/DepartmentTree.vue'
import DepartmentTableRow from '../components/DepartmentTableRow.vue'
import LibraryPage from '../components/LibraryPage.vue'
import AppSidebar from '../components/AppSidebar.vue'
import AppTopbar from '../components/AppTopbar.vue'
import SharedPage from '../components/SharedPage.vue'
import TrashPage from '../components/TrashPage.vue'

const router = useRouter()
const me = ref(null)
const tab = ref('lib')
const subTab = ref('users')
const sysSearchKeyword = ref('')
const showNewDropdown = ref(false)
const newDropdownRef = ref(null)
const deptTreeRefreshKey = ref(0)
const libraries = ref([])
const currentLib = ref(null)
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
const newLibAllowDownload = ref(true)
const newLibUsers = ref([])
const newLibMembers = ref([])
const newLibMembersLoading = ref(false)
const showNewLibMemberPanel = ref(false)
const newLibMemberKeyword = ref('')
const showUpload = ref(false)
const uploadPath = ref('')
const selectedFile = ref(null)
const showMkdir = ref(false)
const mkdirPath = ref('')
const err = ref('')
const trashLibId = ref('')
const trashList = ref([])
const trashLoading = ref(false)
const mySharesList = ref([])
const mySharesLoading = ref(false)
const sharedSubTab = ref('mine')
const receivedSharesList = ref([])
const receivedSharesLoading = ref(false)
const auditList = ref([])
const showVersions = ref(false)
const versions = ref([])
const versionEntryId = ref(null)
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
const editLibId = ref(null)
const editLibName = ref('')
const editLibDesc = ref('')
const editLibMode = ref('self')
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
const storageStats = ref(null)
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
const uploadErr = ref('')

// ---- computed ----

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

const sortedLibraries = computed(() => {
  const list = libraries.value || []
  if (!list.length) return list
  const arr = [...list]
  if (fileSortOrder.value === 'name') arr.sort((a, b) => (a.name || '').localeCompare(b.name || ''))
  else if (fileSortOrder.value === 'size') arr.sort((a, b) => (b.member_count || 0) - (a.member_count || 0))
  else if (fileSortOrder.value === 'created') arr.sort((a, b) => (a.id || 0) - (b.id || 0))
  return arr
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
const sortedFiles = computed(() => _sortFileList(files.value))
const sortedSearchResults = computed(() => _sortFileList(searchResults.value))

// ---- 导航事件 ----

function onNav(newTab) {
  if (newTab === 'lib') { tab.value = 'lib'; clearDeptView(); err.value = '' }
  if (newTab === 'shared') { tab.value = 'shared'; sharedSubTab.value = 'mine'; err.value = ''; loadMyShares() }
  if (newTab === 'trash') { tab.value = 'trash'; err.value = ''; loadTrash() }
}

function onSharedTab(subtab) {
  sharedSubTab.value = subtab
  if (subtab === 'mine') loadMyShares()
  else loadReceivedShares()
}

// ---- 工具函数 ----

function logout() { api.logout() }
function goAdmin() { router.push('/admin') }
function formatDate(s) { if (!s) return '-'; return new Date(s).toLocaleString('zh-CN') }
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

// ---- 生命周期 ----

onMounted(async () => {
  me.value = await api.getMe()
  libraries.value = await api.listLibraries()
  loadStorageStats()
  await loadDepartments()
})

watch(subTab, val => { if (val === 'departments') loadDepartments() })
watch([currentLib, pathPrefix], () => { if (currentLib.value) loadFiles(); searchResults.value = [] })
watch(showNewDropdown, open => {
  if (!open) return
  const onDocClick = () => { showNewDropdown.value = false; document.removeEventListener('click', onDocClick) }
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

// ---- 存储统计 ----

async function loadStorageStats() {
  try { storageStats.value = await api.getStorageStats() } catch { storageStats.value = null }
}

// ---- 搜索 ----

function clearSearch() { searchResults.value = []; searchKeyword.value = '' }
async function doSearch() {
  if (!currentLib.value || !searchKeyword.value?.trim()) { searchResults.value = []; return }
  try { searchResults.value = await api.searchFiles(currentLib.value.id, searchKeyword.value.trim()) }
  catch (e) { err.value = e.message; searchResults.value = [] }
}
function goToPath(path) {
  const dir = path.endsWith('/') ? path.slice(0, -1) : path
  const i = dir.lastIndexOf('/')
  pathPrefix.value = i >= 0 ? dir.slice(0, i + 1) : ''
  searchResults.value = []; searchKeyword.value = ''
}

// ---- 文件操作 ----

async function loadFiles() {
  if (!currentLib.value) return
  filesLoading.value = true
  try { files.value = await api.listFiles(currentLib.value.id, pathPrefix.value) }
  catch (e) { err.value = e.message }
  finally { filesLoading.value = false }
}
function selectLib(lib) { currentLib.value = lib; pathPrefix.value = ''; loadFiles() }
function goUp() {
  const p = pathPrefix.value.replace(/\/$/, '')
  const i = p.lastIndexOf('/')
  pathPrefix.value = i >= 0 ? p.slice(0, i) : ''
}
function enterDir(entry) {
  if (!entry?.is_dir) return
  pathPrefix.value = entry.path + '/'; searchResults.value = []; searchKeyword.value = ''
}
function toggleActionMenu(id) { openActionMenuId.value = openActionMenuId.value === id ? null : id }
function closeActionMenu() { openActionMenuId.value = null }

async function delFile(f) {
  if (!confirm('确定删除到回收站？')) return
  err.value = ''
  try { await api.deleteFile(f.id); loadFiles(); loadStorageStats(); showSuccess('删除成功') }
  catch (e) { err.value = e.message }
}
async function download(entryId, versionNo = null) {
  err.value = ''
  try { await api.downloadFile(entryId, versionNo); showSuccess('下载已开始') }
  catch (e) { err.value = e.message }
}
async function openVersions(f) {
  versionEntryId.value = f.id; versions.value = await api.listVersions(f.id); showVersions.value = true
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
  try { const url = await api.previewUrl(f.id); window.open(url, '_blank', 'noopener,noreferrer') }
  catch (e) { err.value = e.message || '预览失败' }
}
function closePreview() { previewUrl.value = ''; showPreview.value = false; previewText.value = ''; previewErr.value = '' }

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
async function upload() {
  const input = fileInput.value
  if (!input?.files?.length) { uploadErr.value = '请选择文件'; return }
  const path = uploadPath.value.trim() || input.files[0].name
  uploadErr.value = ''
  try {
    const fullPath = pathPrefix.value ? pathPrefix.value + path : path
    await api.uploadFile(currentLib.value.id, fullPath, input.files[0])
    showUpload.value = false; uploadPath.value = ''; input.value = ''
    loadFiles(); loadStorageStats(); showSuccess('上传成功')
  } catch (e) { uploadErr.value = e.message }
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
  if (ok) { loadFiles(); loadStorageStats(); showSuccess(fail ? `已上传 ${ok} 个，失败 ${fail} 个` : `已上传 ${ok} 个文件`) }
}
function onDragOver() { isDragging.value = true }
function onDragLeave() { isDragging.value = false }
async function doMkdir() {
  const path = (pathPrefix.value ? pathPrefix.value + mkdirPath.value : mkdirPath.value).replace(/\/+/g, '/')
  err.value = ''
  try {
    await api.createDir(currentLib.value.id, path)
    showMkdir.value = false; mkdirPath.value = ''; loadFiles(); loadStorageStats(); showSuccess('目录已创建')
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
async function removeShare(row) {
  if (!confirm(`确定取消对「${row.username}」的分享？`)) return
  try { await api.removeFileShare(row.file_entry_id, row.user_id); showSuccess('已取消分享'); await loadMyShares() }
  catch (e) { err.value = e.message }
}
async function loadReceivedShares() {
  if (tab.value !== 'shared' || sharedSubTab.value !== 'tome') return
  receivedSharesLoading.value = true
  try { receivedSharesList.value = await api.listSharesToMe() }
  catch (e) { err.value = e.message; receivedSharesList.value = [] }
  finally { receivedSharesLoading.value = false }
}
function openSharedLib(row) {
  const lib = libraries.value.find(l => l.id === row.library_id)
  if (lib) {
    tab.value = 'lib'; selectLib(lib)
    pathPrefix.value = row.file_path.includes('/') ? row.file_path.replace(/\/[^/]+$/, '') + '/' : ''
  } else { err.value = '未找到该资料库，请刷新页面后重试' }
}

// ---- 回收站 ----

async function loadTrash() {
  if (tab.value !== 'trash') return
  if (!trashLibId.value) { trashList.value = []; trashLoading.value = false; return }
  trashLoading.value = true
  try { trashList.value = await api.listTrash(Number(trashLibId.value)) }
  catch (e) { err.value = e.message }
  finally { trashLoading.value = false }
}
async function restore(entryId) {
  err.value = ''
  try { await api.restoreFile(entryId); loadTrash(); showSuccess('已恢复') }
  catch (e) { err.value = e.message }
}
async function permDelete(entryId) {
  if (!confirm('确定彻底删除？不可恢复。')) return
  err.value = ''
  try { await api.permanentDelete(entryId); loadTrash(); showSuccess('删除成功') }
  catch (e) { err.value = e.message }
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
  newLibName.value = ''; newLibDesc.value = ''; err.value = ''
  newLibDepartmentId.value = activeDeptId.value || null
  newLibMode.value = newLibDepartmentId.value ? 'dept' : 'self'
  newLibMembers.value = []
  if (['self_plus', 'dept_plus', 'members_only'].includes(newLibMode.value)) loadNewLibUsers()
  showNewLib.value = true
}
async function createLib() {
  err.value = ''
  const name = (newLibName.value || '').trim()
  if (!name) { err.value = '请填写资料库名称'; return }
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
  try {
    const created = await api.createLibrary(name, (newLibDesc.value || '').trim(), deptId, visibility, memberIds, newLibAllowDownload.value)
    if (created?.id != null) {
      libraries.value = [created, ...libraries.value.filter(l => l.id !== created.id)]
    } else {
      libraries.value = await api.listLibraries()
    }
    showNewLib.value = false; newLibName.value = ''; newLibDesc.value = ''; newLibDepartmentId.value = null
    newLibVisibility.value = 'private'; newLibMembers.value = []; newLibUsers.value = []
    if (deptId && activeDeptId.value === deptId) activeDeptLibraries.value = await api.listDepartmentLibraries(deptId)
    else if (!deptId) clearDeptView()
    showSuccess(deptId ? '部门资料库已创建' : '资料库已创建')
  } catch (e) { err.value = e.message }
}
async function delLib(lib) {
  if (!confirm('确定删除资料库「' + lib.name + '」？将同时删除库内所有文件（含回收站），不可恢复。')) return
  err.value = ''; errorMessage.value = ''
  try {
    await api.deleteLibrary(lib.id); libraries.value = await api.listLibraries()
    if (currentLib.value?.id === lib.id) currentLib.value = null
    loadStorageStats(); showSuccess('删除成功')
  } catch (e) { err.value = e.message; showError(e.message) }
}
async function openEditLib(lib) {
  editLibId.value = lib.id; editLibName.value = lib.name; editLibDesc.value = lib.description || ''
  const vis = lib.visibility || 'private'
  const hasMembers = (lib.member_count || 0) > 0
  const isDeptLib = !!lib.department_id
  if (isDeptLib) editLibMode.value = hasMembers ? 'dept_plus' : 'dept'
  else if (vis === 'public') editLibMode.value = 'public'
  else editLibMode.value = hasMembers ? 'self_plus' : 'self'
  editLibUsers.value = []; editLibMembers.value = []; editLibInitialMembers.value = []
  if (['self_plus', 'dept_plus', 'members_only'].includes(editLibMode.value)) await loadEditLibUsersAndMembers(lib.id)
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
    const mode = editLibMode.value || 'self'
    const isDeptLib = !!currentLib.value?.department_id
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
    await api.updateLibrary(editLibId.value, editLibName.value.trim(), editLibDesc.value.trim(), visibility)
    libraries.value = await api.listLibraries()
    if (currentLib.value?.id === editLibId.value) currentLib.value = libraries.value.find(l => l.id === editLibId.value)
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
function openDeptLib(lib) { clearDeptView(); selectLib(lib) }
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
    await api.createUser(newUserEmail.value.trim(), newUserUsername.value.trim(), newUserPassword.value, isSuper, deptId)
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
.app-content { flex: 1; min-height: 0; padding: 24px; overflow: auto; }
.app-content .card { background: #fff; }
.empty-hint { color: var(--text-secondary); font-size: 14px; margin: 12px 0; }
.modal {
  position: fixed; inset: 0; background: rgba(0,0,0,0.45);
  display: flex; align-items: center; justify-content: center; z-index: 10;
}
.modal .card { max-width: 440px; width: 90%; max-height: 90vh; overflow: auto; background: #fff; }
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
.add-member-row { display: flex; gap: 10px; align-items: center; margin-bottom: 16px; }
.members-table { width: 100%; border-collapse: collapse; margin-top: 12px; }
.members-table th, .members-table td { padding: 8px 12px; text-align: left; border-bottom: 1px solid var(--border); }
.badge { padding: 2px 8px; border-radius: 4px; font-size: 12px; }
.badge-user { background: #f3f4f6; color: var(--text-secondary); }
.btn-small { font-size: 12px; padding: 4px 10px; }
.admin-select { padding: 8px 12px; border: 1px solid var(--border); border-radius: 8px; font-size: 14px; min-width: 120px; }
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
.user-modal-card { max-width: 520px; }
.user-modal-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px 16px; margin-top: 12px; }
@media (max-width: 640px) { .user-modal-grid { grid-template-columns: 1fr; } }
</style>
