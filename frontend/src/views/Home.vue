<template>
  <div class="app-layout">
    <!-- 左侧深色导航 -->
    <aside class="app-sidebar">
      <!-- Logo -->
      <div class="sidebar-logo">
        <Icons name="drive" class="logo-icon" />
        <span class="logo-text">文件共享和知识管理平台</span>
      </div>
      <!-- 存储空间 -->
      <div class="sidebar-storage">
        <div class="storage-label">存储空间</div>
        <div class="storage-value">
          <span class="storage-used">{{ storageStats?.used_display || '0 B' }}</span>
          <span class="storage-total">/ {{ storageStats?.total_display || '500 GB' }}</span>
        </div>
        <div class="storage-bar">
          <div class="storage-fill" :style="{ width: Math.min((storageStats?.percent || 0), 100) + '%' }"></div>
        </div>
      </div>
      <!-- 主导航 -->
      <nav class="sidebar-nav">
        <a :class="['nav-item', { active: tab === 'lib' }]" href="#" @click.prevent="tab = 'lib'; err = ''">
          <Icons name="folder" class="nav-icon" />
          <span>我的资料库</span>
        </a>
        <a :class="['nav-item', { active: tab === 'trash' }]" href="#" @click.prevent="tab = 'trash'; err = ''; loadTrash()">
          <Icons name="trash" class="nav-icon" />
          <span>回收站</span>
        </a>
      </nav>
      <div class="sidebar-spacer"></div>
      <!-- 底部导航 -->
      <div class="sidebar-bottom">
        <button v-if="me?.is_superuser" :class="['nav-item', { active: tab === 'sys' }]" @click="tab = 'sys'; subTab = 'users'; err = ''; loadUsers(); loadAudit()">
          <Icons name="settings" class="nav-icon" />
          <span>系统管理</span>
        </button>
      </div>
      <!-- 用户信息 -->
      <div class="sidebar-user">
        <div class="user-avatar">{{ me?.username?.[0] || '?' }}</div>
        <div class="user-info">
          <span class="user-name">{{ me?.username }}</span>
          <div class="user-actions">
            <button @click="showChangePw = true" class="user-btn">修改密码</button>
            <button @click="logout" class="user-btn">退出</button>
          </div>
        </div>
      </div>
    </aside>

    <!-- 右侧主区域 -->
    <div class="app-main">
      <!-- 顶部工具栏 -->
      <header class="app-topbar">
        <div class="search-box">
          <Icons name="search" class="search-icon" />
          <input v-model="searchKeyword" type="text" placeholder="搜索文件、文件夹..." class="search-input" @keyup.enter="doSearch" />
        </div>
        <div class="topbar-actions">
          <template v-if="tab === 'lib'">
            <button v-if="!currentLib" class="btn-primary" @click="showNewLib = true">+ 新建资料库</button>
          </template>
        </div>
      </header>

      <!-- 成功/失败提示框：固定定位，删除后自动刷新 -->
      <Transition name="toast">
        <div v-if="successMessage" class="success-toast">{{ successMessage }}</div>
      </Transition>
      <Transition name="toast">
        <div v-if="errorMessage" class="error-toast">{{ errorMessage }}</div>
      </Transition>

      <!-- 资料库：库列表 或 文件列表 -->
      <div v-if="tab === 'lib'" class="app-content">
      <div class="lib-grid-wrap" v-if="!currentLib">
        <div class="lib-header">
          <h3>我的资料库</h3>
        </div>
        <div class="lib-grid" v-if="libraries.length">
          <div v-for="lib in libraries" :key="lib.id" class="lib-card" @click="selectLib(lib)">
            <div class="lib-card-icon"><Icons name="folder" /></div>
            <div class="lib-card-name">{{ lib.name }}</div>
            <span v-if="!lib.is_owner" class="lib-card-badge">共享给我</span>
            <p v-if="lib.description" class="lib-card-desc">{{ lib.description }}</p>
            <div class="lib-card-actions" @click.stop>
              <button class="btn-small" @click="openEditLib(lib)" title="编辑">编辑</button>
              <button class="btn-small danger" @click="delLib(lib)" title="删除">删除</button>
            </div>
          </div>
        </div>
        <p v-else class="empty-hint">暂无资料库，请点击「新建资料库」。</p>
      </div>
      <div class="file-main card" v-if="currentLib"
  :class="{ 'drop-zone-active': isDragging }"
  @dragover.prevent="isDragging = true"
  @dragleave="isDragging = false"
  @drop.prevent="onFileDrop">
        <div class="breadcrumb-bar">
          <a href="#" @click.prevent="currentLib = null; pathPrefix = ''" class="breadcrumb-link">文件库</a>
          <template v-for="(seg, i) in breadcrumbSegments" :key="i">
            <span class="breadcrumb-sep">/</span>
            <a v-if="seg.path !== undefined" href="#" @click.prevent="pathPrefix = seg.path" class="breadcrumb-link">{{ seg.label }}</a>
            <span v-else class="breadcrumb-current">{{ seg.label }}</span>
          </template>
          <div class="toolbar-right">
            <button v-if="currentLib?.is_writeable" @click="showMkdir = true" class="btn-outline">新建目录</button>
            <button v-if="currentLib?.is_writeable" class="primary" @click="showUpload = true; uploadErr = ''">上传文件</button>
          </div>
        </div>
        <p v-if="filesLoading" class="empty-hint">加载中...</p>
        <div v-else-if="searchResults.length" class="search-results-section">
          <div class="search-results-header">
            <span>搜索「{{ searchKeyword }}」共 {{ searchResults.length }} 项</span>
            <button class="btn-small" @click="searchResults = []; searchKeyword = ''">清除</button>
          </div>
          <div class="file-grid-header">
            <span>名称</span>
            <span>修改时间</span>
            <span>大小</span>
            <span>操作</span>
          </div>
          <div v-for="r in searchResults" :key="r.id" class="file-item file-item-row">
            <div class="file-item-name">
              <a v-if="r.is_dir" href="#" @click.prevent="goToPath(r.path)" class="file-item-link"><Icons name="folder" class="file-icon" />{{ r.path }}/</a>
              <a v-else href="#" @click.prevent="onFileClick(r)" class="file-item-link"><Icons name="file" class="file-icon" />{{ r.path }}</a>
            </div>
            <span class="file-meta">{{ formatDate(r.updated_at) }}</span>
            <span class="file-meta">{{ r.is_dir ? '-' : formatSize(r.size) }}</span>
            <span class="file-actions-wrap">
              <button type="button" class="actions-trigger" @click.stop="toggleActionMenu('s-' + r.id)" title="操作">⋮</button>
              <div v-if="openActionMenuId === 's-' + r.id" class="action-dropdown" @click.stop>
                <button v-if="!r.is_dir && (r.can_download !== false)" class="btn-small" @click="download(r.id); closeActionMenu()">下载</button>
                <button v-if="currentLib?.is_owner" class="btn-small" @click="openShare(r); closeActionMenu()">分享</button>
                <button v-if="currentLib?.is_writeable" class="btn-small" @click="openRename(r); closeActionMenu()">重命名</button>
              </div>
            </span>
          </div>
        </div>
        <div v-else class="file-grid">
          <div class="file-grid-header">
            <span>名称</span>
            <span>修改时间</span>
            <span>大小</span>
            <span>操作</span>
          </div>
          <div v-if="pathPrefix" class="file-item file-item-row">
            <a href="#" @click.prevent="goUp" class="file-item-link"><Icons name="folder" class="file-icon" /> .. 上一级</a>
            <span class="file-meta">-</span>
            <span class="file-meta">-</span>
            <span class="file-actions-wrap"></span>
          </div>
          <div v-for="f in files" :key="f.id" class="file-item file-item-row">
            <div class="file-item-name">
              <a v-if="f.is_dir" href="#" @click.prevent="pathPrefix = f.path + '/'" class="file-item-link"><Icons name="folder" class="file-icon" />{{ f.path.split('/').pop() }}/</a>
              <a v-else href="#" @click.prevent="onFileClick(f)" class="file-item-link"><Icons name="file" class="file-icon" />{{ f.path.split('/').pop() }}</a>
            </div>
            <span class="file-meta">{{ formatDate(f.updated_at) }}</span>
            <span class="file-meta">{{ f.is_dir ? '-' : formatSize(f.size) }}</span>
            <span class="file-actions-wrap">
              <button type="button" class="actions-trigger" @click.stop="toggleActionMenu('f-' + f.id)" title="操作">⋮</button>
              <div v-if="openActionMenuId === 'f-' + f.id" class="action-dropdown" @click.stop>
                <template v-if="!f.is_dir">
                  <button v-if="f.can_download !== false" class="btn-small" @click="download(f.id); closeActionMenu()">下载</button>
                  <button class="btn-small" @click="openVersions(f); closeActionMenu()">版本</button>
                  <button v-if="currentLib?.is_owner" class="btn-small" @click="openShare(f); closeActionMenu()">分享</button>
                </template>
                <button v-if="currentLib?.is_writeable" class="btn-small" @click="openRename(f); closeActionMenu()">重命名</button>
                <button v-if="currentLib?.is_writeable" class="btn-small danger" @click="delFile(f); closeActionMenu()">删除</button>
              </div>
            </span>
          </div>
        </div>
        </div>
        <p v-if="currentLib && !filesLoading && files.length === 0 && !searchResults.length" class="empty-hint">当前目录为空，可上传文件或新建目录。</p>
      </div>

    <!-- 回收站 -->
    <div v-if="tab === 'trash'" class="app-content">
      <div class="card" style="max-width: 800px;">
        <h3>回收站</h3>
        <p>
          <select v-model="trashLibId" @change="loadTrash" style="min-width: 200px;">
            <option value="">选择资料库</option>
            <option v-for="lib in libraries" :key="lib.id" :value="lib.id">{{ lib.name }}</option>
          </select>
        </p>
        <p v-if="trashLoading" class="empty-hint">加载中...</p>
        <table v-else-if="trashList.length">
          <thead><tr><th>路径</th><th>删除时间</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="f in trashList" :key="f.id">
              <td>{{ f.path }}</td>
              <td>{{ formatDate(f.deleted_at) }}</td>
              <td>
                <button @click="restore(f.id)">恢复</button>
                <button class="danger" @click="permDelete(f.id)">彻底删除</button>
              </td>
            </tr>
          </tbody>
        </table>
        <p v-else-if="trashLibId">该库回收站为空</p>
        <p v-else class="empty-hint">请选择资料库查看回收站。</p>
      </div>
    </div>

    <!-- 系统管理：团队管理 + 审计日志 -->
    <div v-if="tab === 'sys'" class="app-content sys-content">
      <div v-if="!me?.is_superuser" class="users-permission-card card">
        <p class="permission-hint">需要管理员权限，请使用管理员账号登录。</p>
      </div>
      <template v-else>
      <nav class="sys-subtabs">
        <button :class="['subtab-item', { active: subTab === 'users' }]" @click="subTab = 'users'; loadUsers()">团队管理</button>
        <button :class="['subtab-item', { active: subTab === 'audit' }]" @click="subTab = 'audit'; loadAudit()">审计日志</button>
      </nav>
      <!-- 团队管理 -->
      <div v-if="subTab === 'users'" class="users-page">
        <div class="users-list-header-row">
          <h2 class="page-title">团队管理</h2>
          <button class="primary" @click="showCreateUser = true">创建用户</button>
        </div>
        <div class="users-list card">
          <div class="users-list-header">
            <span class="users-count" v-if="userList.length">共 {{ userList.length }} 人</span>
          </div>
          <div class="users-table-wrap" v-if="userList.length">
            <table class="users-table">
              <colgroup>
                <col style="width: 140px" />
                <col style="width: 180px" />
                <col style="width: 80px" />
                <col style="width: 80px" />
                <col style="width: 160px" />
                <col style="width: 150px" />
              </colgroup>
              <thead><tr><th>用户名</th><th>邮箱</th><th>管理员</th><th>状态</th><th>创建时间</th><th>操作</th></tr></thead>
              <tbody>
                <tr v-for="u in userList" :key="u.id">
                  <td class="col-username"><span class="user-avatar-sm">{{ u.username?.[0] || '?' }}</span><span class="username-text">{{ u.username }}</span></td>
                  <td class="col-email">{{ u.email || '-' }}</td>
                  <td><span :class="['badge', u.is_superuser ? 'badge-admin' : 'badge-user']">{{ u.is_superuser ? '是' : '否' }}</span></td>
                  <td class="col-status"><span :class="['status', u.is_active ? 'status-ok' : 'status-disabled']">{{ u.is_active ? '正常' : '禁用' }}</span></td>
                  <td class="col-date">{{ formatDate(u.created_at) }}</td>
                  <td class="col-actions">
                    <button v-if="u.id !== me?.id" class="btn-small" :class="{ danger: !u.is_active }" @click="toggleUserActive(u)">{{ u.is_active ? '禁用' : '启用' }}</button>
                    <button class="btn-small btn-link" @click="resetUserPassword(u)" title="重置密码">重置密码</button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <p v-else class="empty-hint">暂无用户</p>
        </div>
      </div>
      <!-- 审计日志 -->
      <div v-if="subTab === 'audit'" class="audit-page">
        <div class="card">
          <h3>审计日志</h3>
          <div class="audit-filters">
            <input v-model="auditUsername" placeholder="用户名" style="width: 100px;" />
            <input v-model="auditAction" placeholder="操作类型" style="width: 100px;" />
            <button class="primary" @click="loadAudit">查询</button>
          </div>
          <div class="audit-date-row">
            <span class="audit-date-label">开始日期</span>
            <input v-model="auditStartDate" type="text" placeholder="YYYY-MM-DD" class="audit-date-input" maxlength="10" />
            <span class="audit-date-label">结束日期</span>
            <input v-model="auditEndDate" type="text" placeholder="YYYY-MM-DD" class="audit-date-input" maxlength="10" />
          </div>
          <table>
          <thead><tr><th>时间</th><th>用户</th><th>操作</th><th>资源</th><th>详情</th></tr></thead>
          <tbody>
            <tr v-for="log in auditList" :key="log.id">
              <td>{{ formatDate(log.created_at) }}</td>
              <td>{{ log.username || '-' }}</td>
              <td>{{ log.action }}</td>
              <td>{{ log.resource_type }} {{ log.resource_id }}</td>
              <td>{{ log.detail || '-' }}</td>
            </tr>
          </tbody>
        </table>
        <p v-if="auditList.length === 0" class="empty-hint">暂无审计记录，或调整筛选条件后查询。</p>
        </div>
      </div>
      </template>
    </div>

    </div><!-- /app-main -->

    <!-- 新建资料库 -->
    <div v-if="showNewLib" class="modal">
      <div class="card">
        <h3>新建资料库</h3>
        <input v-model="newLibName" placeholder="名称" style="width:100%; margin-bottom:8px;" />
        <input v-model="newLibDesc" placeholder="描述（选填）" style="width:100%; margin-bottom:8px;" />
        <p v-if="err" class="text-danger">{{ err }}</p>
        <div class="modal-actions">
          <button class="primary" @click="createLib">确定</button>
          <button @click="showNewLib = false">取消</button>
        </div>
      </div>
    </div>

    <!-- 上传 -->
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

    <!-- 预览弹窗 -->
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

    <!-- 版本列表 -->
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

    <!-- 创建用户 -->
    <div v-if="showCreateUser" class="modal">
      <div class="card">
        <h3>创建用户</h3>
        <div class="form-group">
          <label>邮箱（用于登录） <span class="label-opt">必填</span></label>
          <input v-model="newUserEmail" type="email" placeholder="如 user@example.com" />
        </div>
        <div class="form-group">
          <label>用户名（仅用于显示） <span class="label-opt">必填</span></label>
          <input v-model="newUserUsername" placeholder="如 张三" />
        </div>
        <div class="form-group">
          <label>密码（8位以上，含大小写、数字、特殊字符） <span class="label-opt">必填</span></label>
          <input v-model="newUserPassword" type="password" placeholder="请输入强密码" />
        </div>
        <label class="form-check">
          <input type="checkbox" v-model="newUserIsSuperuser" /> 设为管理员 <span class="label-opt">选填</span>
        </label>
        <p v-if="err" class="text-danger">{{ err }}</p>
        <div class="modal-actions">
          <button class="primary" @click="doCreateUserModal">确定</button>
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
import * as api from '../api/client'
import Icons from '../components/Icons.vue'

