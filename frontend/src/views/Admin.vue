<template>
  <div class="admin-layout">
    <div v-if="!me?.is_superuser" class="admin-permission-card">
      <p class="permission-hint">需要管理员权限，请使用管理员账号登录。</p>
    </div>
    <template v-else>
      <header class="admin-header">
        <div class="admin-header-left">
          <Icons name="drive" class="admin-logo" />
          <div>
            <h1 class="admin-title">系统管理</h1>
            <p class="admin-subtitle">Enterprise Cloud Storage Admin</p>
          </div>
        </div>
        <button type="button" class="admin-back-btn" @click="goBackHome">
          <Icons name="arrow-left" class="admin-back-icon" />
          返回
        </button>
      </header>
      <div class="admin-body">
        <aside class="admin-sidebar">
          <nav class="admin-nav">
            <button :class="['admin-nav-item', { active: subTab === 'users' }]" @click="switchTab('users')">
              <Icons name="users" class="admin-nav-icon" />
              用户管理
            </button>
            <button :class="['admin-nav-item', { active: subTab === 'departments' }]" @click="switchTab('departments')">
              <Icons name="building" class="admin-nav-icon" />
              部门管理
            </button>
            <button class="admin-nav-item disabled" disabled title="敬请期待">
              <Icons name="shield" class="admin-nav-icon" />
              权限管理
            </button>
            <button class="admin-nav-item disabled" disabled title="敬请期待">
              <Icons name="database" class="admin-nav-icon" />
              存储管理
            </button>
            <button :class="['admin-nav-item', { active: subTab === 'audit' }]" @click="switchTab('audit')">
              <Icons name="file-text" class="admin-nav-icon" />
              系统日志
            </button>
            <button class="admin-nav-item disabled" disabled title="敬请期待">
              <Icons name="bell" class="admin-nav-icon" />
              通知设置
            </button>
          </nav>
        </aside>
        <main class="admin-main">
          <!-- 用户管理 -->
          <div v-if="subTab === 'users'" class="admin-page">
            <div class="admin-page-header">
              <div>
                <h2 class="admin-page-title">用户管理</h2>
                <p class="admin-page-desc">管理系统用户账号和权限</p>
              </div>
              <button type="button" class="admin-btn-primary" @click="showCreateUser = true">
                <Icons name="plus" class="admin-btn-icon" />
                添加用户
              </button>
            </div>
            <div class="admin-stats">
              <div class="admin-stat-card">
                <div class="admin-stat-label">总用户数</div>
                <div class="admin-stat-value">{{ userList.length }}</div>
                <div class="admin-stat-extra text-green">共 {{ userList.length }} 人</div>
              </div>
              <div class="admin-stat-card">
                <div class="admin-stat-label">活跃用户</div>
                <div class="admin-stat-value">{{ userList.filter(u => u.is_active).length }}</div>
                <div class="admin-stat-extra">
                  {{ userList.length ? Math.round(userList.filter(u => u.is_active).length / userList.length * 100) : 0 }}% 活跃率
                </div>
              </div>
              <div class="admin-stat-card">
                <div class="admin-stat-label">管理员</div>
                <div class="admin-stat-value">{{ userList.filter(u => u.is_superuser).length }}</div>
                <div class="admin-stat-extra">系统管理员</div>
              </div>
              <div class="admin-stat-card">
                <div class="admin-stat-label">停用</div>
                <div class="admin-stat-value">{{ userList.filter(u => !u.is_active).length }}</div>
                <div class="admin-stat-extra">已禁用账号</div>
              </div>
            </div>
            <div class="admin-toolbar card">
              <div class="admin-search-wrap">
                <Icons name="search" class="admin-search-icon" />
                <input
                  v-model="sysSearchKeyword"
                  type="text"
                  :placeholder="sysSearchPlaceholder"
                  class="admin-search-input"
                  @keyup.enter="loadUsers"
                />
              </div>
              <select v-model="userFilterStatus" class="admin-select">
                <option value="">全部状态</option>
                <option value="active">活跃</option>
                <option value="inactive">停用</option>
              </select>
              <select v-model="userFilterRole" class="admin-select">
                <option value="">全部角色</option>
                <option value="admin">管理员</option>
                <option value="user">普通用户</option>
              </select>
            </div>
            <div class="admin-table-wrap card">
              <table class="admin-table">
                <thead>
                  <tr>
                    <th>用户信息</th>
                    <th class="admin-th-center">部门</th>
                    <th class="admin-th-center">角色 / 状态</th>
                    <th class="admin-th-center">创建时间</th>
                    <th class="text-right">操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="u in filteredUserList" :key="u.id" class="admin-table-row">
                    <td>
                      <div class="admin-user-info">
                        <div class="admin-user-name">{{ u.username }}</div>
                        <div class="admin-user-email">{{ u.email || '-' }}</div>
                      </div>
                    </td>
                    <td class="admin-cell admin-cell-center">{{ u.department_name || '-' }}</td>
                    <td class="admin-role-status-cell admin-cell-center">
                      <div class="admin-role-status-wrap">
                        <span :class="['admin-badge', u.is_superuser ? 'badge-admin' : 'badge-user']">
                          {{ u.is_superuser ? '管理员' : '普通用户' }}
                        </span>
                        <span :class="['admin-badge', u.is_active ? 'badge-ok' : 'badge-disabled']">
                          {{ u.is_active ? '活跃' : '停用' }}
                        </span>
                      </div>
                    </td>
                    <td class="admin-cell-muted admin-cell-center">{{ formatDate(u.created_at) }}</td>
                    <td class="text-right">
                      <button
                        v-if="u.id !== me?.id"
                        type="button"
                        class="admin-action-btn"
                        :class="{ danger: !u.is_active }"
                        @click="toggleUserActive(u)"
                      >
                        {{ u.is_active ? '停用' : '启用' }}
                      </button>
                      <button type="button" class="admin-action-btn link" @click="resetUserPassword(u)">重置密码</button>
                    </td>
                  </tr>
                </tbody>
              </table>
              <p v-if="!filteredUserList.length" class="admin-empty">暂无用户</p>
            </div>
          </div>

          <!-- 部门管理 -->
          <div v-if="subTab === 'departments'" class="admin-page">
            <div class="admin-page-header">
              <div>
                <h2 class="admin-page-title">部门管理</h2>
                <p class="admin-page-desc">管理组织架构和部门信息</p>
              </div>
              <button type="button" class="admin-btn-primary" @click="openAddRootDept">
                <Icons name="plus" class="admin-btn-icon" />
                添加部门
              </button>
            </div>
            <div class="admin-stats">
              <div class="admin-stat-card">
                <div class="admin-stat-label">总部门数</div>
                <div class="admin-stat-value">{{ deptTreeCount }}</div>
                <div class="admin-stat-extra">
                  <Icons name="building" class="admin-stat-icon" />
                </div>
              </div>
              <div class="admin-stat-card">
                <div class="admin-stat-label">总员工数</div>
                <div class="admin-stat-value">{{ userList.length }}</div>
                <div class="admin-stat-extra">
                  <Icons name="users" class="admin-stat-icon green" />
                </div>
              </div>
              <div class="admin-stat-card">
                <div class="admin-stat-label">总存储使用</div>
                <div class="admin-stat-value">{{ storageStats?.used_display || '0 B' }}</div>
                <div class="admin-stat-extra">共 {{ storageStats?.total_display || '500 GB' }}</div>
              </div>
              <div class="admin-stat-card">
                <div class="admin-stat-label">使用率</div>
                <div class="admin-stat-value">{{ Math.round(storageStats?.percent || 0) }}%</div>
                <div class="admin-stat-extra text-green">健康水平</div>
              </div>
            </div>
            <div class="card admin-table-wrap">
              <table class="admin-table admin-table-dept">
                <thead>
                  <tr>
                    <th class="admin-dept-th-name">部门名称</th>
                    <th class="admin-dept-th-center">负责人</th>
                    <th class="admin-dept-th-center">人数</th>
                    <th class="admin-dept-th-center">存储使用</th>
                    <th class="admin-dept-th-action">操作</th>
                  </tr>
                </thead>
                <tbody>
                  <DepartmentTableRow
                    v-for="node in filteredDeptTreeForTable"
                    :key="node.id"
                    :node="node"
                    :level="0"
                    :me="me"
                    @add="openAddSubDept"
                    @edit="openEditDept"
                    @delete="doDeleteDept"
                    @refresh="loadDepartments"
                  />
                </tbody>
              </table>
              <p v-if="!deptTreeForTable?.length" class="admin-empty">暂无部门，请点击上方「添加部门」创建。</p>
              <p v-else-if="!filteredDeptTreeForTable?.length" class="admin-empty">
                未找到匹配「{{ sysSearchKeyword }}」的部门。
              </p>
            </div>
          </div>

          <!-- 系统日志 -->
          <div v-if="subTab === 'audit'" class="admin-page">
            <div class="admin-page-header">
              <div>
                <h2 class="admin-page-title">系统日志</h2>
                <p class="admin-page-desc">审计与操作记录</p>
              </div>
            </div>
            <div class="admin-toolbar card">
              <input v-model="auditUsername" placeholder="用户名" class="admin-input-sm" />
              <input v-model="auditAction" placeholder="操作类型" class="admin-input-sm" />
              <span class="admin-label">开始</span>
              <input
                v-model="auditStartDate"
                type="text"
                placeholder="YYYY-MM-DD"
                class="admin-date-input"
                maxlength="10"
              />
              <span class="admin-label">结束</span>
              <input
                v-model="auditEndDate"
                type="text"
                placeholder="YYYY-MM-DD"
                class="admin-date-input"
                maxlength="10"
              />
              <button type="button" class="admin-btn-primary" @click="loadAudit">查询</button>
            </div>
            <div class="admin-table-wrap card">
              <table class="admin-table">
                <thead>
                  <tr>
                    <th>时间</th>
                    <th>用户</th>
                    <th>操作</th>
                    <th>资源</th>
                    <th>详情</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="log in auditList" :key="log.id" class="admin-table-row">
                    <td class="admin-cell-muted">{{ formatDate(log.created_at) }}</td>
                    <td>{{ log.username || '-' }}</td>
                    <td>{{ log.action }}</td>
                    <td>{{ log.resource_type }} {{ log.resource_id }}</td>
                    <td>{{ log.detail || '-' }}</td>
                  </tr>
                </tbody>
              </table>
              <p v-if="!auditList.length" class="admin-empty">暂无审计记录，或调整筛选条件后查询。</p>
            </div>
          </div>
        </main>
      </div>
    </template>

    <!-- 以下为系统管理相关弹窗 -->

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
        <p v-if="addSubDeptParent" style="margin-bottom:12px; color:#6b7280; font-size:14px;">
          上级部门：{{ addSubDeptParent.name }}
        </p>
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
              <option
                v-for="opt in deptOptionsForUser"
                :key="opt.id"
                :value="opt.id"
              >
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
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import * as api from '../api/client'
import Icons from '../components/Icons.vue'
import DepartmentTableRow from '../components/DepartmentTableRow.vue'

