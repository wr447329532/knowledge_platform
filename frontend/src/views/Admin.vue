<template>
  <div class="admin-layout">
    <div v-if="!me" class="admin-permission-card">
      <p class="permission-hint">正在加载权限，请稍候...</p>
    </div>
    <div v-else-if="!me.is_superuser && !me.is_department_leader" class="admin-permission-card">
      <p class="permission-hint">需要管理员或部门负责人权限，请使用有权限的账号登录。</p>
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
            <button
              v-if="me?.is_superuser"
              :class="['admin-nav-item', { active: subTab === 'users' }]"
              @click="switchTab('users')"
            >
              <Icons name="users" class="admin-nav-icon" />
              用户管理
            </button>
            <button
              :class="['admin-nav-item', { active: subTab === 'departments' }]"
              @click="switchTab('departments')"
            >
              <Icons name="building" class="admin-nav-icon" />
              部门管理
            </button>
            <button class="admin-nav-item disabled" disabled title="敬请期待">
              <Icons name="shield" class="admin-nav-icon" />
              权限管理
            </button>
            <button
              v-if="me?.is_superuser"
              :class="['admin-nav-item', { active: subTab === 'storage' }]"
              @click="switchTab('storage')"
            >
              <Icons name="database" class="admin-nav-icon" />
              存储管理
            </button>
            <button
              v-if="me?.is_superuser"
              :class="['admin-nav-item', { active: subTab === 'audit' }]"
              @click="switchTab('audit')"
            >
              <Icons name="file-text" class="admin-nav-icon" />
              系统日志
            </button>
            <button
              v-if="me?.is_superuser"
              :class="['admin-nav-item', { active: subTab === 'notify' }]"
              @click="switchTab('notify')"
            >
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

          <!-- 存储管理 -->
          <div v-if="subTab === 'storage'" class="admin-page">
            <div class="admin-page-header">
              <div>
                <h2 class="admin-page-title">存储管理</h2>
                <p class="admin-page-desc">监控和管理系统存储空间使用情况</p>
              </div>
            </div>

            <div class="admin-stats">
              <div class="admin-stat-card">
                <div class="admin-stat-label">总存储容量</div>
                <div class="admin-stat-value">{{ storageStats?.total_display || '500 GB' }}</div>
                <div class="admin-stat-extra text-muted">企业总配额</div>
              </div>
              <div class="admin-stat-card">
                <div class="admin-stat-label">已使用空间</div>
                <div class="admin-stat-value">{{ storageStats?.used_display || '0 B' }}</div>
                <div class="admin-stat-extra text-green">
                  {{ Math.round(storageStats?.percent || 0) }}% 使用率
                </div>
              </div>
              <div class="admin-stat-card">
                <div class="admin-stat-label">剩余空间</div>
                <div class="admin-stat-value">
                  {{ remainingStorageDisplay }}
                </div>
                <div class="admin-stat-extra text-muted">可用容量</div>
              </div>
              <div class="admin-stat-card">
                <div class="admin-stat-label">总文件数</div>
                <div class="admin-stat-value">
                  {{ totalFileCountDisplay }}
                </div>
                <div class="admin-stat-extra text-blue">按文件类型统计</div>
              </div>
            </div>

            <div class="card admin-storage-overview-card">
              <div class="admin-storage-overview-header">
                <div class="admin-storage-overview-left">
                  <h3 class="admin-storage-card-title">整体存储使用情况</h3>
                  <p class="admin-storage-overview-sub">
                    {{ storageStats?.used_display || '0 B' }} / {{ storageStats?.total_display || '500 GB' }}
                  </p>
                  <div class="admin-storage-bar">
                    <div
                      class="admin-storage-bar-inner"
                      :style="{ width: Math.min(storageStats?.percent || 0, 100) + '%' }"
                    />
                  </div>
                </div>
                <div class="admin-storage-overview-percent">
                  {{ Math.round(storageStats?.percent || 0) }}%
                </div>
              </div>
              <div
                v-if="(storageStats?.percent || 0) > 80"
                class="admin-storage-overview-alert"
              >
                <Icons name="alert-circle" class="admin-storage-alert-icon" />
                <span>存储空间使用率较高，建议扩容或清理无用文件</span>
              </div>
            </div>

            <div class="card admin-storage-tabs">
              <div class="admin-storage-tabs-header">
                <button
                  :class="['admin-storage-tab', { active: storageInnerTab === 'departments' }]"
                  @click="storageInnerTab = 'departments'"
                >
                  部门存储
                </button>
                <button
                  :class="['admin-storage-tab', { active: storageInnerTab === 'users' }]"
                  @click="storageInnerTab = 'users'"
                >
                  用户存储
                </button>
                <button
                  :class="['admin-storage-tab', { active: storageInnerTab === 'filetypes' }]"
                  @click="storageInnerTab = 'filetypes'"
                >
                  文件类型
                </button>
              </div>

              <!-- 部门存储 -->
              <div v-if="storageInnerTab === 'departments'" class="admin-storage-section">
                <div class="admin-toolbar">
                  <div class="admin-search-wrap">
                    <Icons name="search" class="admin-search-icon" />
                    <input
                      v-model="storageSearchKeyword"
                      type="text"
                      placeholder="搜索部门名称..."
                      class="admin-search-input"
                    />
                  </div>
                  <select v-model="storageDeptStatus" class="admin-select">
                    <option value="all">全部状态</option>
                    <option value="normal">正常</option>
                    <option value="warning">警告</option>
                    <option value="critical">超限</option>
                  </select>
                </div>
                <div class="admin-table-wrap">
                  <table class="admin-table">
                    <thead>
                      <tr>
                        <th>部门名称</th>
                        <th>存储使用</th>
                        <th class="admin-th-center">使用率</th>
                        <th class="admin-th-center">用户数</th>
                        <th class="admin-th-center">文件数量</th>
                        <th class="admin-th-center">增长趋势</th>
                        <th class="text-right">操作</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="row in filteredDeptStorage" :key="row.id" class="admin-table-row">
                        <td>
                          <div class="admin-storage-dept-name">
                            <Icons name="building" class="admin-stat-icon" />
                            <span>{{ row.name }}</span>
                          </div>
                        </td>
                        <td>
                          <div class="admin-storage-usage">
                            <div class="admin-storage-usage-main">
                              {{ row.used_display }} / {{ row.total_display }}
                            </div>
                            <div class="admin-storage-bar">
                              <div
                                class="admin-storage-bar-inner"
                                :class="['status-' + row.status]"
                                :style="{ width: Math.min(row.percent, 100) + '%' }"
                              />
                            </div>
                          </div>
                        </td>
                        <td class="admin-cell-center">
                          <span :class="['admin-badge', 'badge-' + row.status]">
                            {{ row.percent.toFixed(1) }}%
                          </span>
                        </td>
                        <td class="admin-cell-center">
                          {{ row.users }}
                        </td>
                        <td class="admin-cell-center">
                          {{ row.file_count.toLocaleString('zh-CN') }}
                        </td>
                        <td class="admin-cell-center">
                          <span class="text-green">{{ row.trend }}</span>
                        </td>
                        <td class="text-right">
                          <button
                            type="button"
                            class="admin-action-btn"
                            @click="openDeptQuotaModal(row)"
                          >
                            调整配额
                          </button>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                  <p v-if="!filteredDeptStorage.length" class="admin-empty">暂无部门存储数据</p>
                </div>
              </div>

              <!-- 用户存储 -->
              <div v-else-if="storageInnerTab === 'users'" class="admin-storage-section">
                <div class="admin-toolbar">
                  <div class="admin-search-wrap">
                    <Icons name="search" class="admin-search-icon" />
                    <input
                      v-model="storageSearchKeyword"
                      type="text"
                      placeholder="搜索用户名称或部门..."
                      class="admin-search-input"
                    />
                  </div>
                  <select v-model="storageUserSort" class="admin-select">
                    <option value="usage-desc">使用量降序</option>
                    <option value="usage-asc">使用量升序</option>
                    <option value="name">按姓名</option>
                  </select>
                </div>
                <div class="admin-table-wrap">
                  <table class="admin-table">
                    <thead>
                      <tr>
                        <th>用户</th>
                        <th class="admin-th-center">部门</th>
                        <th>存储使用</th>
                        <th class="admin-th-center">使用率</th>
                        <th class="admin-th-center">文件数量</th>
                        <th class="admin-th-center">最后上传</th>
                        <th class="text-right">操作</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="row in filteredUserStorage" :key="row.id" class="admin-table-row">
                        <td>
                          <div class="admin-user-info">
                            <div class="admin-user-name">{{ row.name }}</div>
                          </div>
                        </td>
                        <td class="admin-cell-center">
                          {{ row.department_name || '-' }}
                        </td>
                        <td>
                          <div class="admin-storage-usage">
                            <div class="admin-storage-usage-main">
                              {{ row.used_display }} / {{ row.total_display }}
                            </div>
                            <div class="admin-storage-bar">
                              <div
                                class="admin-storage-bar-inner"
                                :style="{ width: Math.min(row.percent, 100) + '%' }"
                              />
                            </div>
                          </div>
                        </td>
                        <td class="admin-cell-center">
                          <span
                            :class="[
                              'admin-badge',
                              row.percent >= 90 ? 'badge-critical' : row.percent >= 70 ? 'badge-warning' : 'badge-ok',
                            ]"
                          >
                            {{ row.percent.toFixed(1) }}%
                          </span>
                        </td>
                        <td class="admin-cell-center">
                          {{ row.file_count.toLocaleString('zh-CN') }}
                        </td>
                        <td class="admin-cell-center">
                          {{ formatDate(row.last_upload) }}
                        </td>
                        <td class="text-right">
                          <button
                            type="button"
                            class="admin-action-btn"
                            @click="openUserQuotaModal(row)"
                          >
                            调整配额
                          </button>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                  <p v-if="!filteredUserStorage.length" class="admin-empty">暂无用户存储数据</p>
                </div>
              </div>

              <!-- 文件类型 -->
              <div v-else class="admin-storage-section">
                <div class="admin-table-wrap admin-storage-filetypes">
                  <div class="admin-storage-filetypes-grid">
                    <div class="admin-storage-card">
                      <h3 class="admin-storage-card-title">文件类型分布（按数量）</h3>
                      <div class="admin-storage-filetype-list">
                        <div
                          v-for="stat in fileTypeStorage"
                          :key="'count-' + stat.type"
                          class="admin-storage-filetype-row"
                        >
                          <div class="admin-storage-filetype-meta">
                            <span class="admin-storage-dot" />
                            <span class="admin-storage-filetype-name">{{ stat.type }}</span>
                          </div>
                          <div class="admin-storage-filetype-values">
                            <span class="admin-storage-filetype-count">
                              {{ stat.count.toLocaleString('zh-CN') }}
                            </span>
                          </div>
                          <div class="admin-storage-bar">
                            <div
                              class="admin-storage-bar-inner"
                              :style="{ width: stat.percent_count.toFixed(1) + '%' }"
                            />
                          </div>
                        </div>
                      </div>
                    </div>
                    <div class="admin-storage-card">
                      <h3 class="admin-storage-card-title">文件类型分布（按大小）</h3>
                      <div class="admin-storage-filetype-list">
                        <div
                          v-for="stat in fileTypeStorage"
                          :key="'size-' + stat.type"
                          class="admin-storage-filetype-row"
                        >
                          <div class="admin-storage-filetype-meta">
                            <span class="admin-storage-dot" />
                            <span class="admin-storage-filetype-name">{{ stat.type }}</span>
                          </div>
                          <div class="admin-storage-filetype-values">
                            <span class="admin-storage-filetype-count">
                              {{ stat.size_display }}
                            </span>
                          </div>
                          <div class="admin-storage-bar">
                            <div
                              class="admin-storage-bar-inner"
                              :style="{ width: stat.percent_size.toFixed(1) + '%' }"
                            />
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
                <p v-if="!fileTypeStorage.length" class="admin-empty">暂无文件类型统计数据</p>
              </div>
            </div>
          </div>

          <!-- 系统日志 -->
          <div v-if="subTab === 'audit'" class="admin-page">
            <div class="admin-page-header">
              <div>
                <h2 class="admin-page-title">系统日志</h2>
                <p class="admin-page-desc">查看和分析系统操作日志</p>
              </div>
            </div>

            <!-- 统计卡片 -->
            <div class="admin-stats">
              <div class="admin-stat-card">
                <div class="admin-stat-label">总操作数</div>
                <div class="admin-stat-value">{{ auditList.length }}</div>
                <div class="admin-stat-extra text-muted">当前加载的系统操作记录数量</div>
              </div>
              <div class="admin-stat-card">
                <div class="admin-stat-label">涉及用户</div>
                <div class="admin-stat-value">{{ auditUniqueUsersCount }}</div>
                <div class="admin-stat-extra text-muted">参与过上述操作的不同用户数</div>
              </div>
              <div class="admin-stat-card">
                <div class="admin-stat-label">文件相关操作</div>
                <div class="admin-stat-value">{{ auditFileOpsCount }}</div>
                <div class="admin-stat-extra text-muted">例如上传、下载、删除、重命名等文件操作次数</div>
              </div>
              <div class="admin-stat-card">
                <div class="admin-stat-label">库相关操作</div>
                <div class="admin-stat-value">{{ auditLibraryOpsCount }}</div>
                <div class="admin-stat-extra text-muted">例如新建、修改、删除文件库等操作次数</div>
              </div>
            </div>

            <!-- 过滤和操作栏 -->
            <div class="card audit-toolbar">
              <div class="audit-toolbar-inner">
                <div class="audit-filters-left">
                  <div class="audit-search">
                    <input
                      v-model="auditSearch"
                      type="text"
                      placeholder="搜索用户、操作或详情..."
                      class="audit-search-input"
                    />
                  </div>

                  <select v-model="auditActionFilter" class="audit-select">
                    <option value="all">全部操作</option>
                    <option value="file">文件操作</option>
                    <option value="user">用户管理</option>
                    <option value="share">分享操作</option>
                    <option value="permission">权限变更</option>
                    <option value="login">登录日志</option>
                    <option value="system">系统操作</option>
                  </select>

                  <select v-model="auditStatusFilter" class="audit-select">
                    <option value="all">全部状态</option>
                    <option value="success">成功</option>
                    <option value="failed">失败</option>
                  </select>

                  <input
                    v-model="auditStartDate"
                    type="date"
                    class="audit-date-input"
                  />
                  <input
                    v-model="auditEndDate"
                    type="date"
                    class="audit-date-input"
                  />

                  <button type="button" class="admin-btn-secondary" @click="refreshAuditFirstPage">
                    查询
                  </button>
                </div>

                <div class="audit-toolbar-right">
                  <button type="button" class="admin-btn-secondary" @click="exportAuditCsv">
                    导出日志
                  </button>
                </div>
              </div>
            </div>

            <!-- 日志列表 -->
            <div class="card audit-table-wrap">
              <div class="audit-table-scroll">
                <table class="audit-table">
                  <thead>
                    <tr>
                      <th>时间</th>
                      <th>用户</th>
                      <th>部门</th>
                      <th>操作</th>
                      <th>目标</th>
                      <th>IP 地址</th>
                      <th>状态</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr
                      v-for="log in filteredAuditList"
                      :key="log.id"
                      class="audit-row"
                    >
                      <td class="audit-cell-muted">
                        {{ formatDate(log.created_at) }}
                      </td>
                      <td class="audit-cell-strong">
                        {{ log.username || '-' }}
                      </td>
                      <td class="audit-cell">
                        {{ log.department_name || '-' }}
                      </td>
                      <td class="audit-cell audit-cell-op">
                        <span
                          :class="['audit-tag', auditActionTagClass(log)]"
                        >
                          {{ formatAuditActionLabel(log) }}
                        </span>
                      </td>
                      <td class="audit-cell">
                        {{ formatAuditDetailLabel(log) }}
                      </td>
                      <td class="audit-cell">
                        {{ log.ip_address || '-' }}
                      </td>
                      <td class="audit-cell">
                        <span :class="['audit-status', auditStatusClass(log)]">
                          {{ formatAuditStatusLabel(log) }}
                        </span>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <p v-if="!filteredAuditList.length" class="admin-empty">
                暂无审计记录，或调整筛选条件后查询。
              </p>
              <div class="audit-pagination" v-else>
                <div class="audit-pagination-info">
                  第 {{ auditPage }} 页，每页 {{ auditPageSize }} 条
                </div>
                <div class="audit-pagination-actions">
                  <button
                    type="button"
                    class="admin-btn-secondary"
                    :disabled="auditPage <= 1"
                    @click="goPrevAuditPage"
                  >
                    上一页
                  </button>
                  <button
                    type="button"
                    class="admin-btn-secondary"
                    :disabled="!auditHasMore"
                    @click="goNextAuditPage"
                  >
                    下一页
                  </button>
                </div>
              </div>
            </div>
          </div>

          <!-- 通知设置 / 通知管理 -->
          <div v-if="subTab === 'notify'" class="admin-page">
            <div class="admin-page-header">
              <div>
                <h2 class="admin-page-title">通知管理</h2>
                <p class="admin-page-desc">管理系统通知模板、发送历史和通知开关</p>
              </div>
              <button type="button" class="admin-btn-primary" @click="showSendDialog = true">
                <Icons name="send" class="admin-btn-icon" />
                发送通知
              </button>
            </div>

            <div class="admin-stats">
              <div class="admin-stat-card">
                <div class="admin-stat-label">通知模板</div>
                <div class="admin-stat-value">{{ notifyTemplates.length }}</div>
                <div class="admin-stat-extra text-muted">
                  {{ notifyTemplates.filter(t => t.enabled).length }} 个已启用
                </div>
              </div>
              <div class="admin-stat-card">
                <div class="admin-stat-label">历史发送</div>
                <div class="admin-stat-value">{{ notifyHistory.length }}</div>
                <div class="admin-stat-extra text-green">最近 {{ notifyHistory.length }} 条记录</div>
              </div>
              <div class="admin-stat-card">
                <div class="admin-stat-label">系统通知开关</div>
                <div class="admin-stat-value">{{ notifySettings.length }}</div>
                <div class="admin-stat-extra text-muted">可配置通知项</div>
              </div>
              <div class="admin-stat-card">
                <div class="admin-stat-label">最近一次发送</div>
                <div class="admin-stat-value">
                  {{ notifyHistory[0]?.title || '暂无' }}
                </div>
                <div class="admin-stat-extra text-muted">
                  {{ notifyHistory[0]?.sentTime ? formatDate(notifyHistory[0].sentTime) : '——' }}
                </div>
              </div>
            </div>

            <div class="card admin-storage-tabs">
              <div class="admin-storage-tabs-header">
                <button
                  :class="['admin-storage-tab', { active: notifyInnerTab === 'templates' }]"
                  @click="notifyInnerTab = 'templates'"
                >
                  通知模板
                </button>
                <button
                  :class="['admin-storage-tab', { active: notifyInnerTab === 'history' }]"
                  @click="notifyInnerTab = 'history'"
                >
                  发送历史
                </button>
                <button
                  :class="['admin-storage-tab', { active: notifyInnerTab === 'settings' }]"
                  @click="notifyInnerTab = 'settings'"
                >
                  通知设置
                </button>
              </div>

              <!-- 模板列表 -->
              <div v-if="notifyInnerTab === 'templates'" class="admin-notify-section">
                <div class="admin-notify-templates-grid">
                  <div
                    v-for="tpl in notifyTemplates"
                    :key="tpl.id"
                    class="admin-notify-template-card"
                  >
                    <div class="admin-notify-template-header">
                      <div class="admin-notify-template-left">
                        <div class="admin-notify-template-icon">
                          <Icons
                            :name="['file','database','lock','check-circle','settings','bell'].includes(tpl.icon) ? tpl.icon : 'bell'"
                            class="admin-notify-template-icon-svg"
                          />
                        </div>
                        <div>
                          <div class="admin-notify-template-title-wrap">
                            <h3 class="admin-notify-template-name">{{ tpl.name }}</h3>
                            <span
                              :class="[
                                'admin-badge',
                                tpl.enabled ? 'badge-ok' : 'badge-disabled',
                              ]"
                            >
                              {{ tpl.enabled ? '启用中' : '已禁用' }}
                            </span>
                          </div>
                          <p class="admin-notify-template-sub">{{ tpl.title }}</p>
                        </div>
                      </div>
                    </div>
                    <div class="admin-notify-template-body">
                      <p class="admin-notify-template-content">{{ tpl.content }}</p>
                    </div>
                    <div class="admin-notify-template-footer">
                      <div class="admin-notify-channels">
                        <span
                          v-if="tpl.channels?.includes('system')"
                          class="admin-notify-chip chip-system"
                        >
                          <Icons name="bell" class="admin-notify-chip-icon" />
                          系统通知
                        </span>
                        <span
                          v-if="tpl.channels?.includes('email')"
                          class="admin-notify-chip chip-email"
                        >
                          <Icons name="mail" class="admin-notify-chip-icon" />
                          邮件
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <!-- 发送历史 -->
              <div v-else-if="notifyInnerTab === 'history'" class="admin-notify-section">
                <div class="admin-table-wrap">
                  <table class="admin-table">
                    <thead>
                      <tr>
                        <th>通知标题</th>
                        <th>内容</th>
                        <th class="admin-th-center">接收人数</th>
                        <th class="admin-th-center">发送时间</th>
                        <th class="admin-th-center">发送渠道</th>
                        <th class="admin-th-center">状态</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="row in notifyHistory" :key="row.id" class="admin-table-row">
                        <td>
                          <div class="admin-user-name">{{ row.title }}</div>
                        </td>
                        <td>
                          <div class="admin-cell-ellipsis">{{ row.content }}</div>
                        </td>
                        <td class="admin-cell-center">
                          <div class="admin-notify-recipients">
                            <Icons name="users" class="admin-stat-icon" />
                            {{ row.recipients }}
                          </div>
                        </td>
                        <td class="admin-cell-center">
                          {{ formatDate(row.sentTime) }}
                        </td>
                        <td class="admin-cell-center">
                          <div class="admin-notify-chips-row">
                            <span
                              v-if="row.channels?.includes('system')"
                              class="admin-notify-chip chip-system"
                            >
                              <Icons name="bell" class="admin-notify-chip-icon" />
                              系统
                            </span>
                            <span
                              v-if="row.channels?.includes('email')"
                              class="admin-notify-chip chip-email"
                            >
                              <Icons name="mail" class="admin-notify-chip-icon" />
                              邮件
                            </span>
                          </div>
                        </td>
                        <td class="admin-cell-center">
                          <span class="admin-badge badge-ok">已发送</span>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                  <p v-if="!notifyHistory.length" class="admin-empty">暂无发送记录</p>
                </div>
              </div>

              <!-- 通知设置 -->
              <div v-else class="admin-notify-section">
                <div
                  v-for="cat in groupedNotifySettings"
                  :key="cat.category"
                  class="admin-notify-settings-card"
                >
                  <h3 class="admin-notify-settings-title">
                    <Icons name="bell" class="admin-notify-settings-icon" />
                    {{ cat.category }}
                  </h3>
                  <div class="admin-notify-settings-list">
                    <div
                      v-for="s in cat.items"
                      :key="s.id"
                      class="admin-notify-setting-row"
                    >
                      <div class="admin-notify-setting-left">
                        <div class="admin-notify-setting-name">{{ s.name }}</div>
                        <div class="admin-notify-setting-desc">
                          {{ s.enabled ? '已启用' : '已禁用' }}
                        </div>
                      </div>
                      <label class="switch">
                        <input
                          type="checkbox"
                          :checked="s.enabled"
                          @change="toggleNotifySetting(s)"
                        />
                        <span class="slider" />
                      </label>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- 发送通知弹窗 -->
            <div v-if="showSendDialog" class="modal">
              <div class="card user-modal-card">
                <h3>发送通知</h3>
                <p class="admin-notify-send-desc">创建一次性系统通知，立即发送给选定用户范围。</p>
                <div class="user-modal-grid admin-notify-send-grid">
                  <div class="form-group form-group-full">
                    <label>通知标题</label>
                    <input
                      v-model="sendForm.title"
                      placeholder="请输入通知标题，例如「系统维护通知」"
                    />
                  </div>
                  <div class="form-group form-group-full">
                    <label>通知内容</label>
                    <textarea
                      v-model="sendForm.content"
                      rows="4"
                      class="admin-textarea"
                      placeholder="请输入通知内容，例如维护时间、影响范围等"
                    />
                  </div>
                  <div class="form-group">
                    <label>发送对象</label>
                    <select v-model="sendForm.target" class="admin-select">
                      <option value="all">所有用户</option>
                      <option value="department">指定部门（当前按全部部门处理）</option>
                      <option value="custom">指定用户（当前按全部用户处理）</option>
                    </select>
                  </div>
                  <div class="form-group">
                    <label>发送渠道</label>
                    <div class="admin-notify-channel-options">
                      <div class="admin-notify-channel-option">
                        <input
                          id="notify-channel-system"
                          type="checkbox"
                          class="admin-notify-checkbox"
                          :checked="sendForm.channels.includes('system')"
                          @change="onToggleChannel('system', $event.target.checked)"
                        />
                        <label for="notify-channel-system" class="admin-notify-channel-label">
                          系统通知
                        </label>
                      </div>
                      <div class="admin-notify-channel-option">
                        <input
                          id="notify-channel-email"
                          type="checkbox"
                          class="admin-notify-checkbox"
                          :checked="sendForm.channels.includes('email')"
                          @change="onToggleChannel('email', $event.target.checked)"
                        />
                        <label for="notify-channel-email" class="admin-notify-channel-label">
                          邮件
                        </label>
                      </div>
                    </div>
                    <p class="admin-notify-send-hint">建议至少选择「系统通知」，重要公告可同时勾选邮件。</p>
                  </div>
                </div>
                <p v-if="err" class="text-danger">{{ err }}</p>
                <div class="modal-actions">
                  <button
                    class="primary"
                    :disabled="sendingNotify"
                    @click="doSendNotification"
                  >
                    {{ sendingNotify ? '发送中...' : '立即发送' }}
                  </button>
                  <button @click="closeSendDialog">取消</button>
                </div>
              </div>
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

    <!-- 部门配额调整 -->
    <div v-if="showDeptQuota" class="modal">
      <div class="card">
        <h3>调整部门存储配额</h3>
        <p style="margin-bottom:8px; color:#6b7280; font-size:14px;">
          部门：{{ editingDeptQuotaRow?.name }}
        </p>
        <div class="form-group">
          <label>配额（GB）</label>
          <input
            v-model="deptQuotaInput"
            type="number"
            min="1"
            step="1"
            placeholder="例如 100"
            style="width:100%; margin-bottom:8px;"
          />
        </div>
        <p v-if="err" class="text-danger">{{ err }}</p>
        <div class="modal-actions">
          <button class="primary" @click="saveDeptQuota">保存</button>
          <button @click="showDeptQuota = false; editingDeptQuotaRow = null; deptQuotaInput = ''; err = ''">
            取消
          </button>
        </div>
      </div>
    </div>

    <!-- 用户配额调整 -->
    <div v-if="showUserQuota" class="modal">
      <div class="card">
        <h3>调整用户存储配额</h3>
        <p style="margin-bottom:8px; color:#6b7280; font-size:14px;">
          用户：{{ editingUserQuotaRow?.name }}
        </p>
        <div class="form-group">
          <label>配额（GB）</label>
          <input
            v-model="userQuotaInput"
            type="number"
            min="1"
            step="1"
            placeholder="例如 100"
            style="width:100%; margin-bottom:8px;"
          />
        </div>
        <p v-if="err" class="text-danger">{{ err }}</p>
        <div class="modal-actions">
          <button class="primary" @click="saveUserQuota">保存</button>
          <button @click="showUserQuota = false; editingUserQuotaRow = null; userQuotaInput = ''; err = ''">
            取消
          </button>
        </div>
      </div>
    </div>

    <!-- 编辑部门 -->
    <div v-if="showEditDept" class="modal">
      <div class="card">
        <h3>编辑部门</h3>
        <div class="form-group">
          <label>部门名称</label>
          <input v-model="editDeptName" placeholder="部门名称" style="width:100%; margin-bottom:8px;" />
        </div>
        <div class="form-group">
          <label>部门负责人 <span class="label-opt">选填</span></label>
          <select v-model="editDeptLeaderId" class="admin-select">
            <option :value="0">无负责人</option>
            <option
              v-for="u in editDeptMembers"
              :key="u.id"
              :value="u.id"
            >
              {{ u.username || u.email || ('用户 #' + u.id) }}
            </option>
          </select>
          <p v-if="!editDeptMembers.length" class="admin-hint">
            该部门暂无成员，保存后将仅更新部门名称。
          </p>
        </div>
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

    <!-- 重置密码 -->
    <div v-if="showResetPassword" class="modal">
      <div class="card user-modal-card">
        <h3>重置密码</h3>
        <p style="margin-top:8px; margin-bottom:16px; color:#6b7280; font-size:14px;">
          用户：{{ resettingUser?.username }}（{{ resettingUser?.email || '无邮箱' }}）
        </p>
        <div class="form-group">
          <label>新密码 <span class="label-opt">必填</span></label>
          <input
            v-model="resetPasswordInput"
            type="password"
            placeholder="8+ 位，包含大小写字母、数字和特殊字符"
          />
        </div>
        <p v-if="resetPasswordError" class="text-danger">{{ resetPasswordError }}</p>
        <div class="modal-actions">
          <button class="primary" @click="confirmResetPassword">确定</button>
          <button @click="closeResetPassword">取消</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import * as XLSX from 'xlsx'