const me = ref(null)
const tab = ref('lib')
const subTab = ref('users')
const libraries = ref([])
const currentLib = ref(null)
const pathPrefix = ref('')
const files = ref([])
const filesLoading = ref(false)
const successMessage = ref('')
const errorMessage = ref('')
const showNewLib = ref(false)
const newLibName = ref('')
const newLibDesc = ref('')
const showUpload = ref(false)
const uploadPath = ref('')
const selectedFile = ref(null)
const showMkdir = ref(false)
const mkdirPath = ref('')
const err = ref('')
const trashLib = ref(null)
const trashLibId = ref('')
const trashList = ref([])
const trashLoading = ref(false)
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
const previewType = ref('') // image | pdf | text
const previewText = ref('')
const previewErr = ref('')
const previewLoading = ref(false)
const shareList = ref([])
const shareAddableUsers = ref([])
const shareAddUserId = ref('')
const sharePermission = ref('read')

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

function logout() { api.logout() }

function formatDate(s) {
  if (!s) return '-'
  const d = new Date(s)
  return d.toLocaleString('zh-CN')
}

function formatSize(bytes) {
  if (bytes == null || bytes === undefined) return '-'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

function showSuccess(msg) {
  successMessage.value = msg
  errorMessage.value = ''
  err.value = ''
  setTimeout(() => { successMessage.value = '' }, 3000)
}
function showError(msg) {
  errorMessage.value = msg
  setTimeout(() => { errorMessage.value = '' }, 4000)
}

onMounted(async () => {
  me.value = await api.getMe()
  libraries.value = await api.listLibraries()
  loadStorageStats()
})

function selectLib(lib) {
  currentLib.value = lib
  pathPrefix.value = ''
  loadFiles()
}
function openShare(f) {
  if (f.is_dir) return
  shareFile.value = f
  showShare.value = true
  shareAddUserId.value = ''
  sharePermission.value = 'read'
  err.value = ''
  loadShareList()
  loadShareAddableUsers()
}
function closeShare() {
  showShare.value = false
  shareFile.value = null
  shareList.value = []
  shareAddableUsers.value = []
}
async function loadShareList() {
  if (!shareFile.value) return
  try {
    shareList.value = await api.listFileShares(shareFile.value.id)
  } catch (e) {
    err.value = e.message
  }
}
async function loadShareAddableUsers() {
  if (!shareFile.value) return
  try {
    shareAddableUsers.value = await api.listFileShareAddableUsers(shareFile.value.id)
  } catch (e) {
    shareAddableUsers.value = []
  }
}
async function doAddShare() {
  const uid = shareAddUserId.value
  if (!uid || !shareFile.value) return
  err.value = ''
  try {
    await api.addFileShare(shareFile.value.id, Number(uid), sharePermission.value)
    loadShareList()
    loadShareAddableUsers()
    shareAddUserId.value = ''
    showSuccess('已添加分享')
  } catch (e) {
    err.value = e.message
  }
}
async function doRemoveShare(s) {
  if (!confirm('确定移除此分享？')) return
  if (!shareFile.value) return
  err.value = ''
  try {
    await api.removeFileShare(shareFile.value.id, s.user_id)
    loadShareList()
    loadShareAddableUsers()
    showSuccess('已移除分享')
  } catch (e) {
    err.value = e.message
  }
}

watch([currentLib, pathPrefix], () => { if (currentLib.value) loadFiles(); searchResults.value = [] })
watch(openActionMenuId, (id) => {
  if (!id) return
  const close = () => { openActionMenuId.value = null }
  const onDocClick = () => { close(); document.removeEventListener('click', onDocClick) }
  setTimeout(() => document.addEventListener('click', onDocClick), 0)
})

async function loadStorageStats() {
  try {
    storageStats.value = await api.getStorageStats()
  } catch (e) { storageStats.value = null }
}
async function doSearch() {
  if (!currentLib.value || !searchKeyword.value?.trim()) {
    searchResults.value = []
    return
  }
  try {
    searchResults.value = await api.searchFiles(currentLib.value.id, searchKeyword.value.trim())
  } catch (e) {
    err.value = e.message
    searchResults.value = []
  }
}
function goToPath(path) {
  const dir = path.endsWith('/') ? path.slice(0, -1) : path
  const i = dir.lastIndexOf('/')
  pathPrefix.value = i >= 0 ? dir.slice(0, i + 1) : ''
  searchResults.value = []
  searchKeyword.value = ''
}
function openRename(f) {
  renameEntry.value = f
  renameNewPath.value = f.path
  showRename.value = true
  err.value = ''
}
function closeRename() {
  showRename.value = false
  renameEntry.value = null
  renameNewPath.value = ''
  err.value = ''
}
async function doRename() {
  if (!renameEntry.value) return
  const newPath = renameNewPath.value?.trim()
  if (!newPath) {
    err.value = '请输入新路径'
    return
  }
  err.value = ''
  try {
    await api.renameFile(renameEntry.value.id, newPath)
    loadFiles()
    if (searchResults.value.length) doSearch()
    closeRename()
    showSuccess('重命名成功')
  } catch (e) {
    err.value = e.message
  }
}
async function loadFiles() {
  if (!currentLib.value) return
  filesLoading.value = true
  try {
    files.value = await api.listFiles(currentLib.value.id, pathPrefix.value)
  } catch (e) {
    err.value = e.message
  } finally {
    filesLoading.value = false
  }
}

function goUp() {
  const p = pathPrefix.value.replace(/\/$/, '')
  const i = p.lastIndexOf('/')
  pathPrefix.value = i >= 0 ? p.slice(0, i) : ''
}

async function createLib() {
  err.value = ''
  const name = (newLibName.value || '').trim()
  if (!name) {
    err.value = '请填写资料库名称'
    return
  }
  try {
    await api.createLibrary(name, (newLibDesc.value || '').trim())
    libraries.value = await api.listLibraries()
    showNewLib.value = false
    newLibName.value = ''
    newLibDesc.value = ''
    showSuccess('资料库已创建')
  } catch (e) {
    err.value = e.message
  }
}

async function loadTrash() {
  if (tab.value !== 'trash') return
  if (!trashLibId.value) {
    trashList.value = []
    trashLoading.value = false
    return
  }
  trashLoading.value = true
  try {
    trashList.value = await api.listTrash(Number(trashLibId.value))
  } catch (e) {
    err.value = e.message
  } finally {
    trashLoading.value = false
  }
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
  } catch (e) {
    err.value = e.message
  }
}

