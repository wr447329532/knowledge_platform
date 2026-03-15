const BASE = '/api'

function getToken() {
  // 优先使用会话级 token（记住登录未勾选时），否则回退到持久化 token
  return sessionStorage.getItem('token') || localStorage.getItem('token')
}

function clearToken() {
  sessionStorage.removeItem('token')
  localStorage.removeItem('token')
}

function setToken(token, { remember } = { remember: true }) {
  clearToken()
  if (remember) {
    localStorage.setItem('token', token)
  } else {
    sessionStorage.setItem('token', token)
  }
}

function replaceTokenPreserveStorage(token) {
  // 根据当前 token 所在位置决定写入哪种存储，避免改变登录时的记住策略
  const inSession = !!sessionStorage.getItem('token')
  const inLocal = !!localStorage.getItem('token')
  clearToken()
  if (inSession) {
    sessionStorage.setItem('token', token)
  } else if (inLocal) {
    localStorage.setItem('token', token)
  } else {
    // 默认行为：如果之前没有 token，就当作持久化处理
    localStorage.setItem('token', token)
  }
}

export async function api(url, options = {}) {
  const token = getToken()
  const headers = { ...options.headers }
  if (token) headers['Authorization'] = `Bearer ${token}`
  const res = await fetch(BASE + url, { ...options, headers })
  if (res.status === 401) {
    clearToken()
    window.location.href = '/#/login'
    throw new Error('未登录')
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    const msg = Array.isArray(err.detail) ? err.detail.map((e) => e.msg || JSON.stringify(e)).join('；') : (err.detail || res.statusText)
    throw new Error(msg)
  }
  // 204 No Content 无响应体，不解析 JSON
  if (res.status === 204) return null
  const type = res.headers.get('content-type')
  if (type && type.includes('application/json')) return res.json()
  return res
}

export async function login(username, password, remember = true) {
  const form = new FormData()
  form.append('username', username)
  form.append('password', password)
  let res
  try {
    res = await fetch(BASE + '/auth/login', { method: 'POST', body: form })
  } catch (e) {
    throw new Error('无法连接服务器，请确认后端已启动（端口 8000）')
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || '登录失败')
  }
  const data = await res.json()
  if (data && data.access_token) {
    setToken(data.access_token, { remember })
  }
  return data
}

/** 仅管理员可调用：创建新用户（平台不支持开放注册）。邮箱必填用于登录，用户名仅用于显示。 */
export async function createUser(email, username, password, is_superuser = false, department_id = null) {
  const data = await api('/auth/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, username, password, is_superuser, department_id }),
  })
  return data
}

export function logout() {
  clearToken()
  window.location.href = '/#/login'
}

export async function getMe() {
  return api('/auth/me')
}

export async function updateMe(profile) {
  // 目前仅支持更新用户名（显示姓名），更新成功后后端会返回新的 access_token
  const body = {}
  if (profile.name !== undefined) body.username = profile.name
  const data = await api('/auth/me', {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (data && data.access_token) {
    replaceTokenPreserveStorage(data.access_token)
  }
  return data
}

export async function changePassword(oldPassword, newPassword) {
  return api('/auth/change-password', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ old_password: oldPassword, new_password: newPassword }),
  })
}

/** 仅管理员：用户列表，可选 search（用户名/邮箱）、is_active（true/false） */
export async function listUsers(params = {}) {
  const q = new URLSearchParams()
  if (params.search != null && params.search !== '') q.set('search', params.search)
  if (params.is_active === true) q.set('is_active', 'true')
  if (params.is_active === false) q.set('is_active', 'false')
  const query = q.toString()
  return api(`/auth/users${query ? '?' + query : ''}`)
}

/** 库成员选择用的活跃用户列表：所有登录用户可调用，仅返回活跃账号 */
export async function listUsersForLibrary(search = '') {
  const q = new URLSearchParams()
  if (search != null && search !== '') q.set('search', search)
  const query = q.toString()
  return api(`/auth/users/active${query ? '?' + query : ''}`)
}