import * as api from '../api/client'
import Icons from '../components/Icons.vue'
import DepartmentTableRow from '../components/DepartmentTableRow.vue'

const router = useRouter()
const route = useRoute()

const me = ref(null)
const subTab = ref('users')
const sysSearchKeyword = ref('')
const userFilterStatus = ref('')
const userFilterRole = ref('')
const userList = ref([])
const storageStats = ref(null)
const deptStorage = ref([])
const userStorage = ref([])
const fileTypeStorage = ref([])
const deptTreeForTable = ref([])
const auditList = ref([])
const auditSearch = ref('')
const auditActionFilter = ref('all')
const auditStatusFilter = ref('all')
const auditStartDate = ref('')
const auditEndDate = ref('')
const auditPage = ref(1)
const auditPageSize = 50
const auditHasMore = ref(false)

const storageInnerTab = ref('departments')
const storageSearchKeyword = ref('')
const storageDeptStatus = ref('all')
const storageUserSort = ref('usage-desc')

// 通知管理
const notifyInnerTab = ref('templates')
const notifyTemplates = ref([])
const notifyHistory = ref([])
const notifySettings = ref([])
const showSendDialog = ref(false)
const sendingNotify = ref(false)
const sendForm = ref({
  title: '',
  content: '',
  target: 'all',
  channels: ['system'],
})