async function loadUsers() {
  try {
    userList.value = await api.listUsers()
  } catch (e) {
    err.value = e.message
  }
}

async function toggleUserActive(u) {
  if (u.id === me.value?.id) return
  const action = u.is_active ? '禁用' : '启用'
  if (!confirm('确定' + action + '用户「' + u.username + '」？')) return
  err.value = ''
  try {
    await api.updateUser(u.id, { is_active: !u.is_active })
    await loadUsers()
  } catch (e) {
    err.value = e.message
  }
}

async function resetUserPassword(u) {
  const newPw = prompt('请输入新密码（8位以上，含大小写、数字、特殊字符）：', '')
  if (newPw == null || newPw === '') return
  const pwdErr = _checkStrongPassword(newPw)
  if (pwdErr) {
    err.value = pwdErr
    return
  }
  err.value = ''
  try {
    await api.updateUser(u.id, { new_password: newPw })
    showSuccess('已重置「' + u.username + '」的密码')
  } catch (e) {
    err.value = e.message
  }
}

function openEditLib(lib) {
  editLibId.value = lib.id
  editLibName.value = lib.name
  editLibDesc.value = lib.description || ''
  showEditLib.value = true
  err.value = ''
}

async function saveEditLib() {
  err.value = ''
  try {
    await api.updateLibrary(editLibId.value, editLibName.value.trim(), editLibDesc.value.trim())
    libraries.value = await api.listLibraries()
    if (currentLib.value?.id === editLibId.value) currentLib.value = libraries.value.find(l => l.id === editLibId.value)
    showEditLib.value = false
    showSuccess('资料库已更新')
  } catch (e) {
    err.value = e.message
  }
}