const router = useRouter()

const me = ref(null)
const subTab = ref('users')
const sysSearchKeyword = ref('')
const userFilterStatus = ref('')
const userFilterRole = ref('')
const userList = ref([])
const storageStats = ref(null)
const deptTreeForTable = ref([])
const auditList = ref([])
const auditUsername = ref('')
const auditAction = ref('')
const auditStartDate = ref('')
const auditEndDate = ref('')

// 部门弹窗相关
const showAddRootDept = ref(false)
const newRootDeptName = ref('')
const showAddSubDept = ref(false)
const addSubDeptParent = ref(null)
const addSubDeptName = ref('')
const showEditDept = ref(false)
const editDeptNode = ref(null)
const editDeptName = ref('')

// 创建用户相关
const showCreateUser = ref(false)
const newUserEmail = ref('')
const newUserUsername = ref('')
const newUserPassword = ref('')
const newUserDeptId = ref(null)
const newUserRole = ref('user')

const err = ref('')

const sysSearchPlaceholder = computed(() => {
  if (subTab.value === 'users') return '搜索用户、邮箱...'
  if (subTab.value === 'audit') return '搜索操作、用户...'
  if (subTab.value === 'departments') return '搜索部门...'
  return '搜索...'
})

const filteredUserList = computed(() => {
  let list = userList.value
  const kw = sysSearchKeyword.value?.trim().toLowerCase()
  if (kw) {
    list = list.filter(
      u =>
        (u.username || '').toLowerCase().includes(kw) ||
        (u.email || '').toLowerCase().includes(kw),
    )
  }
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

function _countDeptNodes(nodes) {
  if (!nodes?.length) return 0
  return nodes.reduce((sum, n) => sum + 1 + _countDeptNodes(n.children), 0)
}

function _filterDeptTree(nodes, keyword) {
  if (!nodes?.length) return []
  const kw = (keyword || '').trim().toLowerCase()
  if (!kw) return nodes
  const out = []
  for (const n of nodes) {
    const match = (n.name || '').toLowerCase().includes(kw)
    const filteredChildren = _filterDeptTree(n.children, keyword)
    if (match || filteredChildren.length) {
      out.push({ ...n, children: match ? (n.children || []) : filteredChildren })
    }
  }
  return out
}

const filteredDeptTreeForTable = computed(() =>
  _filterDeptTree(deptTreeForTable.value, sysSearchKeyword.value),
)

const deptOptionsForUser = computed(() => _flattenDepts(deptTreeForTable.value))
const deptTreeCount = computed(() => _countDeptNodes(deptTreeForTable.value))

function formatDate(s) {
  if (!s) return '-'
  const d = new Date(s)
  return d.toLocaleString('zh-CN')
}

function goBackHome() {
  router.push('/')
}

function switchTab(name) {
  subTab.value = name
  if (name === 'users') loadUsers()
  if (name === 'departments') loadDepartments()
  if (name === 'audit') loadAudit()
}

async function loadStorageStats() {
  try {
    storageStats.value = await api.getStorageStats()
  } catch (e) {
    storageStats.value = null
  }
}

async function loadUsers() {
  try {
    const params = {}
    const kw = sysSearchKeyword.value?.trim()
    if (kw) params.search = kw
    if (userFilterStatus.value === 'active') params.is_active = true
    if (userFilterStatus.value === 'inactive') params.is_active = false
    userList.value = await api.listUsers(params)
  } catch (e) {
    err.value = e.message
  }
}

async function loadDepartments() {
  try {
    deptTreeForTable.value = await api.getDepartmentTree()
  } catch (e) {
    deptTreeForTable.value = []
  }
}

async function loadAudit() {
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

function onSysSearch() {
  const kw = sysSearchKeyword.value?.trim()
  if (!kw && subTab.value !== 'departments') {
    // 清空搜索时重新加载数据
    if (subTab.value === 'users') loadUsers()
    if (subTab.value === 'audit') loadAudit()
    return
  }
  if (subTab.value === 'users') loadUsers()
  if (subTab.value === 'audit') loadAudit()
  // 部门管理为前端过滤，filteredDeptTreeForTable 会随 sysSearchKeyword 自动更新
}

function openAddRootDept() {
  newRootDeptName.value = ''
  err.value = ''
  showAddRootDept.value = true
}

async function doAddRootDept() {
  err.value = ''
  const name = newRootDeptName.value?.trim()
  if (!name) {
    err.value = '请输入部门名称'
    return
  }
  try {
    await api.createDepartment(name, null, 0)
    showAddRootDept.value = false
    newRootDeptName.value = ''
    await loadDepartments()
  } catch (e) {
    err.value = e.message
  }
}

function openAddSubDept(node) {
  addSubDeptParent.value = node
  addSubDeptName.value = ''
  err.value = ''
  showAddSubDept.value = true
}

async function doAddSubDept() {
  if (!addSubDeptParent.value) return
  err.value = ''
  const name = addSubDeptName.value?.trim()
  if (!name) {
    err.value = '请输入部门名称'
    return
  }
  try {
    await api.createDepartment(name, addSubDeptParent.value.id, 0)
    showAddSubDept.value = false
    addSubDeptParent.value = null
    addSubDeptName.value = ''
    await loadDepartments()
  } catch (e) {
    err.value = e.message
  }
}

function openEditDept(node) {
  editDeptNode.value = node
  editDeptName.value = node.name
  showEditDept.value = true
  err.value = ''
}

async function doSaveEditDept() {
  if (!editDeptNode.value) return
  err.value = ''
  const name = editDeptName.value?.trim()
  if (!name) {
    err.value = '请输入部门名称'
    return
  }
  try {
    await api.updateDepartment(editDeptNode.value.id, { name })
    showEditDept.value = false
    editDeptNode.value = null
    await loadDepartments()
  } catch (e) {
    err.value = e.message
  }
}

async function doDeleteDept(node) {
  if (!confirm('确定删除部门「' + node.name + '」？其子部门将一并删除。')) return
  try {
    await api.deleteDepartment(node.id)
    await loadDepartments()
  } catch (e) {
    err.value = e.message || '删除失败'
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
  err.value = ''
  try {
    await api.updateUser(u.id, { new_password: newPw })
    // 不强制刷新列表，以免打断正在查看的数据
  } catch (e) {
    err.value = e.message
  }
}

function closeCreateUser() {
  showCreateUser.value = false
  newUserEmail.value = ''
  newUserUsername.value = ''
  newUserPassword.value = ''
  newUserDeptId.value = null
  newUserRole.value = 'user'
  err.value = ''
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
  try {
    const isSuper = newUserRole.value === 'admin'
    const deptId = newUserDeptId.value ? Number(newUserDeptId.value) : null
    await api.createUser(newUserEmail.value.trim(), newUserUsername.value.trim(), newUserPassword.value, isSuper, deptId)
    showCreateUser.value = false
    newUserEmail.value = ''
    newUserUsername.value = ''
    newUserPassword.value = ''
    newUserDeptId.value = null
    newUserRole.value = 'user'
    await loadUsers()
  } catch (e) {
    err.value = e.message
  }
}

onMounted(async () => {
  me.value = await api.getMe()
  if (!me.value?.is_superuser) {
    return
  }
  await Promise.all([
    loadUsers(),
    loadDepartments(),
    loadStorageStats(),
    loadAudit(),
  ])
})
</script>

<style scoped>
.admin-layout {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #f3f4f6;
}

.admin-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 24px;
  background: #fff;
  border-bottom: 1px solid var(--border);
}

.admin-header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.admin-logo {
  width: 32px;
  height: 32px;
}

.admin-title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
}

.admin-subtitle {
  margin: 2px 0 0;
  font-size: 12px;
  color: #6b7280;
}

.admin-back-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border-radius: 999px;
  border: 1px solid var(--border);
  padding: 6px 12px;
  background: #fff;
  font-size: 13px;
  cursor: pointer;
}

.admin-back-icon {
  width: 16px;
  height: 16px;
}

.admin-body {
  display: flex;
  flex: 1;
  min-height: 0;
}

.admin-sidebar {
  width: 220px;
  background: #fff;
  border-right: 1px solid var(--border);
  padding: 16px 12px;
}

.admin-nav {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.admin-nav-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 8px;
  border: none;
  background: transparent;
  cursor: pointer;
  font-size: 14px;
  text-align: left;
}

.admin-nav-item.active {
  background: #e5f0ff;
  color: #1d4ed8;
}

.admin-nav-item.disabled {
  cursor: default;
  opacity: 0.6;
}

.admin-nav-icon {
  width: 20px;
  height: 20px;
  flex-shrink: 0;
}

.admin-main {
  flex: 1;
  padding: 32px;
  overflow-y: auto;
  min-width: 0;
}

.admin-page {
  max-width: 1200px;
}

.admin-page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 24px;
  gap: 16px;
}