// 部门弹窗相关
const showAddRootDept = ref(false)
const newRootDeptName = ref('')
const showAddSubDept = ref(false)
const addSubDeptParent = ref(null)
const addSubDeptName = ref('')
const showEditDept = ref(false)
const editDeptNode = ref(null)
const editDeptName = ref('')
const editDeptLeaderId = ref(0)
const editDeptMembers = ref([])

// 存储配额弹窗相关
const showDeptQuota = ref(false)
const editingDeptQuotaRow = ref(null)
const deptQuotaInput = ref('')
const showUserQuota = ref(false)
const editingUserQuotaRow = ref(null)
const userQuotaInput = ref('')

// 创建用户相关
const showCreateUser = ref(false)
const newUserEmail = ref('')
const newUserUsername = ref('')
const newUserPassword = ref('')
const newUserDeptId = ref(null)
const newUserRole = ref('user')

// 重置密码相关
const showResetPassword = ref(false)
const resettingUser = ref(null)
const resetPasswordInput = ref('')
const resetPasswordError = ref('')

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

const filteredDeptStorage = computed(() => {
  const kw = storageSearchKeyword.value?.trim().toLowerCase()
  let list = deptStorage.value || []
  if (kw) {
    list = list.filter((d) => (d.name || '').toLowerCase().includes(kw))
  }
  if (storageDeptStatus.value !== 'all') {
    list = list.filter((d) => d.status === storageDeptStatus.value)
  }
  return list
})