async function delLib(lib) {
  if (!confirm('确定删除资料库「' + lib.name + '」？将同时删除库内所有文件（含回收站），不可恢复。')) return
  err.value = ''
  errorMessage.value = ''
  try {
    await api.deleteLibrary(lib.id)
    libraries.value = await api.listLibraries()
    if (currentLib.value?.id === lib.id) currentLib.value = null
    loadStorageStats()
    showSuccess('删除成功')
  } catch (e) {
    err.value = e.message
    showError(e.message)
  }
}

async function doChangePassword() {
  err.value = ''
  if (!newPassword.value) {
    err.value = '请输入新密码'
    return
  }
  const pwdErr = _checkStrongPassword(newPassword.value)
  if (pwdErr) {
    err.value = pwdErr
    return
  }
  if (newPassword.value !== newPassword2.value) {
    err.value = '两次输入的新密码不一致'
    return
  }
  try {
    await api.changePassword(oldPassword.value, newPassword.value)
    showChangePw.value = false
    oldPassword.value = ''
    newPassword.value = ''
    newPassword2.value = ''
    showSuccess('密码已修改')
  } catch (e) {
    err.value = e.message
  }
}

function closeCreateUser() {
  showCreateUser.value = false
  newUserEmail.value = ''
  newUserUsername.value = ''
  newUserPassword.value = ''
  newUserIsSuperuser.value = false
  err.value = ''
}
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
  if (!newUserEmail.value.trim()) {
    err.value = '请填写邮箱（用于登录）'
    return
  }
  if (!newUserUsername.value.trim()) {
    err.value = '请填写用户名（用于显示）'
    return
  }
  if (!newUserPassword.value) {
    err.value = '请填写密码'
    return
  }
  const pwdErr = _checkStrongPassword(newUserPassword.value)
  if (pwdErr) {
    err.value = pwdErr
    return
  }
  try {
    await api.createUser(newUserEmail.value.trim(), newUserUsername.value.trim(), newUserPassword.value, newUserIsSuperuser.value)
    showSuccess('用户已创建：' + newUserUsername.value)
    closeCreateUser()
    loadUsers()
  } catch (e) {
    err.value = e.message
  }
}

