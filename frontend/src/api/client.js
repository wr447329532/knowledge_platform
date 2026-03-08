const BASE = '/api'

function getToken() {
  return localStorage.getItem('token')
}

export async function api(url, options = {}) {
  const token = getToken()
  const headers = { ...options.headers }
  if (token) headers['Authorization'] = `Bearer ${token}`
  const res = await fetch(BASE + url, { ...options, headers })
  if (res.status === 401) {
    localStorage.removeItem('token')
    window.location.href = '/#/login'
    throw new Error('未登录')
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    const msg = Array.isArray(err.detail) ? err.detail.map((e) => e.msg || JSON.stringify(e)).join('；') : (err.detail || res.statusText)
    throw new Error(msg)
  }
  const type = res.headers.get('content-type')
  if (type && type.includes('application/json')) return res.json()
  return res
}

export async function login(username, password) {
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
  localStorage.setItem('token', data.access_token)
  return data
}

/** 仅管理员可调用：创建新用户（平台不支持开放注册） */
export async function createUser(username, password, email = '', is_superuser = false) {
  const data = await api('/auth/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password, email: email || null, is_superuser }),
  })
  return data
}

export function logout() {
  localStorage.removeItem('token')
  window.location.href = '/#/login'
}

export async function getMe() {
  return api('/auth/me')
}

export async function changePassword(oldPassword, newPassword) {
  return api('/auth/change-password', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ old_password: oldPassword, new_password: newPassword }),
  })
}

/** 仅管理员：用户列表 */
export async function listUsers() {
  return api('/auth/users')
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

export async function createLibrary(name, description = '') {
  return api('/libraries/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, description }),
  })
}

export async function updateLibrary(id, name, description) {
  const body = {}
  if (name !== undefined) body.name = name
  if (description !== undefined) body.description = description
  return api(`/libraries/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export async function deleteLibrary(id) {
  return api(`/libraries/${id}`, { method: 'DELETE' })
}

/** 文件分享：仅拥有者可管理 */
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

/** 获取存储空间统计 */
export async function getStorageStats(libraryId = null) {
  let url = '/files/storage'
  if (libraryId != null) url += `?library_id=${libraryId}`
  return api(url)
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