const filteredUserStorage = computed(() => {
  const kw = storageSearchKeyword.value?.trim().toLowerCase()
  let list = [...(userStorage.value || [])]
  if (kw) {
    list = list.filter(
      (u) =>
        (u.name || '').toLowerCase().includes(kw) ||
        (u.department_name || '').toLowerCase().includes(kw),
    )
  }
  if (storageUserSort.value === 'usage-desc') {
    list.sort((a, b) => (b.used_bytes || 0) - (a.used_bytes || 0))
  } else if (storageUserSort.value === 'usage-asc') {
    list.sort((a, b) => (a.used_bytes || 0) - (b.used_bytes || 0))
  } else if (storageUserSort.value === 'name') {
    list.sort((a, b) => (a.name || '').localeCompare(b.name || ''))
  }
  return list
})

const remainingStorageDisplay = computed(() => {
  if (!storageStats.value) return '0 B'
  const total = storageStats.value.total_bytes || 0
  const used = storageStats.value.used_bytes || 0
  const remain = Math.max(total - used, 0)
  return formatBytes(remain)
})

// 系统日志统计与过滤
const auditUniqueUsersCount = computed(() => {
  const set = new Set()
  for (const log of auditList.value || []) {
    if (log.username) set.add(log.username)
  }
  return set.size
})