async function download(entryId, versionNo = null) {
  err.value = ''
  try {
    await api.downloadFile(entryId, versionNo)
    showSuccess('下载已开始')
  } catch (e) {
    err.value = e.message
  }
}

function canPreviewFile(path) {
  return path && api.canPreview(path)
}
function onFileClick(file) {
  if (file.is_dir) return
  openPreview(file)
}
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
  if (!previewTypeOf(f.path)) {
    err.value = '该文件类型暂不支持预览'
    return
  }
  try {
    const url = await api.previewUrl(f.id)
    window.open(url, '_blank', 'noopener,noreferrer')
  } catch (e) {
    err.value = e.message || '预览失败'
  }
}
function closePreview() {
  previewUrl.value = ''
  showPreview.value = false
  previewText.value = ''
  previewErr.value = ''
}
function toggleActionMenu(id) {
  openActionMenuId.value = openActionMenuId.value === id ? null : id
}
function closeActionMenu() {
  openActionMenuId.value = null
}

async function openVersions(f) {
  versionEntryId.value = f.id
  versions.value = await api.listVersions(f.id)
  showVersions.value = true
}

async function delFile(f) {
  if (!confirm('确定删除到回收站？')) return
  err.value = ''
  try {
    await api.deleteFile(f.id)
    loadFiles()
    loadStorageStats()
    showSuccess('删除成功')
  } catch (e) {
    err.value = e.message
  }
}