.admin-page-title {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
}

.admin-page-desc {
  margin: 4px 0 0;
  font-size: 14px;
  color: #6b7280;
}

.admin-btn-primary {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  background: linear-gradient(90deg, #4a90e2, #357abd);
  color: #fff;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  flex-shrink: 0;
}

.admin-btn-icon {
  width: 16px;
  height: 16px;
}

.admin-stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}

.admin-stat-card {
  background: #fff;
  border-radius: 12px;
  padding: 16px 16px 14px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
}

.admin-stat-label {
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 6px;
}

.admin-stat-value {
  font-size: 20px;
  font-weight: 600;
  margin-bottom: 4px;
}

.admin-stat-extra {
  font-size: 12px;
  color: #9ca3af;
}

.admin-stat-icon {
  width: 16px;
  height: 16px;
}

.admin-stat-icon.green {
  color: #16a34a;
}

.admin-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.admin-search-wrap {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 8px;
}

.admin-search-icon {
  width: 16px;
  height: 16px;
  color: #9ca3af;
}

.admin-search-input {
  flex: 1;
  min-width: 0;
  border-radius: 999px;
  border: 1px solid var(--border);
  padding: 6px 12px;
  font-size: 13px;
}

.admin-select {
  border-radius: 999px;
  border: 1px solid var(--border);
  padding: 6px 12px;
  font-size: 13px;
  background: #fff;
}