const auditFileOpsCount = computed(() =>
  (auditList.value || []).filter(l => l.resource_type === 'file').length,
)

const auditLibraryOpsCount = computed(() =>
  (auditList.value || []).filter(l => l.resource_type === 'library').length,
)

function auditInferType(log) {
  const action = (log.action || '').toLowerCase()
  const rtype = (log.resource_type || '').toLowerCase()
  if (rtype === 'file' || /upload|download|delete|restore|permanent_delete/.test(action)) return 'file'
  if (rtype === 'library' || /library/.test(action)) return 'file'
  if (/user/.test(action) || /create_user|update_user|change_password/.test(action)) return 'user'
  if (/share/.test(action)) return 'share'
  if (/permission|role/.test(action)) return 'permission'
  if (/login|logout/.test(action)) return 'login'
  return 'system'
}

function auditActionTagClass(log) {
  const a = (log.action || '').toLowerCase()
  if (a.includes('upload')) return 'tag-file-upload'
  if (a.includes('download')) return 'tag-file-download'
  if (a.includes('restore')) return 'tag-file-restore'
  if (a.includes('permanent_delete') || (a.includes('delete') && !a.includes('restore'))) return 'tag-file-delete'
  if (a.includes('rename')) return 'tag-file-rename'
  if (a.includes('create_library') || a.includes('update_library') || (a.includes('delete') && a.includes('library')))
    return 'tag-library'
  if (a.includes('add_library_member') || a.includes('remove_library_member')) return 'tag-permission'
  if (a.includes('share')) return 'tag-share'
  if (a.includes('change_password')) return 'tag-security'
  if (a.includes('create_user') || a.includes('update_user')) return 'tag-user'
  if (a.includes('login_failed')) return 'tag-login-failed'
  if (a.includes('login')) return 'tag-login'
  if (a.includes('notification')) return 'tag-notify'
  if (a.includes('quota')) return 'tag-quota'

  const t = auditInferType(log)
  if (t === 'file') return 'tag-file'
  if (t === 'user') return 'tag-user'
  if (t === 'share') return 'tag-share'
  if (t === 'permission') return 'tag-permission'
  if (t === 'login') return 'tag-login'
  if (t === 'system') return 'tag-system'
  return 'tag-default'
}

function formatAuditActionLabel(log) {
  const a = (log.action || '').toLowerCase()
  if (!a) return '其他操作'
  if (a.includes('upload')) return '上传文件'
  if (a.includes('download')) return '下载文件'
  if (a.includes('restore')) return '恢复文件'
  if (a.includes('permanent_delete')) return '彻底删除'
  if (a.includes('rename')) return '重命名'
  if (a.includes('delete') && a.includes('library')) return '删除文件库'
  if (a.includes('delete') && !a.includes('library')) return '删除文件'
  if (a.includes('create_library')) return '新建文件库'
  if (a.includes('update_library')) return '修改文件库'
  if (a.includes('add_library_member')) return '添加文件库成员'
  if (a.includes('remove_library_member')) return '移除文件库成员'
  if (a.includes('share')) return '分享文件或文件库'
  if (a.includes('change_password')) return '修改密码'
  if (a.includes('create_user')) return '创建用户'
  if (a.includes('update_user')) return '修改用户'
  if (a.includes('login_failed')) return '登录失败'
  if (a.includes('login')) return '登录'
  if (a.includes('notification')) return '发送通知'
  if (a.includes('quota')) return '调整存储配额'
  return log.action || '其他操作'
}

function formatAuditResourceLabel(log) {
  const rt = (log.resource_type || '').toLowerCase()
  const id = log.resource_id
  if (rt === 'file') return id ? `文件 #${id}` : '文件'
  if (rt === 'library') return id ? `文件库 #${id}` : '文件库'
  if (rt === 'user') return id ? `用户 #${id}` : '用户'
  if (rt === 'notification') return '通知'
  if (rt) return rt
  return '系统'
}

function extractNameFromDetail(log) {
  const detail = log.detail || ''
  // 常见格式示例：
  // - "path=/docs/paper.pdf"
  // - "library_name=技术文档库"
  // - "user=张三"
  // - "file=项目文档.pdf"
  const patterns = [
    /file_name=([^;，,]+)/i,
    /filename=([^;，,]+)/i,
    /file=([^;，,]+)/i,
    /library_name=([^;，,]+)/i,
    /库名[:：]\s*([^;，,]+)/,
    /路径[:：]\s*([^;，,]+)/,
    /path=([^;，,]+)/i,
  ]
  for (const p of patterns) {
    const m = detail.match(p)
    if (m && m[1]) {
      const v = m[1].trim()
      if (v) return v
    }
  }
  return ''
}

function formatAuditTargetLabel(log) {
  // 优先从 detail 中提取更具体的目标名称，其次回退到资源类型 + ID
  const name = extractNameFromDetail(log)
  if (name) return name
  return formatAuditResourceLabel(log)
}

function formatAuditDetailLabel(log) {
  const a = (log.action || '').toLowerCase()
  const user = log.username || '某用户'
  const target = formatAuditTargetLabel(log)
  const dept = log.department_name || ''

  if (a.includes('upload')) {
    return `${user} 在${dept ? '「' + dept + '」中' : ''}上传了 ${target}`
  }
  if (a.includes('download')) {
    return `${user} 下载了 ${target}`
  }
  if (a.includes('restore')) {
    return `${user} 从回收站恢复了 ${target}`
  }
  if (a.includes('permanent_delete')) {
    return `${user} 彻底删除了 ${target}`
  }
  if (a.includes('delete') && a.includes('library')) {
    return `${user} 删除了文件库 ${target}`
  }
  if (a.includes('delete') && !a.includes('library')) {
    return `${user} 删除了 ${target}`
  }
  if (a.includes('create_library')) {
    return `${user} 新建了文件库 ${target}`
  }
  if (a.includes('update_library')) {
    return `${user} 修改了文件库 ${target}`
  }
  if (a.includes('add_library_member')) {
    return `${user} 为文件库 ${target} 添加了成员`
  }
  if (a.includes('remove_library_member')) {
    return `${user} 从文件库 ${target} 移除了成员`
  }
  if (a.includes('share')) {
    return `${user} 分享了 ${target}`
  }
  if (a.includes('change_password')) {
    return `${user} 修改了账户密码`
  }
  if (a.includes('create_user')) {
    return `${user} 创建了新用户 ${target}`
  }
  if (a.includes('update_user')) {
    return `${user} 修改了用户 ${target} 的信息`
  }
  if (a.includes('login_failed')) {
    return `${user} 登录失败`
  }
  if (a.includes('login')) {
    return `${user} 登录了系统`
  }
  if (a.includes('notification')) {
    return `${user} 发送了通知`
  }
  if (a.includes('quota')) {
    return `${user} 调整了存储配额`
  }

  // 默认回退：直接展示原始 detail 或「无详情」
  return log.detail || '无详情'
}