function onFileSelect() { uploadErr.value = '' }
async function onFileDrop(e) {
  isDragging.value = false
  if (!currentLib.value || !currentLib.value.is_writeable) return
  const items = e.dataTransfer?.files
  if (!items?.length) return
  uploadErr.value = ''
  let ok = 0
  let fail = 0
  for (let i = 0; i < items.length; i++) {
    const file = items[i]
    if (file?.name) {
      try {
        const fullPath = pathPrefix.value ? pathPrefix.value + file.name : file.name
        await api.uploadFile(currentLib.value.id, fullPath, file)
        ok++
      } catch (err) {
        uploadErr.value = err.message
        fail++
      }
    }
  }
  if (ok) {
    loadFiles()
    loadStorageStats()
    showSuccess(fail ? `已上传 ${ok} 个，失败 ${fail} 个` : `已上传 ${ok} 个文件`)
  }
}
const uploadErr = ref('')
async function upload() {
  const input = fileInput.value
  if (!input?.files?.length) { uploadErr.value = '请选择文件'; return }
  const path = uploadPath.value.trim() || input.files[0].name
  uploadErr.value = ''
  try {
    const fullPath = pathPrefix.value ? pathPrefix.value + path : path
    await api.uploadFile(currentLib.value.id, fullPath, input.files[0])
    showUpload.value = false
    uploadPath.value = ''
    input.value = ''
    loadFiles()
    loadStorageStats()
    showSuccess('上传成功')
  } catch (e) {
    uploadErr.value = e.message
    console.error('上传失败:', e)
  }
}

async function doMkdir() {
  const path = (pathPrefix.value ? pathPrefix.value + mkdirPath.value : mkdirPath.value).replace(/\/+/g, '/')
  err.value = ''
  try {
    await api.createDir(currentLib.value.id, path)
    showMkdir.value = false
    mkdirPath.value = ''
    loadFiles()
    loadStorageStats()
    showSuccess('目录已创建')
  } catch (e) {
    err.value = e.message
  }
}

async function restore(entryId) {
  err.value = ''
  try {
    await api.restoreFile(entryId)
    loadTrash()
    showSuccess('已恢复')
  } catch (e) {
    err.value = e.message
  }
}

async function permDelete(entryId) {
  if (!confirm('确定彻底删除？不可恢复。')) return
  err.value = ''
  try {
    await api.permanentDelete(entryId)
    loadTrash()
    showSuccess('删除成功')
  } catch (e) {
    err.value = e.message
  }
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
/* 左侧深色导航 - 固定高度，不随主内容滚动 */
.app-sidebar {
  width: var(--sidebar-width);
  height: 100vh;
  background: var(--sidebar-bg);
  color: var(--sidebar-text);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  overflow: hidden;
}
.sidebar-logo {
  height: 56px;
  display: flex;
  align-items: center;
  padding: 0 24px;
  border-bottom: 1px solid rgba(75,85,99,0.5);
  flex-shrink: 0;
}
.logo-icon { width: 28px; height: 28px; font-size: 28px; color: var(--sidebar-accent); }
.logo-text { margin-left: 12px; font-size: 14px; font-weight: 600; line-height: 1.3; }
.sidebar-storage {
  padding: 16px 24px;
  border-bottom: 1px solid rgba(75,85,99,0.5);
  flex-shrink: 0;
}
.storage-label { font-size: 12px; color: rgba(156,163,175); margin-bottom: 6px; }
.storage-value { display: flex; align-items: baseline; gap: 6px; margin-bottom: 6px; }
.storage-used { font-size: 20px; font-weight: 600; }
.storage-total { font-size: 12px; color: rgba(156,163,175); }
.storage-bar {
  width: 100%;
  height: 6px;
  background: rgba(75,85,99);
  border-radius: 999px;
  overflow: hidden;
}
.storage-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--sidebar-accent), #357abd);
  border-radius: 999px;
  transition: width 0.3s;
}
.sidebar-spacer { flex: 1; min-height: 0; }
.sidebar-nav {
  padding: 12px;
  border-bottom: 1px solid rgba(75,85,99,0.5);
  flex-shrink: 0;
}
.sidebar-nav .nav-item { margin-bottom: 2px; }
.sidebar-nav .nav-item:last-child { margin-bottom: 0; }
.sidebar-bottom {
  padding: 12px;
  border-top: 1px solid rgba(75,85,99,0.5);
  flex-shrink: 0;
}
.sidebar-bottom .nav-item { margin-bottom: 2px; }
.sidebar-bottom .nav-item:last-child { margin-bottom: 0; }
.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
  color: rgba(209,213,219);
  text-decoration: none;
  font-size: 14px;
  font-weight: 500;
  border: none;
  background: none;
  width: 100%;
  text-align: left;
  cursor: pointer;
  border-radius: 8px;
  transition: background 0.2s, color 0.2s;
}
.nav-item:hover { background: rgba(75,85,99,0.5); color: #fff; }
.nav-item.active { background: var(--sidebar-accent); color: #fff; }
.nav-icon { width: 16px; height: 16px; font-size: 16px; flex-shrink: 0; opacity: 0.9; }
.sidebar-user {
  padding: 12px 24px;
  border-top: 1px solid rgba(75,85,99,0.5);
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}
.user-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--sidebar-accent), #357abd);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
  flex-shrink: 0;
}
.user-info { flex: 1; min-width: 0; }
.user-name { display: block; font-size: 14px; font-weight: 500; }
.user-actions { display: flex; gap: 8px; margin-top: 4px; }
.user-btn {
  background: none;
  border: none;
  color: var(--sidebar-text-muted);
  padding: 0;
  font-size: 12px;
  cursor: pointer;
}
.user-btn:hover { color: var(--sidebar-text); text-decoration: underline; }