/** 仅管理员：更新用户（禁用/启用、重置密码） */
export async function updateUser(userId, { is_active, new_password }) {
  const body = {}
  if (is_active !== undefined) body.is_active = is_active
  if (new_password !== undefined) body.new_password = new_password
  return api(`/auth/users/${userId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export async function listLibraries() {
  return api('/libraries/')
}

export async function getLibrary(id) {
  return api(`/libraries/${id}`)
}

export async function createLibrary(name, description = '', departmentId = null, visibility = 'private', memberUserIds = [], allowDownload = true) {
  const body = { name, description, visibility, allow_download: allowDownload }
  if (departmentId != null) body.department_id = departmentId
  if (Array.isArray(memberUserIds) && memberUserIds.length) body.member_user_ids = memberUserIds
  return api('/libraries/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export async function updateLibrary(id, name, description, visibility, allowDownload) {
  const body = {}
  if (name !== undefined) body.name = name
  if (description !== undefined) body.description = description
  if (visibility !== undefined) body.visibility = visibility
  if (allowDownload !== undefined) body.allow_download = allowDownload
  return api(`/libraries/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

/** 软删除：将资料库移入回收站（可恢复） */
export async function deleteLibrary(id) {
  return api(`/libraries/${id}`, { method: 'DELETE' })
}

/** 列出回收站中的资料库 */
export async function listLibraryTrash() {
  return api('/libraries/trash')
}

/** 从回收站恢复资料库 */
export async function restoreLibrary(id) {
  return api(`/libraries/${id}/restore`, { method: 'POST' })
}

/** 彻底删除回收站中的资料库（不可恢复） */
export async function permanentDeleteLibrary(id) {
  return api(`/libraries/trash/${id}`, { method: 'DELETE' })
}

/** 资料库成员管理 */
export async function listLibraryMembers(libraryId) {
  return api(`/libraries/${libraryId}/members`)
}

export async function addLibraryMember(libraryId, userId, role = 'read') {
  return api(`/libraries/${libraryId}/members?user_id=${encodeURIComponent(userId)}&role=${encodeURIComponent(role)}`, {
    method: 'POST',
  })
}

export async function removeLibraryMember(libraryId, userId) {
  return api(`/libraries/${libraryId}/members/${userId}`, {
    method: 'DELETE',
  })
}

/** 部门树 */
export async function getDepartmentTree() {
  return api('/departments/tree')
}
export async function getDepartmentInfo(id) {
  return api(`/departments/${id}/info`)
}
export async function listDepartmentFiles(id) {
  return api(`/departments/${id}/files`)
}
export async function listDepartmentLibraries(id) {
  return api(`/departments/${id}/libraries`)
}
export async function listDepartmentMembers(id) {
  return api(`/departments/${id}/members`)
}
export async function createDepartment(name, parentId = null, sortOrder = 0) {
  return api('/departments/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, parent_id: parentId, sort_order: sortOrder }),
  })
}
export async function updateDepartment(id, { name, parent_id, sort_order, leader_user_id }) {
  const body = {}
  if (name !== undefined) body.name = name
  if (parent_id !== undefined) body.parent_id = parent_id
  if (sort_order !== undefined) body.sort_order = sort_order
  if (leader_user_id !== undefined) body.leader_user_id = leader_user_id
  return api(`/departments/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}
export async function deleteDepartment(id) {
  return api(`/departments/${id}`, { method: 'DELETE' })
}

/** 文件分享：仅拥有者可管理（单文件） */
export async function listMyShares() {
  // 共享文件库：我分享的文件库
  return api('/libraries/shared/mine')
}
/** 分享给我的文件列表 */
export async function listSharesToMe() {
  // 共享文件库：分享给我的文件库
  return api('/libraries/shared/to-me')
}
export async function listFileShareAddableUsers(entryId) {
  return api(`/files/shares/addable-users?entry_id=${entryId}`)
}
export async function listFileShares(entryId) {
  return api(`/files/shares?entry_id=${entryId}`)
}
export async function addFileShare(entryId, userId, permission = 'download') {
  return api(`/files/shares?entry_id=${entryId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: userId, permission }),
  })
}
export async function removeFileShare(entryId, userId) {
  return api(`/files/shares?entry_id=${entryId}&user_id=${userId}`, { method: 'DELETE' })
}

export async function listFiles(libraryId, pathPrefix = '', includeDirs = true) {
  let url = `/files/list?library_id=${libraryId}&include_dirs=${includeDirs}`
  if (pathPrefix) url += `&path_prefix=${encodeURIComponent(pathPrefix)}`
  return api(url)
}

/** 重命名文件或目录 */
export async function renameFile(entryId, newPath) {
  return api(`/files/${entryId}/rename?new_path=${encodeURIComponent(newPath)}`, {
    method: 'PATCH',
  })
}

/** 搜索文件（按路径关键词） */
export async function searchFiles(libraryId, keyword) {
  if (!keyword || !keyword.trim()) return []
  return api(`/files/search?library_id=${libraryId}&keyword=${encodeURIComponent(keyword.trim())}`)
}

/** 全局/库内搜索（用于版本匹配）：libraryId 为 null 时返回 [] */
export async function searchFilesGlobal(keyword, libraryId) {
  if (!keyword || !keyword.trim()) return []
  if (libraryId == null) return []
  return api(`/files/search?library_id=${libraryId}&keyword=${encodeURIComponent(keyword.trim())}`)
}