function auditStatusClass(log) {
  const a = (log.action || '').toLowerCase()
  const detail = (log.detail || '').toLowerCase()
  if (a.includes('failed') || detail.includes('失败') || detail.includes('error')) {
    return 'failed'
  }
  return 'success'
}

function formatAuditStatusLabel(log) {
  const cls = auditStatusClass(log)
  return cls === 'failed' ? '失败' : '成功'
}

const filteredAuditList = computed(() => {
  const kw = (auditSearch.value || '').trim().toLowerCase()
  return (auditList.value || []).filter(log => {
    const type = auditInferType(log)
    const matchesAction = auditActionFilter.value === 'all' || type === auditActionFilter.value
    // 当前审计日志未记录失败状态，这里暂全部视为成功
    const matchesStatus = auditStatusFilter.value === 'all' || auditStatusFilter.value === 'success'
    const text =
      (log.username || '') +
      (log.action || '') +
      (log.detail || '') +
      (log.resource_type || '') +
      (log.resource_id || '')
    const matchesSearch = !kw || text.toLowerCase().includes(kw)
    return matchesAction && matchesStatus && matchesSearch
  })
})

const totalFileCountDisplay = computed(() => {
  if (!fileTypeStorage.value?.length) return '0'
  const total = fileTypeStorage.value.reduce((sum, s) => sum + (s.count || 0), 0)
  return total.toLocaleString('zh-CN')
})

const groupedNotifySettings = computed(() => {
  const groups = {}
  for (const s of notifySettings.value || []) {
    if (!groups[s.category]) {
      groups[s.category] = []
    }
    groups[s.category].push(s)
  }
  return Object.keys(groups).map((k) => ({
    category: k,
    items: groups[k],
  }))
})

async function loadNotifyAll() {
  try {
    const [tpls, his, sets] = await Promise.all([
      api.listNotificationTemplatesAdmin(),
      api.listNotificationHistoryAdmin(),
      api.listNotificationSettingsAdmin(),
    ])
    notifyTemplates.value = tpls || []
    notifyHistory.value = his || []
    notifySettings.value = sets || []
  } catch (e) {
    console.error(e)
  }
}

function formatDate(s) {
  if (!s) return '-'
  try {
    let raw = String(s)
    // 审计日志历史数据可能是不带时区的时间字符串，这里按 UTC 解析后再转北京时间
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

function formatBytes(b) {
  if (!b || b <= 0) return '0 B'
  if (b < 1024) return `${b} B`
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`
  if (b < 1024 * 1024 * 1024) return `${(b / (1024 * 1024)).toFixed(1)} MB`
  return `${(b / (1024 * 1024 * 1024)).toFixed(1)} GB`
}

function openDeptQuotaModal(row) {
  editingDeptQuotaRow.value = row
  // total_display 里是格式化后的字符串，这里直接用一个粗略的 GB 值回填输入框
  const gb = row.total_bytes ? (row.total_bytes / (1024 * 1024 * 1024)) : 0
  deptQuotaInput.value = gb ? gb.toFixed(1) : ''
  err.value = ''
  showDeptQuota.value = true
}

async function saveDeptQuota() {
  if (!editingDeptQuotaRow.value) return
  const v = Number(deptQuotaInput.value)
  if (!v || v <= 0) {
    err.value = '请输入大于 0 的配额（GB）'
    return
  }
  try {
    await api.updateDepartmentQuota(editingDeptQuotaRow.value.id, v)
    showDeptQuota.value = false
    editingDeptQuotaRow.value = null
    deptQuotaInput.value = ''
    await loadDeptStorage()
  } catch (e) {
    err.value = e.message
  }
}

function openUserQuotaModal(row) {
  editingUserQuotaRow.value = row
  const gb = row.total_bytes ? (row.total_bytes / (1024 * 1024 * 1024)) : 0
  userQuotaInput.value = gb ? gb.toFixed(1) : ''
  err.value = ''
  showUserQuota.value = true
}

async function saveUserQuota() {
  if (!editingUserQuotaRow.value) return
  const v = Number(userQuotaInput.value)
  if (!v || v <= 0) {
    err.value = '请输入大于 0 的配额（GB）'
    return
  }
  try {
    await api.updateUserQuota(editingUserQuotaRow.value.id, v)
    showUserQuota.value = false
    editingUserQuotaRow.value = null
    userQuotaInput.value = ''
    await loadUserStorage()
  } catch (e) {
    err.value = e.message
  }
}

async function toggleNotifySetting(s) {
  try {
    const updated = await api.updateNotificationSettingAdmin(s.id, !s.enabled)
    s.enabled = updated.enabled
    // 同步刷新模板与设置，使「通知模板」卡片的启用状态与开关保持一致
    await loadNotifyAll()
  } catch (e) {
    err.value = e.message
  }
}

function onToggleChannel(channel, checked) {
  const cur = sendForm.value.channels || []
  if (checked) {
    if (!cur.includes(channel)) {
      sendForm.value.channels = [...cur, channel]
    }
  } else {
    sendForm.value.channels = cur.filter((c) => c !== channel)
  }
}

async function doSendNotification() {
  err.value = ''
  if (!sendForm.value.title.trim()) {
    err.value = '请输入通知标题'
    return
  }
  if (!sendForm.value.content.trim()) {
    err.value = '请输入通知内容'
    return
  }
  if (!sendForm.value.channels.length) {
    err.value = '请至少选择一个发送渠道'
    return
  }
  try {
    sendingNotify.value = true
    await api.sendAdminNotification({
      title: sendForm.value.title.trim(),
      content: sendForm.value.content.trim(),
      target: sendForm.value.target,
      channels: sendForm.value.channels,
    })
    await loadNotifyAll()
    showSendDialog.value = false
    sendForm.value = {
      title: '',
      content: '',
      target: 'all',
      channels: ['system'],
    }
  } catch (e) {
    err.value = e.message
  } finally {
    sendingNotify.value = false
  }
}

function closeSendDialog() {
  showSendDialog.value = false
  sendForm.value = {
    title: '',
    content: '',
    target: 'all',
    channels: ['system'],
  }
  err.value = ''
}

function goBackHome() {
  router.push('/')
}

function switchTab(name) {
  // 非超级管理员（如部门负责人）仅允许访问「部门管理」
  if (!me.value?.is_superuser && name !== 'departments') {
    return
  }
  subTab.value = name
  if (name === 'users') loadUsers()
  if (name === 'departments') loadDepartments()
  if (name === 'storage') loadStorageAll()
  if (name === 'audit') loadAudit()
  if (name === 'notify') loadNotifyAll()
}

async function loadStorageStats() {
  try {
    storageStats.value = await api.getStorageStats()
  } catch (e) {
    storageStats.value = null
  }
}

async function loadStorageAll() {
  await Promise.all([
    loadStorageStats(),
    loadDeptStorage(),
    loadUserStorage(),
    loadFileTypeStorage(),
  ])
}

async function loadDeptStorage() {
  try {
    deptStorage.value = await api.getDepartmentStorage()
  } catch (e) {
    deptStorage.value = []
  }
}

async function loadUserStorage() {
  try {
    userStorage.value = await api.getUserStorage()
  } catch (e) {
    userStorage.value = []
  }
}

async function loadFileTypeStorage() {
  try {
    fileTypeStorage.value = await api.getFileTypeStorage()
  } catch (e) {
    fileTypeStorage.value = []
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
    const params = {
      limit: auditPageSize,
      offset: (auditPage.value - 1) * auditPageSize,
    }
    if (auditStartDate.value) params.start_date = auditStartDate.value
    if (auditEndDate.value) params.end_date = auditEndDate.value
    const logs = await api.listAuditLogs(params)
    auditList.value = logs || []
    auditHasMore.value = (logs || []).length === auditPageSize
  } catch (e) {
    err.value = e.message
  }
}

function refreshAuditFirstPage() {
  auditPage.value = 1
  loadAudit()
}

function goPrevAuditPage() {
  if (auditPage.value <= 1) return
  auditPage.value -= 1
  loadAudit()
}

function goNextAuditPage() {
  if (!auditHasMore.value) return
  auditPage.value += 1
  loadAudit()
}

/** 导出系统日志为 Excel（按当前筛选条件拉取全部数据后下载） */
async function exportAuditCsv() {
  err.value = ''
  try {
    const params = { limit: 500 }
    if (auditStartDate.value) params.start_date = auditStartDate.value
    if (auditEndDate.value) params.end_date = auditEndDate.value
    const allLogs = []
    let offset = 0
    let chunk
    do {
      chunk = await api.listAuditLogs({ ...params, offset })
      allLogs.push(...(chunk || []))
      offset += 500
    } while (Array.isArray(chunk) && chunk.length === 500)

    const kw = (auditSearch.value || '').trim().toLowerCase()
    const filtered = allLogs.filter((log) => {
      const type = auditInferType(log)
      const matchesAction = auditActionFilter.value === 'all' || type === auditActionFilter.value
      const matchesStatus = auditStatusFilter.value === 'all' || auditStatusFilter.value === 'success'
      const text =
        (log.username || '') +
        (log.action || '') +
        (log.detail || '') +
        (log.resource_type || '') +
        (log.resource_id || '')
      const matchesSearch = !kw || text.toLowerCase().includes(kw)
      return matchesAction && matchesStatus && matchesSearch
    })

    const rows = [
      ['时间', '用户', '部门', '操作', '目标', 'IP 地址', '状态'],
      ...filtered.map((log) => [
        formatDate(log.created_at),
        log.username || '-',
        log.department_name || '-',
        formatAuditActionLabel(log),
        formatAuditDetailLabel(log),
        log.ip_address || '-',
        formatAuditStatusLabel(log),
      ]),
    ]
    const ws = XLSX.utils.aoa_to_sheet(rows)
    const wb = XLSX.utils.book_new()
    XLSX.utils.book_append_sheet(wb, ws, '系统日志')
    const fileName = `系统日志_${new Date().toISOString().slice(0, 10)}.xlsx`
    XLSX.writeFile(wb, fileName)
    err.value = ''
  } catch (e) {
    err.value = e.message || '导出失败'
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
  editDeptLeaderId.value = node.leader_user_id || 0
  editDeptMembers.value = []
  // 预加载该部门成员，用于负责人下拉框
  if (node.id) {
    api
      .listDepartmentMembers(node.id)
      .then(users => {
        editDeptMembers.value = users || []
      })
      .catch(() => {
        editDeptMembers.value = []
      })
  }
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
    await api.updateDepartment(editDeptNode.value.id, {
      name,
      leader_user_id: editDeptLeaderId.value,
    })
    showEditDept.value = false
    editDeptNode.value = null
    editDeptLeaderId.value = 0
    editDeptMembers.value = []
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
  resettingUser.value = u
  resetPasswordInput.value = ''
  resetPasswordError.value = ''
  showResetPassword.value = true
}

async function confirmResetPassword() {
  const u = resettingUser.value
  if (!u) return
  const pw = resetPasswordInput.value || ''
  // 前端做一层基础校验，减少来回请求
  if (pw.length < 8) {
    resetPasswordError.value = '密码至少 8 位'
    return
  }
  if (!/[A-Z]/.test(pw) || !/[a-z]/.test(pw) || !/[0-9]/.test(pw) || !/[!@#$%^&*()_+\-=[\]{};':"\\|,.<>/?`~]/.test(pw)) {
    resetPasswordError.value = '需包含大小写字母、数字和特殊字符'
    return
  }
  err.value = ''
  resetPasswordError.value = ''
  try {
    await api.updateUser(u.id, { new_password: pw })
    showResetPassword.value = false
    resettingUser.value = null
    resetPasswordInput.value = ''
    window.alert('密码已重置，请通知用户使用新密码登录。')
  } catch (e) {
    // 后端返回的校验错误展示在弹窗内
    resetPasswordError.value = e.message || '重置密码失败'
  }
}