.admin-table-wrap {
  background: #fff;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
}

.admin-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.admin-table th,
.admin-table td {
  padding: 6px 12px;
  text-align: left;
}

.admin-table thead th {
  font-size: 12px;
  font-weight: 500;
  color: #6b7280;
  border-bottom: 1px solid #e5e7eb;
}

.admin-table-row:nth-child(odd) td {
  background: #f9fafb;
}

.admin-user-info {
  display: flex;
  flex-direction: column;
}

.admin-user-name {
  font-weight: 500;
}

.admin-user-email {
  font-size: 12px;
  color: #6b7280;
}

.admin-cell {
  white-space: nowrap;
}

.admin-cell-muted {
  font-size: 12px;
  color: #9ca3af;
  white-space: nowrap;
}

.admin-role-status-cell {
  text-align: center;
  vertical-align: middle;
  white-space: nowrap;
}

.admin-th-center {
  text-align: center;
}

.admin-cell-center {
  text-align: center;
}

.admin-role-status-wrap {
  display: inline-flex;
  gap: 6px;
  align-items: center;
}

.admin-badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
}

.badge-admin {
  background: #eef2ff;
  color: #4f46e5;
}

.badge-user {
  background: #f3f4f6;
  color: #4b5563;
}

.badge-ok {
  background: #ecfdf3;
  color: #16a34a;
}