/** 获取存储空间统计 */
export async function getStorageStats(libraryId = null) {
  let url = '/files/storage'
  if (libraryId != null) url += `?library_id=${libraryId}`
  return api(url)
}

/** 存储管理：按部门统计 */
export async function getDepartmentStorage() {
  return api('/files/storage/departments')
}

/** 存储管理：按用户统计 */
export async function getUserStorage() {
  return api('/files/storage/users')
}

/** 存储管理：按文件类型统计 */
export async function getFileTypeStorage() {
  return api('/files/storage/filetypes')
}

/** 存储管理：调整部门配额（GB） */
export async function updateDepartmentQuota(deptId, quotaGb) {
  return api(`/files/storage/departments/${deptId}/quota`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ quota_gb: quotaGb }),
  })
}

/** 存储管理：调整用户配额（GB） */
export async function updateUserQuota(userId, quotaGb) {
  return api(`/files/storage/users/${userId}/quota`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ quota_gb: quotaGb }),
  })
}

export async function uploadFile(libraryId, relativePath, file) {
  const form = new FormData()
  form.append('file', file)
  const token = getToken()
  const res = await fetch(BASE + `/files/upload?library_id=${libraryId}&relative_path=${encodeURIComponent(relativePath)}`, {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: form,
  })
  if (res.status === 401) {
    localStorage.removeItem('token')
    window.location.href = '/#/login'
    throw new Error('未登录')
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    let msg = '上传失败'
    if (err.detail) {
      msg = Array.isArray(err.detail) ? err.detail.map((e) => e.msg || e.loc?.join('.') || JSON.stringify(e)).join('；') : String(err.detail)
    } else if (res.status === 413) {
      msg = '文件过大，请尝试上传较小的文件或联系管理员调整限制'
    }
    throw new Error(msg)
  }
  return res.json()
}

/** 带上传进度的上传（用于上传弹窗进度条），onProgress(0-100) */
/** 上传为新版本（指定 entry 对象，需含 library_id、path） */
export function uploadVersionWithProgress(entry, comment, file, onProgress) {
  if (!entry?.library_id || !entry?.path) throw new Error('无效的文件条目')
  return uploadFileWithProgress(entry.library_id, entry.path, file, onProgress)
}