function closeResetPassword() {
  showResetPassword.value = false
  resettingUser.value = null
  resetPasswordInput.value = ''
  resetPasswordError.value = ''
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
  try {
    me.value = await api.getMe()
  } catch (e) {
    router.push('/login')
    return
  }

  // URL 指定了 tab 时（如从顶部栏「部门管理」进入）
  if (route.query?.tab === 'departments') {
    subTab.value = 'departments'
  }

  // 超级管理员：加载全部系统管理数据
  if (me.value?.is_superuser) {
    await Promise.all([
      loadUsers(),
      loadDepartments(),
      loadStorageAll(),
      loadAudit(),
    ])
    return
  }

  // 部门负责人：仅加载部门管理相关数据，默认停留在「部门管理」标签
  if (me.value?.is_department_leader) {
    subTab.value = 'departments'
    await loadDepartments()
    return
  }

  // 既不是管理员也不是部门负责人：不允许访问该页面，返回首页
  router.push('/')
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

.admin-storage-tabs {
  margin-top: 16px;
}

.admin-storage-overview-card {
  margin-top: 16px;
  margin-bottom: 16px;
}

.admin-storage-overview-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 220px;
  margin-bottom: 4px;
}

.admin-storage-overview-left {
  flex: 1;
}

.admin-storage-overview-sub {
  margin: 4px 0 0;
  font-size: 13px;
  color: #6b7280;
}

.admin-storage-overview-percent {
  font-size: 20px;
  font-weight: 600;
  min-width: 48px;
  text-align: right;
}

.admin-storage-overview-alert {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 8px;
  font-size: 13px;
  color: #b45309;
}

.admin-storage-alert-icon {
  width: 14px;
  height: 14px;
  color: #f59e0b;
}

.admin-storage-tabs-header {
  display: flex;
  gap: 8px;
  border-bottom: 1px solid var(--border);
  padding-bottom: 4px;
  margin-bottom: 16px;
}

.admin-storage-tab {
  padding: 6px 12px;
  border-radius: 999px;
  border: none;
  background: transparent;
  font-size: 13px;
  color: #6b7280;
  cursor: pointer;
}

.admin-storage-tab.active {
  background: #e5f0ff;
  color: #2563eb;
}

.admin-storage-section {
  margin-top: 4px;
}

.admin-storage-dept-name {
  display: flex;
  align-items: center;
  gap: 6px;
}

.admin-storage-usage {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.admin-storage-usage-main {
  font-size: 13px;
}

.admin-storage-bar {
  position: relative;
  width: 160px;
  height: 6px;
  border-radius: 999px;
  background: #e5e7eb;
  overflow: hidden;
}

.admin-storage-bar-inner {
  position: absolute;
  left: 0;
  top: 0;
  height: 100%;
  border-radius: 999px;
  background: #4b9fff;
}

.admin-storage-bar-inner.status-warning {
  background: #f59e0b;
}

.admin-storage-bar-inner.status-critical {
  background: #ef4444;
}

.admin-storage-filetypes-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 16px;
}

.admin-storage-card {
  padding: 12px 16px;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: #fff;
}

.admin-storage-card-title {
  margin: 0 0 8px;
  font-size: 14px;
  font-weight: 600;
}

.admin-storage-filetype-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.admin-storage-filetype-row {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.admin-storage-filetype-meta {
  display: flex;
  align-items: center;
  gap: 6px;
}

.admin-storage-dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: #4b9fff;
}

.admin-storage-filetype-name {
  font-size: 13px;
  color: #374151;
}