.badge-disabled {
  background: #fef2f2;
  color: #b91c1c;
}

.admin-action-btn {
  border-radius: 999px;
  border: 1px solid var(--border);
  padding: 4px 10px;
  font-size: 12px;
  background: #fff;
  cursor: pointer;
}

.admin-action-btn.danger {
  border-color: #f97373;
  color: #b91c1c;
}

.admin-action-btn.link {
  border: none;
  background: none;
  color: #2563eb;
  padding-inline: 4px;
}

.admin-empty {
  margin: 12px 0 0;
  font-size: 13px;
  color: #6b7280;
}

.admin-dept-th-name {
  width: 40%;
}

.admin-dept-th-center,
.admin-dept-th-action {
  text-align: center;
}

.admin-input-sm {
  border-radius: 999px;
  border: 1px solid var(--border);
  padding: 6px 10px;
  font-size: 12px;
}

.admin-date-input {
  border-radius: 8px;
  border: 1px solid var(--border);
  padding: 4px 8px;
  font-size: 12px;
}

.admin-label {
  font-size: 12px;
  color: #6b7280;
}

.admin-permission-card {
  max-width: 480px;
  margin: 80px auto 0;
  background: #fff;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.08);
}

.permission-hint {
  margin: 0;
  font-size: 14px;
  color: #6b7280;
}

.user-modal-card {
  min-width: 520px;
}

.user-modal-grid {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 12px;
}

/* 弹窗通用布局（居中显示） */
.modal {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 50;
}

.modal .card {
  width: 90%;
  max-width: 520px;
  max-height: 90vh;
  overflow: auto;
  background: #fff;
}

.modal .card h3 {
  margin-top: 0;
}

.text-danger {
  color: #b91c1c;
  font-size: 13px;
  margin: 8px 0 0;
}

.modal .form-group {
  margin-bottom: 12px;
}

.modal .form-group label {
  display: block;
  font-size: 14px;
  font-weight: 500;
  color: var(--text, #111827);
  margin-bottom: 6px;
}

.modal .form-group input,
.modal .form-group select {
  width: 100%;
  box-sizing: border-box;
  padding: 8px 12px;
}

.modal-actions {
  margin-top: 16px;
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
</style>