export function uploadFileWithProgress(libraryId, relativePath, file, onProgress) {
  return new Promise((resolve, reject) => {
    const token = getToken()
    const xhr = new XMLHttpRequest()
    const form = new FormData()
    form.append('file', file)
    const url = `${BASE}/files/upload?library_id=${libraryId}&relative_path=${encodeURIComponent(relativePath)}`
    xhr.open('POST', url)
    if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`)
    xhr.upload.addEventListener('progress', (e) => {
      if (e.lengthComputable && typeof onProgress === 'function') {
        onProgress(Math.round((e.loaded / e.total) * 100))
      }
    })
    xhr.addEventListener('load', () => {
      if (xhr.status === 401) {
        localStorage.removeItem('token')
        window.location.href = '/#/login'
        reject(new Error('未登录'))
        return
      }
      if (xhr.status < 200 || xhr.status >= 300) {
        let msg = '上传失败'
        try {
          const err = JSON.parse(xhr.responseText)
          if (err.detail) msg = Array.isArray(err.detail) ? err.detail.map((e) => e.msg || JSON.stringify(e)).join('；') : String(err.detail)
        } catch (_) {}
        if (xhr.status === 413) msg = '文件过大，请尝试上传较小的文件或联系管理员调整限制'
        reject(new Error(msg))
        return
      }
      try {
        resolve(JSON.parse(xhr.responseText || '{}'))
      } catch (_) {
        resolve({})
      }
    })
    xhr.addEventListener('error', () => reject(new Error('网络错误')))
    xhr.send(form)
  })
}

export function downloadUrl(entryId, versionNo = '') {
  let url = `${BASE}/files/download?entry_id=${entryId}`
  if (versionNo) url += `&version_no=${versionNo}`
  const token = getToken()
  return `${url}&t=${Date.now()}` // 带 token 需前端用 fetch 加 header 下载，这里先做新开窗口会丢 header，改用 fetch 下载
}

export async function downloadFile(entryId, versionNo = null) {
  let url = BASE + `/files/download?entry_id=${entryId}`
  if (versionNo != null) url += `&version_no=${versionNo}`
  const token = getToken()
  const res = await fetch(url, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
  if (!res.ok) throw new Error('下载失败')
  const blob = await res.blob()
  const disposition = res.headers.get('content-disposition')
  let filename = 'download'
  if (disposition) {
    const m = disposition.match(/filename="?([^";]+)"?/)
    if (m) filename = decodeURIComponent(m[1].trim())
  }
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = filename
  a.click()
  URL.revokeObjectURL(a.href)
}

async function _previewFetch(entryId, versionNo = null) {
  let url = BASE + `/files/preview?entry_id=${entryId}`
  if (versionNo != null) url += `&version_no=${versionNo}`
  const token = getToken()
  let res
  try {
    res = await fetch(url, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
  } catch (e) {
    throw new Error('请求失败，请确认后端已启动（端口 8000）且前端代理正常')
  }
  if (res.status === 401) {
    localStorage.removeItem('token')
    window.location.href = '/#/login'
    throw new Error('未登录')
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    const msg = typeof err.detail === 'string' ? err.detail : (Array.isArray(err.detail) ? err.detail.map((e) => e.msg || JSON.stringify(e)).join('；') : '预览失败')
    throw new Error(msg)
  }
  return res
}

/** 获取预览 token（用于 iframe/img 直接加载 URL，Seafile 式） */
export async function getPreviewToken(entryId) {
  return api(`/files/preview-token?entry_id=${entryId}`)
}

/** 获取预览直链 URL（含 token，用于 iframe/img src） */
export async function previewUrl(entryId) {
  const { token } = await getPreviewToken(entryId)
  let url = BASE + `/files/preview-by-token?entry_id=${entryId}&token=${encodeURIComponent(token)}`
  return url
}

/** 获取预览 Blob URL（图片/PDF），调用方用完后需 revokeObjectURL（备用） */
export async function previewFile(entryId, versionNo = null) {
  const res = await _previewFetch(entryId, versionNo)
  const blob = await res.blob()
  return URL.createObjectURL(blob)
}

/** 获取预览文本内容（txt/md/json 等） */
export async function previewFileAsText(entryId) {
  const res = await _previewFetch(entryId)
  return res.text()
}

const PREVIEW_EXT = ['.pdf', '.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.bmp', '.txt', '.md', '.json', '.xml', '.html', '.htm', '.css', '.js', '.yaml', '.yml']
export function canPreview(path) {
  const ext = '.' + (path || '').split('.').pop().toLowerCase()
  return PREVIEW_EXT.includes(ext)
}

export async function listVersions(entryId) {
  return api(`/files/versions?entry_id=${entryId}`)
}

export async function createDir(libraryId, path) {
  return api(`/files/mkdir?library_id=${libraryId}&path=${encodeURIComponent(path)}`, { method: 'POST' })
}

export async function deleteFile(entryId) {
  return api(`/files/${entryId}`, { method: 'DELETE' })
}

export async function listTrash(libraryId) {
  return api(`/files/trash?library_id=${libraryId}`)
}

export async function restoreFile(entryId) {
  return api(`/files/${entryId}/restore`, { method: 'POST' })
}

export async function permanentDelete(entryId) {
  return api(`/files/trash/${entryId}`, { method: 'DELETE' })
}

export async function listAuditLogs(params = {}) {
  const q = new URLSearchParams(params).toString()
  return api(`/audit/logs${q ? '?' + q : ''}`)
}

/** 通知 */
export async function listNotifications(unreadOnly = false) {
  const q = unreadOnly ? '?unread_only=true' : ''
  return api(`/notifications/${q}`)
}

export async function markNotificationRead(id) {
  return api(`/notifications/${id}/read`, { method: 'POST' })
}

export async function markAllNotificationsRead() {
  return api('/notifications/read-all', { method: 'POST' })
}

/** 系统管理 - 通知模板列表（管理员） */
export async function listNotificationTemplatesAdmin() {
  return api('/notifications/admin/templates')
}

/** 系统管理 - 通知发送历史（管理员） */
export async function listNotificationHistoryAdmin(limit = 50) {
  const q = new URLSearchParams({ limit: String(limit) }).toString()
  return api(`/notifications/admin/history${q ? '?' + q : ''}`)
}

/** 系统管理 - 通知开关设置（管理员） */
export async function listNotificationSettingsAdmin() {
  return api('/notifications/admin/settings')
}

/** 系统管理 - 更新通知开关（管理员） */
export async function updateNotificationSettingAdmin(settingId, enabled) {
  return api(`/notifications/admin/settings/${settingId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ enabled }),
  })
}

/** 系统管理 - 发送自定义通知（管理员） */
export async function sendAdminNotification({ title, content, target = 'all', channels = ['system'] }) {
  return api('/notifications/admin/send', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title, content, target, channels }),
  })
}