/* 右侧主区 */
.app-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  background: var(--bg-page);
}
.app-topbar {
  height: var(--header-height);
  background: #fff;
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  gap: 20px;
  padding: 0 24px;
}
.search-box {
  flex: 1;
  max-width: 480px;
  display: flex;
  align-items: center;
  gap: 8px;
  background: #f5f6f8;
  border-radius: var(--radius);
  padding: 0 14px;
  height: 40px;
}
.search-icon { width: 18px; height: 18px; font-size: 18px; color: #999; flex-shrink: 0; }
.search-input {
  flex: 1;
  border: none;
  background: transparent;
  font-size: 14px;
  padding: 0;
}
.search-input:focus { outline: none; }
.topbar-actions { margin-left: auto; }
.btn-primary {
  background: var(--primary);
  color: #fff;
  border: none;
  padding: 8px 16px;
  border-radius: var(--radius);
  font-size: 14px;
  cursor: pointer;
}
.btn-primary:hover { background: var(--primary-dark); }
.btn-outline { margin-right: 8px; }

.success-toast {
  position: fixed;
  top: 20px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 9999;
  background: var(--success-bg, #e8f5e9);
  color: var(--success, #2e7d32);
  padding: 12px 24px;
  border-radius: var(--radius, 8px);
  font-size: 14px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.15);
}
.toast-enter-active { animation: toast-in 0.3s ease-out; }
.toast-leave-active { animation: toast-out 0.3s ease-in; }
@keyframes toast-in {
  from { opacity: 0; transform: translate(-50%, -20px); }
  to { opacity: 1; transform: translate(-50%, 0); }
}
@keyframes toast-out {
  from { opacity: 1; transform: translate(-50%, 0); }
  to { opacity: 0; transform: translate(-50%, -20px); }
}
.error-toast {
  position: fixed;
  top: 20px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 9999;
  background: #ffebee;
  color: #c62828;
  padding: 12px 24px;
  border-radius: var(--radius, 8px);
  font-size: 14px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.15);
}
.text-danger { color: var(--danger); font-size: 14px; margin: 0 0 8px 0; }
.text-success { color: var(--success); font-size: 14px; margin: 0 0 8px 0; }

/* 内容区 - 主内容滚动，不撑开布局 */
.app-content {
  flex: 1;
  min-height: 0;
  padding: 24px;
  overflow: auto;
}
/* 我的资料库 - 卡片网格 */
.lib-grid-wrap { width: 100%; }
.lib-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; }
.lib-header h3 { margin: 0; font-size: 18px; color: var(--text); }
.lib-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 20px; }
.lib-card {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 20px;
  cursor: pointer;
  transition: border-color 0.2s, box-shadow 0.2s;
}
.lib-card:hover { border-color: var(--primary); box-shadow: 0 2px 8px rgba(26,86,176,0.12); }
.lib-card-icon { width: 40px; height: 40px; font-size: 40px; color: var(--primary); margin-bottom: 12px; }
.lib-card-name { font-weight: 600; font-size: 15px; color: var(--text); margin-bottom: 4px; }
.lib-card-badge { font-size: 11px; color: var(--primary); background: var(--primary-bg); padding: 2px 8px; border-radius: 4px; margin-left: 6px; }
.lib-card-desc { font-size: 13px; color: var(--text-secondary); margin: 0 0 12px 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.add-member-row { display: flex; gap: 10px; align-items: center; margin-bottom: 16px; }
.members-table { width: 100%; border-collapse: collapse; margin-top: 12px; }
.members-table th, .members-table td { padding: 8px 12px; text-align: left; border-bottom: 1px solid var(--border); }
.lib-card-actions { display: flex; gap: 8px; flex-wrap: wrap; }
.file-main { flex: 1; min-width: 0; }
.file-main h3 { margin: 0 0 12px 0; font-size: 16px; }
.breadcrumb-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}
.breadcrumb-link { color: var(--primary); }
.breadcrumb-sep { color: var(--text-secondary); }
.breadcrumb-current { color: var(--text-secondary); max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.toolbar-right { margin-left: auto; }

.btn-small { font-size: 12px; padding: 4px 10px; }
/* 系统管理 */
.sys-subtabs { display: flex; gap: 4px; margin-bottom: 24px; border-bottom: 1px solid var(--border); padding-bottom: 0; }
.subtab-item { padding: 10px 20px; border: none; background: none; font-size: 14px; font-weight: 500; color: var(--text-secondary); cursor: pointer; border-bottom: 2px solid transparent; margin-bottom: -1px; }
.subtab-item:hover { color: var(--primary); }
.subtab-item.active { color: var(--primary); border-color: var(--primary); font-weight: 600; }
.users-list-header-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.users-list-header-row .page-title { margin: 0; font-size: 20px; font-weight: 600; color: var(--text); }
/* 团队管理 */
.users-page { max-width: 960px; }
.users-permission-card { padding: 32px; text-align: center; }
.permission-hint { margin: 0; font-size: 15px; color: var(--danger); }
.modal .form-group { margin-bottom: 16px; }
.modal .form-group label { display: block; font-size: 14px; font-weight: 500; color: var(--text); margin-bottom: 6px; }
.modal .form-group input { width: 100%; box-sizing: border-box; padding: 8px 12px; }
.label-opt { font-weight: normal; color: var(--text-secondary); font-size: 12px; }
.modal .form-check { display: flex; align-items: center; gap: 8px; font-size: 14px; color: var(--text-secondary); cursor: pointer; margin: 16px 0 0 0; }
.users-list { flex: 1; min-width: 0; }
.users-list-header { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; }
.users-list-header h3 { margin: 0; font-size: 16px; font-weight: 600; }
.users-count { font-size: 13px; color: var(--text-secondary); }
.users-table-wrap { overflow-x: auto; }
.users-table { margin: 0; table-layout: fixed; width: 100%; min-width: 680px; border-collapse: collapse; }
.users-table th, .users-table td {
  padding: 12px 16px;
  text-align: left;
  vertical-align: middle;
}
.users-table td { overflow: hidden; }
.users-table .col-actions { overflow: visible; }
.users-table .col-username {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}
.username-text { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.users-table .col-email {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.user-avatar-sm {
  width: 28px; height: 28px; border-radius: 50%;
  background: linear-gradient(135deg, var(--primary), var(--primary-dark));
  color: #fff; font-size: 12px; font-weight: 600;
  display: inline-flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.users-table .col-date { color: var(--text-secondary); font-size: 13px; }
.users-table .col-actions {
  white-space: nowrap;
  overflow: visible;
  min-width: 150px;
}
.users-table .col-actions .btn-small { margin-right: 6px; }
.users-table .col-actions .btn-link { background: transparent; border: none; color: var(--primary); padding: 0 4px; font-size: 12px; }
.users-table .col-actions .btn-link:hover { text-decoration: underline; }
.badge { padding: 2px 8px; border-radius: 4px; font-size: 12px; }
.badge-admin { background: var(--primary-bg); color: var(--primary); }
.badge-user { background: #f3f4f6; color: var(--text-secondary); }
.col-status { white-space: nowrap; min-width: 52px; }
.status { padding: 2px 8px; border-radius: 4px; font-size: 12px; white-space: nowrap; display: inline-block; }
.status-ok { background: var(--success-bg); color: var(--success); }
.status-disabled { background: #fef2f2; color: var(--danger); }

/* 文件列表 - 行形式 */
.search-results-section { display: flex; flex-direction: column; gap: 0; }
.search-results-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  background: #f0f7ff;
  border-bottom: 1px solid var(--border);
  margin-bottom: 0;
}
.file-main.drop-zone-active { outline: 2px dashed var(--primary); background: var(--primary-bg); }
.file-grid { display: flex; flex-direction: column; gap: 0; }
.file-item-row {
  display: grid;
  grid-template-columns: 1fr 180px 100px auto;
  align-items: center;
  gap: 16px;
  padding: 10px 14px;
  border-bottom: 1px solid var(--border);
  min-height: 44px;
}
.file-grid-header {
  display: grid;
  grid-template-columns: 1fr 180px 100px auto;
  gap: 16px;
  padding: 10px 14px;
  background: #f7f8fa;
  font-weight: 600;
  font-size: 13px;
  color: var(--text);
  border-bottom: 1px solid var(--border);
}
.file-item-row:hover { background: #fafbfc; }
.file-item-name { min-width: 0; }
.file-item-link { display: inline-flex; align-items: center; gap: 8px; }
.file-item-link.plain { cursor: default; }
.file-item-link.plain:hover { text-decoration: none; }
.file-icon { width: 20px; height: 20px; font-size: 20px; color: var(--primary); flex-shrink: 0; }
.file-meta { font-size: 13px; color: var(--text-secondary); }
.file-actions-wrap { position: relative; display: inline-block; }
.actions-trigger {
  width: 32px; height: 32px; padding: 0; border: 1px solid var(--border); border-radius: 4px;
  background: #fff; color: var(--text-secondary); font-size: 18px; line-height: 1; cursor: pointer;
  display: inline-flex; align-items: center; justify-content: center;
}
.actions-trigger:hover { background: #f5f5f5; color: var(--text); }
.action-dropdown {
  position: absolute; right: 0; top: 100%; margin-top: 4px; z-index: 20;
  min-width: 88px; padding: 6px; background: #fff; border: 1px solid var(--border); border-radius: 6px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.12); display: flex; flex-direction: column; gap: 4px;
}
.action-dropdown .btn-small { width: 100%; min-width: 64px; box-sizing: border-box; justify-content: center; }

.audit-filters { display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 12px; align-items: center; }
.audit-date-row { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; padding: 12px 0; border-top: 1px solid var(--border); }
.audit-date-label { font-size: 14px; color: var(--text); white-space: nowrap; }
.audit-date-input { width: 150px; min-width: 150px; box-sizing: border-box; }
.empty-hint { color: var(--text-secondary); font-size: 14px; margin: 12px 0; }

.modal {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10;
}
.modal .card {
  max-width: 440px;
  width: 90%;
  max-height: 90vh;
  overflow: auto;
  background: #fff;
}
.modal .card h3 { margin-top: 0; }
.preview-card { min-width: 50vw; min-height: 50vh; width: 92vw; height: 90vh; max-width: 95vw; max-height: 92vh; display: flex; flex-direction: column; overflow: hidden; }
.preview-loading { padding: 40px; text-align: center; color: var(--text-secondary); }
.preview-body { flex: 1; overflow: auto; min-height: 50vh; display: flex; justify-content: center; align-items: flex-start; padding: 12px; }
.preview-img { max-width: 100%; min-height: 50vh; max-height: 82vh; object-fit: contain; }
.preview-iframe { width: 88vw; min-width: 50vw; min-height: 50vh; height: 82vh; border: 1px solid var(--border); border-radius: 6px; }
.preview-text { margin: 0; padding: 12px; font-family: inherit; font-size: 13px; white-space: pre-wrap; word-break: break-all; min-width: 50vw; min-height: 50vh; max-width: 85vw; max-height: 82vh; overflow: auto; background: #f8f9fa; border-radius: 6px; border: 1px solid var(--border); text-align: left; }
.modal-actions { margin-top: 16px; display: flex; gap: 10px; flex-wrap: wrap; }

.app-content .card { background: #fff; }
</style>