.admin-storage-filetype-values {
  display: flex;
  justify-content: flex-end;
  font-size: 12px;
  color: #6b7280;
}

.admin-storage-filetype-count {
  font-variant-numeric: tabular-nums;
}

.badge-normal {
  background: #ecfdf3;
  color: #15803d;
}

.badge-warning {
  background: #fffbeb;
  color: #b45309;
}

.badge-critical {
  background: #fef2f2;
  color: #b91c1c;
}

/* 通知管理样式复用存储管理卡片风格 */
.admin-notify-section {
  margin-top: 8px;
}

.admin-notify-templates-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 16px;
}

.admin-notify-template-card {
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 16px;
  background: #fff;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.admin-notify-template-header {
  display: flex;
  justify-content: space-between;
}

.admin-notify-template-left {
  display: flex;
  gap: 10px;
}

.admin-notify-template-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 999px;
  background: #eff6ff;
  color: #2563eb;
}

.admin-notify-template-icon-svg {
  width: 18px;
  height: 18px;
}

.admin-notify-template-title-wrap {
  display: flex;
  align-items: center;
  gap: 6px;
}

.admin-notify-template-name {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
}

.admin-notify-template-sub {
  margin: 2px 0 0;
  font-size: 13px;
  color: #6b7280;
}

.admin-notify-template-body {
  background: #f9fafb;
  border-radius: 8px;
  padding: 8px 10px;
}

.admin-notify-template-content {
  margin: 0;
  font-size: 13px;
  color: #4b5563;
}

.admin-notify-template-footer {
  display: flex;
  justify-content: flex-start;
}

.admin-notify-channels {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.admin-notify-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
}

.chip-system {
  background: #dbeafe;
  color: #1d4ed8;
}

.chip-email {
  background: #ede9fe;
  color: #6d28d9;
}

.admin-notify-chip-icon {
  width: 12px;
  height: 12px;
}

.admin-notify-settings-card {
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 14px 16px;
  background: #fff;
  margin-bottom: 12px;
}

.admin-notify-settings-title {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 0 0 8px;
  font-size: 14px;
  font-weight: 600;
}

.admin-notify-settings-icon {
  width: 16px;
  height: 16px;
  color: #4b9fff;
}

.admin-notify-settings-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.admin-notify-setting-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 10px;
  border-radius: 8px;
  border: 1px solid #e5e7eb;
}

.admin-notify-setting-left {
  display: flex;
  flex-direction: column;
}

.admin-notify-setting-name {
  font-size: 13px;
  font-weight: 500;
}

.admin-notify-setting-desc {
  font-size: 12px;
  color: #6b7280;
}

.admin-notify-recipients {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
}

.admin-notify-chips-row {
  display: flex;
  justify-content: center;
  gap: 4px;
}

.admin-notify-channel-switches {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.admin-notify-send-grid {
  grid-template-columns: 1fr 1fr;
}

.admin-notify-send-grid .form-group-full {
  grid-column: 1 / -1;
}

.admin-notify-send-desc {
  margin: 4px 0 12px;
  font-size: 13px;
  color: #6b7280;
}

.admin-notify-send-hint {
  margin: 6px 0 0;
  font-size: 12px;
  color: #9ca3af;
}

.admin-notify-channel-switches-row {
  display: flex;
  gap: 16px;
  align-items: center;
}

/* ================= 系统日志（审计）样式 ================= */

.audit-toolbar {
  margin-top: 16px;
  margin-bottom: 12px;
  padding: 12px 16px;
}

.audit-toolbar-inner {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.audit-filters-left {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.audit-search {
  min-width: 220px;
}

.audit-search-input {
  width: 100%;
  padding: 6px 10px;
  border-radius: 6px;
  border: 1px solid #d1d5db;
  font-size: 13px;
}

.audit-search-input:focus {
  outline: none;
  border-color: #4b9fff;
  box-shadow: 0 0 0 1px rgba(75, 159, 255, 0.3);
  background: #fff;
}

.audit-select {
  padding: 6px 10px;
  border-radius: 6px;
  border: 1px solid #d1d5db;
  font-size: 13px;
  background: #fff;
}

.audit-date-input {
  padding: 6px 10px;
  border-radius: 6px;
  border: 1px solid #d1d5db;
  font-size: 13px;
}

.audit-toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.audit-table-wrap {
  margin-top: 12px;
}

.audit-table-scroll {
  max-height: 420px;
  overflow: auto;
}

.audit-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.audit-table thead {
  background: #f9fafb;
  border-bottom: 1px solid #e5e7eb;
}

.audit-table th {
  padding: 8px 12px;
  text-align: left;
  font-weight: 500;
  color: #6b7280;
  font-size: 12px;
}

.audit-row:nth-child(odd) {
  background: #fff;
}

.audit-row:nth-child(even) {
  background: #f9fafb;
}

.audit-row:hover {
  background: #eff6ff;
}

.audit-cell {
  padding: 8px 12px;
  color: #374151;
}

.audit-cell-muted {
  padding: 8px 12px;
  color: #9ca3af;
  white-space: nowrap;
}

.audit-cell-strong {
  padding: 8px 12px;
  font-weight: 500;
}

.audit-cell-op {
  white-space: nowrap;
}

.audit-tag {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 500;
  background: #e5e7eb;
  color: #374151;
}

.tag-file-upload {
  background: #dbeafe;
  color: #1d4ed8;
}

.tag-file-download {
  background: #cffafe;
  color: #0369a1;
}

.tag-file-delete {
  background: #fee2e2;
  color: #b91c1c;
}

.tag-file-restore {
  background: #dcfce7;
  color: #15803d;
}

.tag-file-rename {
  background: #ede9fe;
  color: #6d28d9;
}

.tag-library {
  background: #fef9c3;
  color: #a16207;
}

.tag-user {
  background: #e0f2fe;
  color: #0369a1;
}

.tag-share {
  background: #f3e8ff;
  color: #7e22ce;
}

.tag-permission {
  background: #ffedd5;
  color: #c2410c;
}

.tag-login {
  background: #e0f2fe;
  color: #0369a1;
}

.tag-login-failed {
  background: #fee2e2;
  color: #b91c1c;
}

.tag-security {
  background: #e5e7eb;
  color: #374151;
}

.tag-notify {
  background: #fef3c7;
  color: #92400e;
}

.tag-quota {
  background: #f3f4ff;
  color: #3730a3;
}

.tag-system {
  background: #e5e7eb;
  color: #374151;
}

.tag-default {
  background: #e5e7eb;
  color: #4b5563;
}

.audit-status {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 48px;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 500;
}

.audit-status.success {
  background: #dcfce7;
  color: #15803d;
}

.audit-status.failed {
  background: #fee2e2;
  color: #b91c1c;
}

.audit-pagination {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid #e5e7eb;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  color: #6b7280;
}

.audit-pagination-actions {
  display: flex;
  gap: 8px;
}

.admin-textarea {
  width: 100%;
  min-height: 96px;
  resize: vertical;
}

.admin-notify-channel-options {
  display: flex;
  flex-direction: row;
  flex-wrap: wrap;
  gap: 60px;
  align-items: center;
}

.admin-notify-channel-option {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  color: #374151;
}

.admin-notify-checkbox {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
  margin-right: 2px;
}

.admin-notify-channel-label {
  display: inline-block;
  white-space: nowrap;
}

.switch {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
}

.switch input {
  opacity: 0;
  width: 0;
  height: 0;
  position: absolute
}

.slider {
  position: relative;
  width: 30px;
  height: 16px;
  background-color: #d1d5db;
  border-radius: 999px;
  transition: 0.2s;
  flex-shrink: 0;
  margin-right: 8px;
}

.slider:before {
  content: '';
  position: absolute;
  height: 12px;
  width: 12px;
  left: 2px;
  top: 2px;
  background-color: white;
  border-radius: 50%;
  transition: 0.2s;
}

.switch input:checked + .slider {
  background-color: #4b9fff;
}

.switch input:checked + .slider:before {
  transform: translateX(14px);
}

.switch-label {
  font-size: 13px;
  color: #374151;
  white-space: nowrap;
  display: inline-block;
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

