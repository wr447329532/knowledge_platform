<template>
  <div class="app-layout" :class="{ 'app-layout-admin': tab === 'sys' }">
    <!-- 左侧深色导航（系统管理时不显示） -->
    <aside v-if="tab !== 'sys'" class="app-sidebar">
      <!-- Logo -->
      <div class="sidebar-logo">
        <Icons name="drive" class="logo-icon" />
        <span class="logo-text">企业云盘</span>
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
        <a :class="['nav-item', { active: tab === 'lib' && !activeDeptId }]" href="#" @click.prevent="tab = 'lib'; clearDeptView(); err = ''">
          <Icons name="folder" class="nav-icon" />
          <span>我的文件库</span>
        </a>
        <a :class="['nav-item', { active: tab === 'shared' }]" href="#" @click.prevent="tab = 'shared'; sharedSubTab = 'mine'; err = ''; loadMyShares()">
          <Icons name="share" class="nav-icon" />
          <span>共享文件</span>
        </a>
        <a :class="['nav-item', { active: tab === 'recent' }]" href="#" @click.prevent="tab = 'recent'; err = ''">
          <Icons name="clock" class="nav-icon" />
          <span>最近访问</span>
        </a>
        <a :class="['nav-item', { active: tab === 'starred' }]" href="#" @click.prevent="tab = 'starred'; err = ''">
          <Icons name="star" class="nav-icon" />
          <span>星标文件</span>
        </a>
        <a :class="['nav-item', { active: tab === 'trash' }]" href="#" @click.prevent="tab = 'trash'; err = ''; loadTrash()">
          <Icons name="trash" class="nav-icon" />
          <span>回收站</span>
        </a>
      </nav>
      <!-- 部门树：可滚动，选中部门时高亮 -->
      <div class="sidebar-dept">
        <DepartmentTree :me="me" :active-dept-id="activeDeptId" @select="handleDeptSelect" />
      </div>
      <div class="sidebar-spacer"></div>
      <!-- 底部导航 -->
      <div class="sidebar-bottom">
        <button v-if="me?.is_superuser" :class="['nav-item', { active: tab === 'sys' }]" @click="tab = 'sys'; subTab = 'users'; err = ''; showNewDropdown = false; loadUsers(); loadAudit()">
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
      <!-- 顶部工具栏：系统管理用独立样式，其他用原样 -->
      <header v-if="tab !== 'sys'" class="app-topbar">
        <!-- 第一行：搜索 + 右侧全局操作 -->
        <div class="app-topbar-row">
          <div class="search-box">
            <Icons name="search" class="search-icon" />
            <input
              v-model="searchKeyword"
              type="text"
              :placeholder="topbarSearchPlaceholder"
              class="search-input"
              @keyup.enter="doSearch"
            />
          </div>
          <div class="topbar-actions">
            <template v-if="tab === 'lib'">
              <!-- 未进入具体文件库（含部门视图）：新建资料库，可选所属部门 -->
              <button
                v-if="!currentLib"
                class="btn-primary"
                @click="openNewLib()"
              >
                + 新建资料库
              </button>
              <!-- 进入某个文件库后：全局新建（上传） -->
              <button
                v-else-if="currentLib?.is_writeable"
                class="btn-primary"
                @click="showUpload = true; uploadErr = ''"
              >
                + 新建
              </button>
            </template>
          </div>
        </div>

        <!-- 第二行：我的文件库路径 + 视图控制（部门视图不显示） -->
        <div
          v-if="tab === 'lib' && !activeDeptId"
          class="file-toolbar file-toolbar-topbar"
        >
          <div class="file-toolbar-left">
            <span class="file-breadcrumb-item">文件库</span>
            <template v-if="currentLib">
              <span class="file-breadcrumb-sep">/</span>
              <a
                href="#"
                @click.prevent="currentLib = null; pathPrefix = ''"
                class="file-breadcrumb-link"
              >{{ currentLib?.name }}</a>
              <template
                v-for="(seg, i) in breadcrumbSegments"
                :key="i"
              >
                <span class="file-breadcrumb-sep">/</span>
                <a
                  v-if="seg.path !== undefined"
                  href="#"
                  @click.prevent="pathPrefix = seg.path"
                  class="file-breadcrumb-link"
                >{{ seg.label }}</a>
                <span
                  v-else
                  class="file-breadcrumb-current"
                >{{ seg.label }}</span>
              </template>
            </template>
            <template v-else>
              <span class="file-breadcrumb-sep">/</span>
              <span class="file-breadcrumb-current">全部文件</span>
            </template>
          </div>
          <div class="file-toolbar-right">
            <select
              v-model="fileSortOrder"
              class="file-sort-select"
              title="排序"
            >
              <option value="modified">最近修改</option>
              <option value="name">文件名</option>
              <option value="size">文件大小</option>
              <option value="created">创建时间</option>
            </select>
            <div class="file-view-toggle">
              <button
                type="button"
                :class="['file-view-btn', { active: fileViewMode === 'list' }]"
                @click="fileViewMode = 'list'"
                title="列表"
              >
                <Icons
                  name="list"
                  class="file-view-icon"
                />
              </button>
              <button
                type="button"
                :class="['file-view-btn', { active: fileViewMode === 'grid' }]"
                @click="fileViewMode = 'grid'"
                title="网格"
              >
                <Icons
                  name="layout-grid"
                  class="file-view-icon"
                />
              </button>
            </div>
          </div>
        </div>
      </header>

      <!-- 成功/失败提示框：固定定位，删除后自动刷新 -->
      <Transition name="toast">
        <div v-if="successMessage" class="success-toast">{{ successMessage }}</div>
      </Transition>
      <Transition name="toast">
        <div v-if="errorMessage" class="error-toast">{{ errorMessage }}</div>
      </Transition>

      <!-- 资料库 / 部门文件：库列表 或 文件列表 -->
      <div v-if="tab === 'lib'" class="app-content">
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
              <p class="dept-empty-text">该部门暂无资料库</p>
              <p class="dept-empty-hint">点击右上角「新建资料库」，选择所属部门「{{ activeDeptInfo?.name }}」后创建</p>
            </div>
          </template>
        </div>
      </div>
      <!-- 我的文件库：库列表 -->
      <div class="lib-grid-wrap" v-else-if="!currentLib">
        <div class="lib-header">
          <h3>我的文件库</h3>
        </div>
        <!-- 我的文件库：列表 / 网格视图切换 -->
        <template v-if="libraries.length">
          <!-- 行视图 -->
          <div v-if="fileViewMode === 'list'" class="lib-list-grid">
            <div class="lib-list-header">
              <span>名称</span>
              <span>描述</span>
              <span>类型</span>
              <span>操作</span>
            </div>
            <div
              v-for="lib in libraries"
              :key="lib.id"
              class="lib-list-row"
            >
              <div class="lib-list-name">
                <a
                  href="#"
                  @click.prevent="selectLib(lib)"
                  class="file-item-link"
                >
                  <Icons name="folder" class="file-icon" />
                  {{ lib.name }}
                </a>
                <span
                  v-if="!lib.is_owner"
                  class="lib-card-badge-inline"
                >共享给我</span>
              </div>
              <span class="file-meta">
                {{ lib.description || '-' }}
              </span>
              <span class="file-meta">
                {{ lib.is_owner ? '我的库' : '共享库' }}
              </span>
              <span class="file-actions-wrap">
                <button
                  class="btn-small"
                  @click.stop="openEditLib(lib)"
                  title="编辑"
                >编辑</button>
                <button
                  class="btn-small danger"
                  @click.stop="delLib(lib)"
                  title="删除"
                >删除</button>
              </span>
            </div>
          </div>
          <!-- 网格视图 -->
          <div v-else class="lib-grid">
            <div
              v-for="lib in libraries"
              :key="lib.id"
              class="lib-card"
              @click="selectLib(lib)"
            >
              <div class="lib-card-icon"><Icons name="folder" /></div>
              <div class="lib-card-name">
                {{ lib.name }}
                <span
                  v-if="!lib.is_owner"
                  class="lib-card-badge"
                >共享给我</span>
              </div>
              <p
                v-if="lib.description"
                class="lib-card-desc"
              >{{ lib.description }}</p>
              <div class="lib-card-actions" @click.stop>
                <button
                  class="btn-small"
                  @click="openEditLib(lib)"
                  title="编辑"
                >编辑</button>
                <button
                  class="btn-small danger"
                  @click="delLib(lib)"
                  title="删除"
                >删除</button>
              </div>
            </div>
          </div>
        </template>
        <p v-else class="empty-hint">暂无资料库，请点击「新建资料库」。</p>
      </div>
      <div class="file-main file-main-dashboard card" v-if="currentLib"
  :class="{ 'drop-zone-active': isDragging }"
  @dragover.prevent="isDragging = true"
  @dragleave="isDragging = false"
  @drop.prevent="onFileDrop">
        <div class="file-content-area">
        <p v-if="filesLoading" class="empty-hint">加载中...</p>
        <div v-else-if="searchResults.length" class="search-results-section">
          <div class="search-results-header">
            <span>搜索「{{ searchKeyword }}」共 {{ searchResults.length }} 项</span>
            <button class="btn-small" @click="searchResults = []; searchKeyword = ''">清除</button>
          </div>
          <template v-if="fileViewMode === 'list'">
            <div class="file-grid-header">
              <span>名称</span>
              <span>修改时间</span>
              <span>大小</span>
              <span>操作</span>
            </div>
            <div v-for="r in sortedSearchResults" :key="r.id" class="file-item file-item-row">
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
          </template>
          <div v-else class="file-cards-grid">
            <div v-for="r in sortedSearchResults" :key="r.id" class="file-card" @click="r.is_dir ? goToPath(r.path) : onFileClick(r)">
              <div class="file-card-icon"><Icons :name="r.is_dir ? 'folder' : 'file'" /></div>
              <div class="file-card-name" :title="r.path">{{ r.path.split('/').pop() }}{{ r.is_dir ? '/' : '' }}</div>
              <div class="file-card-meta">{{ r.is_dir ? '-' : formatSize(r.size) }} · {{ formatDate(r.updated_at) }}</div>
              <button type="button" class="file-card-menu" @click.stop="toggleActionMenu('s-' + r.id)" title="操作">⋮</button>
              <div v-if="openActionMenuId === 's-' + r.id" class="action-dropdown file-card-dropdown" @click.stop>
                <button v-if="!r.is_dir && (r.can_download !== false)" class="btn-small" @click="download(r.id); closeActionMenu()">下载</button>
                <button v-if="currentLib?.is_owner" class="btn-small" @click="openShare(r); closeActionMenu()">分享</button>
                <button v-if="currentLib?.is_writeable" class="btn-small" @click="openRename(r); closeActionMenu()">重命名</button>
              </div>
            </div>
          </div>
        </div>
        <template v-if="fileViewMode === 'list'">
            <div class="file-grid">
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
              <div v-for="f in sortedFiles" :key="f.id" class="file-item file-item-row">
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
          </template>
          <div v-else class="file-cards-grid">
            <div v-if="pathPrefix" class="file-card file-card-up" @click="goUp">
              <div class="file-card-icon"><Icons name="folder" /></div>
              <div class="file-card-name">.. 上一级</div>
            </div>
            <div v-for="f in sortedFiles" :key="f.id" class="file-card" @click="f.is_dir ? (pathPrefix = f.path + '/') : onFileClick(f)">
              <div class="file-card-icon"><Icons :name="f.is_dir ? 'folder' : 'file'" /></div>
              <div class="file-card-name" :title="f.path">{{ f.path.split('/').pop() }}{{ f.is_dir ? '/' : '' }}</div>
              <div class="file-card-meta">{{ f.is_dir ? '-' : formatSize(f.size) }} · {{ formatDate(f.updated_at) }}</div>
              <button type="button" class="file-card-menu" @click.stop="toggleActionMenu('f-' + f.id)" title="操作">⋮</button>
              <div v-if="openActionMenuId === 'f-' + f.id" class="action-dropdown file-card-dropdown" @click.stop>
                <template v-if="!f.is_dir">
                  <button v-if="f.can_download !== false" class="btn-small" @click="download(f.id); closeActionMenu()">下载</button>
                  <button class="btn-small" @click="openVersions(f); closeActionMenu()">版本</button>
                  <button v-if="currentLib?.is_owner" class="btn-small" @click="openShare(f); closeActionMenu()">分享</button>
                </template>
                <button v-if="currentLib?.is_writeable" class="btn-small" @click="openRename(f); closeActionMenu()">重命名</button>
                <button v-if="currentLib?.is_writeable" class="btn-small danger" @click="delFile(f); closeActionMenu()">删除</button>
              </div>
            </div>
          </div>
        <p v-if="currentLib && !filesLoading && files.length === 0 && !searchResults.length" class="empty-hint">当前目录为空，可上传文件或新建目录。</p>
        </div>
      </div>
      </div>

      <!-- 共享文件：我分享的 + 分享给我的 -->
      <div v-if="tab === 'shared'" class="app-content shared-page">
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
          <button :class="['shared-tab', { active: sharedSubTab === 'mine' }]" @click="sharedSubTab = 'mine'; loadMyShares()">我分享的</button>
          <button :class="['shared-tab', { active: sharedSubTab === 'tome' }]" @click="sharedSubTab = 'tome'; loadReceivedShares()">分享给我的</button>
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
                <div
                  v-for="row in mySharesList"
                  :key="row.id"
                  class="shared-list-row"
                >
                  <div class="shared-td-name">
                    <div class="shared-file-name" :title="row.file_path">
                      <Icons name="file" class="shared-file-icon" />
                      <span class="shared-file-path">{{ row.file_path }}</span>
                    </div>
                  </div>
                  <div class="shared-td-to">
                    <span class="shared-user">{{ row.username }}</span>
                    <span
                      v-if="row.department_name"
                      class="shared-dept"
                    >{{ row.department_name }}</span>
                  </div>
                  <div class="shared-td-lib">
                    <span class="shared-cell">{{ row.library_name }}</span>
                  </div>
                  <div class="shared-td-perm">
                    <span
                      :class="[
                        'shared-permission',
                        row.permission === 'download' ? 'perm-download' : 'perm-read'
                      ]"
                    >
                      {{ row.permission === 'download' ? '可下载' : '只读' }}
                    </span>
                  </div>
                  <div class="shared-td-action shared-td-action-last">
                    <button
                      type="button"
                      class="btn-small danger"
                      @click="removeShare(row)"
                    >
                      取消分享
                    </button>
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
                <div
                  v-for="row in receivedSharesList"
                  :key="row.id"
                  class="shared-list-row"
                >
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
                    <span
                      :class="[
                        'shared-permission',
                        row.permission === 'download' ? 'perm-download' : 'perm-read'
                      ]"
                    >
                      {{ row.permission === 'download' ? '可下载' : '只读' }}
                    </span>
                  </div>
                  <div class="shared-td-action shared-td-action-last">
                    <button
                      type="button"
                      class="shared-open-btn"
                      @click="openSharedLib(row)"
                    >
                      打开
                    </button>
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

      <!-- 最近访问（占位） -->
      <div v-if="tab === 'recent'" class="app-content">
        <div class="card placeholder-page">
          <Icons name="clock" class="placeholder-icon" />
          <h3>最近访问</h3>
          <p class="empty-hint">暂无最近访问记录，敬请期待。</p>
        </div>
      </div>

      <!-- 星标文件（占位） -->
      <div v-if="tab === 'starred'" class="app-content">
        <div class="card placeholder-page">
          <Icons name="star" class="placeholder-icon" />
          <h3>星标文件</h3>
          <p class="empty-hint">暂无星标文件，敬请期待。</p>
        </div>
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

    <!-- 系统管理：AdminLayout 风格 -->
    <div v-if="tab === 'sys'" class="admin-layout">
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
          <button type="button" class="admin-back-btn" @click="tab = 'lib'">
            <Icons name="arrow-left" class="admin-back-icon" />
            返回
          </button>
        </header>
        <div class="admin-body">
          <aside class="admin-sidebar">
            <nav class="admin-nav">
              <button :class="['admin-nav-item', { active: subTab === 'users' }]" @click="subTab = 'users'; loadUsers()">
                <Icons name="users" class="admin-nav-icon" />
                用户管理
              </button>
              <button :class="['admin-nav-item', { active: subTab === 'departments' }]" @click="subTab = 'departments'; loadDepartments()">
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
              <button :class="['admin-nav-item', { active: subTab === 'audit' }]" @click="subTab = 'audit'; loadAudit()">
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
                  <div class="admin-stat-extra">{{ userList.length ? Math.round(userList.filter(u => u.is_active).length / userList.length * 100) : 0 }}% 活跃率</div>
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
                  placeholder="搜索用户名、姓名或邮箱..."
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
                      <th>部门</th>
                      <th>角色 / 状态</th>
                      <th>创建时间</th>
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
                      <td class="admin-cell">{{ u.department_name || '-' }}</td>
                      <td class="admin-role-status-cell">
                        <span :class="['admin-badge', u.is_superuser ? 'badge-admin' : 'badge-user']">{{ u.is_superuser ? '管理员' : '普通用户' }}</span>
                        <span :class="['admin-badge', u.is_active ? 'badge-ok' : 'badge-disabled']">{{ u.is_active ? '活跃' : '停用' }}</span>
                      </td>
                      <td class="admin-cell-muted">{{ formatDate(u.created_at) }}</td>
                      <td class="text-right">
                        <button v-if="u.id !== me?.id" type="button" class="admin-action-btn" :class="{ danger: !u.is_active }" @click="toggleUserActive(u)">{{ u.is_active ? '停用' : '启用' }}</button>
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
                  <div class="admin-stat-extra"><Icons name="building" class="admin-stat-icon" /></div>
                </div>
                <div class="admin-stat-card">
                  <div class="admin-stat-label">总员工数</div>
                  <div class="admin-stat-value">{{ userList.length }}</div>
                  <div class="admin-stat-extra"><Icons name="users" class="admin-stat-icon green" /></div>
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
                <p v-else-if="!filteredDeptTreeForTable?.length" class="admin-empty">未找到匹配「{{ sysSearchKeyword }}」的部门。</p>
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
                <input v-model="auditStartDate" type="text" placeholder="YYYY-MM-DD" class="admin-date-input" maxlength="10" />
                <span class="admin-label">结束</span>
                <input v-model="auditEndDate" type="text" placeholder="YYYY-MM-DD" class="admin-date-input" maxlength="10" />
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
    </div>

    </div><!-- /app-main -->

    <!-- 新建资料库：统一入口，可选所属部门 -->
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
            <option
              v-for="opt in deptOptionsForUser"
              :key="opt.id"
              :value="opt.id"
            >
              {{ '　'.repeat(opt.level) + opt.name }}
            </option>
          </select>
          <p class="form-hint">选择部门则创建为部门共享库，部门成员均可访问</p>
        </div>
        <p v-if="err" class="text-danger">{{ err }}</p>
        <div class="modal-actions">
          <button class="primary" @click="createLib">确定</button>
          <button @click="showNewLib = false; newLibDepartmentId = null">取消</button>
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
import DepartmentTree from '../components/DepartmentTree.vue'
import DepartmentTableRow from '../components/DepartmentTableRow.vue'

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
const fileSortOrder = ref('modified') // modified | name | size | created
const fileViewMode = ref('list') // list | grid
const files = ref([])
const filesLoading = ref(false)
const successMessage = ref('')
const errorMessage = ref('')
const showNewLib = ref(false)
const newLibName = ref('')
const newLibDesc = ref('')
const newLibDepartmentId = ref(null)
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
const mySharesList = ref([])
const mySharesLoading = ref(false)
const sharedSubTab = ref('mine') // 'mine' | 'tome'
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
const newUserRole = ref('user') // admin | user
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
// 企业云盘：当前选中的部门视图
const activeDeptId = ref(null)
const activeDeptInfo = ref(null)
const activeDeptLibraries = ref([])
const activeDeptLoading = ref(false)
const activeDeptErr = ref('')

const topbarSearchPlaceholder = computed(() => {
  if (tab.value === 'lib' || tab.value === 'shared') return '搜索文件、文件夹...'
  if (tab.value === 'recent' || tab.value === 'starred') return '搜索...'
  return '搜索文件、文件夹...'
})

const sysSearchPlaceholder = computed(() => {
  if (subTab.value === 'users') return '搜索用户、邮箱...'
  if (subTab.value === 'audit') return '搜索操作、用户...'
  if (subTab.value === 'departments') return '搜索部门...'
  return '搜索...'
})

const sharedLibraries = computed(() => libraries.value.filter((lib) => !lib.is_owner))

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

/** 递归过滤部门树：名称包含关键词的节点及其祖先保留 */
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
  _filterDeptTree(deptTreeForTable.value, sysSearchKeyword.value)
)

const deptOptionsForUser = computed(() =>
  _flattenDepts(deptTreeForTable.value)
)

function _countDeptNodes(nodes) {
  if (!nodes?.length) return 0
  return nodes.reduce((sum, n) => sum + 1 + _countDeptNodes(n.children), 0)
}
const deptTreeCount = computed(() => _countDeptNodes(deptTreeForTable.value))

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
  if (!list || !list.length) return list
  const order = fileSortOrder.value
  const arr = [...list]
  if (order === 'name') {
    arr.sort((a, b) => {
      const na = (a.path || '').toLowerCase()
      const nb = (b.path || '').toLowerCase()
      if (a.is_dir && !b.is_dir) return -1
      if (!a.is_dir && b.is_dir) return 1
      return na.localeCompare(nb)
    })
  } else if (order === 'size') {
    arr.sort((a, b) => {
      if (a.is_dir && !b.is_dir) return -1
      if (!a.is_dir && b.is_dir) return 1
      return (b.size || 0) - (a.size || 0)
    })
  } else if (order === 'created') {
    arr.sort((a, b) => new Date(a.updated_at || 0) - new Date(b.updated_at || 0))
  } else {
    // modified (default)
    arr.sort((a, b) => new Date(b.updated_at || 0) - new Date(a.updated_at || 0))
  }
  return arr
}
const sortedFiles = computed(() => _sortFileList(files.value))
const sortedSearchResults = computed(() => _sortFileList(searchResults.value))

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
  // 初始加载一次部门数据，供系统管理「部门管理」使用
  await loadDepartments()
})

// 当系统管理子 tab 切换到「部门管理」时，自动刷新部门树
watch(subTab, (val) => {
  if (val === 'departments') {
    loadDepartments()
  }
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
watch(showNewDropdown, (open) => {
  if (!open) return
  const close = () => { showNewDropdown.value = false }
  const onDocClick = () => { close(); document.removeEventListener('click', onDocClick) }
  setTimeout(() => document.addEventListener('click', onDocClick), 0)
})
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
  const raw = newLibDepartmentId.value
  const deptId = raw === '' || raw === null || raw === undefined ? null : Number(raw)
  try {
    await api.createLibrary(name, (newLibDesc.value || '').trim(), deptId)
    libraries.value = await api.listLibraries()
    showNewLib.value = false
    newLibName.value = ''
    newLibDesc.value = ''
    newLibDepartmentId.value = null
    if (deptId && activeDeptId.value === deptId) {
      activeDeptLibraries.value = await api.listDepartmentLibraries(deptId)
    }
    showSuccess(deptId ? '部门资料库已创建' : '资料库已创建')
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

async function loadMyShares() {
  if (tab.value !== 'shared') return
  mySharesLoading.value = true
  try {
    mySharesList.value = await api.listMyShares()
  } catch (e) {
    err.value = e.message
    mySharesList.value = []
  } finally {
    mySharesLoading.value = false
  }
}

async function removeShare(row) {
  if (!confirm(`确定取消对「${row.username}」的分享？`)) return
  try {
    await api.removeFileShare(row.file_entry_id, row.user_id)
    showSuccess('已取消分享')
    await loadMyShares()
  } catch (e) {
    err.value = e.message
  }
}

async function loadReceivedShares() {
  if (tab.value !== 'shared' || sharedSubTab.value !== 'tome') return
  receivedSharesLoading.value = true
  try {
    receivedSharesList.value = await api.listSharesToMe()
  } catch (e) {
    err.value = e.message
    receivedSharesList.value = []
  } finally {
    receivedSharesLoading.value = false
  }
}

function openSharedLib(row) {
  const lib = libraries.value.find((l) => l.id === row.library_id)
  if (lib) {
    tab.value = 'lib'
    selectLib(lib)
    pathPrefix.value = row.file_path.includes('/') ? row.file_path.replace(/\/[^/]+$/, '') + '/' : ''
  } else {
    err.value = '未找到该资料库，请刷新页面后重试'
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
  // 始终刷新部门树数据，供「部门管理」表格使用
  deptTreeRefreshKey.value++
  try {
    deptTreeForTable.value = await api.getDepartmentTree()
  } catch (e) {
    deptTreeForTable.value = []
  }
}

function onSysSearch() {
  const kw = sysSearchKeyword.value?.trim()
  if (subTab.value === 'users') loadUsers()
  else if (subTab.value === 'audit') loadAudit()
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
  if (!name) { err.value = '请输入部门名称'; return }
  try {
    await api.createDepartment(name, null, 0)
    showAddRootDept.value = false
    newRootDeptName.value = ''
    deptTreeRefreshKey.value++
    await loadDepartments()
    showSuccess('根部门已创建')
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
  if (!name) { err.value = '请输入部门名称'; return }
  try {
    await api.createDepartment(name, addSubDeptParent.value.id, 0)
    showAddSubDept.value = false
    addSubDeptParent.value = null
    addSubDeptName.value = ''
    await loadDepartments()
    showSuccess('子部门已创建')
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
  if (!name) { err.value = '请输入部门名称'; return }
  try {
    await api.updateDepartment(editDeptNode.value.id, { name })
    showEditDept.value = false
    editDeptNode.value = null
    await loadDepartments()
    showSuccess('部门已更新')
  } catch (e) {
    err.value = e.message
  }
}

async function doDeleteDept(node) {
  if (!confirm('确定删除部门「' + node.name + '」？其子部门将一并删除。')) return
  try {
    await api.deleteDepartment(node.id)
    await loadDepartments()
    showSuccess('已删除')
  } catch (e) {
    showError(e.message || '删除失败')
  }
}

async function loadDeptFiles(deptId) {
  activeDeptLoading.value = true
  activeDeptErr.value = ''
  try {
    activeDeptInfo.value = await api.getDepartmentInfo(deptId)
    if (!activeDeptInfo.value?.has_access) {
      activeDeptLibraries.value = []
      return
    }
    activeDeptLibraries.value = await api.listDepartmentLibraries(deptId)
  } catch (e) {
    activeDeptErr.value = e.message || '加载部门库失败'
    activeDeptLibraries.value = []
  } finally {
    activeDeptLoading.value = false
  }
}

async function handleDeptSelect(node) {
  // 点击侧边栏部门：切换到部门文件视图
  tab.value = 'lib'
  currentLib.value = null
  pathPrefix.value = ''
  activeDeptId.value = node.id
  await loadDeptFiles(node.id)
}

function clearDeptView() {
  activeDeptId.value = null
  activeDeptInfo.value = null
  activeDeptLibraries.value = []
  activeDeptErr.value = ''
}

function openNewLib() {
  newLibName.value = ''
  newLibDesc.value = ''
  err.value = ''
  newLibDepartmentId.value = activeDeptId.value || null
  showNewLib.value = true
}

function openDeptLib(lib) {
  clearDeptView()
  selectLib(lib)
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
    const isSuper = newUserRole.value === 'admin' || newUserIsSuperuser.value
    const deptId = newUserDeptId.value ? Number(newUserDeptId.value) : null
    await api.createUser(
      newUserEmail.value.trim(),
      newUserUsername.value.trim(),
      newUserPassword.value,
      isSuper,
      deptId,
    )
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
.app-layout-admin .app-main { width: 100%; }
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
.sidebar-dept {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 12px;
  border-bottom: 1px solid rgba(75,85,99,0.5);
}
.sidebar-spacer { flex: 0; min-height: 0; }
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
  background: #fff;
  border-bottom: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 8px 24px 10px;
}
.app-topbar-row {
  display: flex;
  align-items: center;
  gap: 20px;
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
.lib-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; flex-wrap: wrap; gap: 12px; }
.lib-header h3 { margin: 0; font-size: 18px; color: var(--text); }
.lib-header-desc { margin: 4px 0 0 0; width: 100%; font-size: 14px; color: var(--text-secondary); }
.placeholder-page { max-width: 480px; text-align: center; padding: 48px 24px; }
.placeholder-page h3 { margin: 0 0 12px 0; font-size: 18px; color: var(--text); }
.placeholder-icon { width: 48px; height: 48px; color: var(--primary); opacity: 0.6; margin-bottom: 16px; }

/* 共享文件页：星标文件风格优化 */
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
  width: 44px;
  height: 44px;
  border-radius: 10px;
  background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.shared-page-icon { width: 22px; height: 22px; color: #4a90e2; }
.shared-page-header-text { min-width: 0; }
.shared-page-title { margin: 0; font-size: 22px; font-weight: 600; color: #111; letter-spacing: -0.02em; }
.shared-page-desc { margin: 6px 0 0 0; font-size: 13px; color: #6b7280; line-height: 1.4; }
.shared-tabs {
  flex-shrink: 0;
  display: flex;
  gap: 4px;
  padding: 12px 32px 0;
  background: #fff;
  border-bottom: 1px solid var(--border);
}
.shared-tab {
  padding: 10px 20px;
  border: none;
  background: none;
  font-size: 14px;
  font-weight: 500;
  color: #6b7280;
  cursor: pointer;
  border-radius: 8px 8px 0 0;
  margin-bottom: -1px;
  transition: color 0.2s, background 0.2s;
}
.shared-tab:hover { color: #111; background: #f9fafb; }
.shared-tab.active { color: #4a90e2; background: #f3f4f6; border-bottom: 2px solid #4a90e2; }
.shared-page-body { flex: 1; overflow: auto; background: #f3f4f6; padding: 24px 32px; }
.shared-open-btn {
  padding: 6px 14px;
  border: none;
  background: #4a90e2;
  color: #fff;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  border-radius: 6px;
  transition: background 0.2s;
}
.shared-open-btn:hover { background: #357abd; }
.shared-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 20px;
  padding: 64px 24px;
  color: #6b7280;
  font-size: 14px;
}
.shared-loading-dots { display: flex; align-items: center; justify-content: center; gap: 6px; }
.shared-loading-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #4a90e2;
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
.shared-table-card {
  /* 去掉外层卡片效果，和“我的文件库”列表保持一致 */
  background: transparent;
  border-radius: 0;
  box-shadow: none;
  border: none;
  overflow: visible;
}
.shared-list-grid {
  display: flex;
  flex-direction: column;
  width: 100%;
}
.shared-list-header,
.shared-list-row {
  display: grid;
  /* 名称 / 共享给 / 所属资料库 / 权限 / 操作 */
  grid-template-columns: 2.4fr 2fr 1.8fr 1.4fr 1.2fr;
  gap: 12px;
  padding: 10px 12px;
  align-items: center;
}
.shared-list-header {
  background: #f7f8fa;
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
  border-bottom: 1px solid var(--border);
}
.shared-list-row {
  border-bottom: 1px solid #f3f4f6;
}
.shared-list-row:hover { background: #fafafa; }
.shared-td-name { min-width: 0; } /* 配合 truncate，让名称列可见且可缩放 */
.shared-col-perm,
.shared-td-perm {
  text-align: center;
}
.shared-col-action { text-align: right; }
.shared-td-action-last {
  text-align: right;
  white-space: nowrap;
}
.shared-file-name {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}
.shared-file-icon { width: 18px; height: 18px; color: #4a90e2; flex-shrink: 0; }
.shared-file-path {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #111;
  font-weight: 500;
}
.shared-td-to { color: #374151; }
.shared-user { font-weight: 500; color: #111; }
.shared-dept {
  display: inline-block;
  margin-left: 6px;
  padding: 0 6px;
  font-size: 12px;
  color: #6b7280;
  background: #f3f4f6;
  border-radius: 4px;
}
.shared-permission {
  display: inline-block;
  padding: 2px 8px;
  font-size: 12px;
  font-weight: 500;
  border-radius: 6px;
}
.shared-permission.perm-read { background: #f3f4f6; color: #4b5563; }
.shared-permission.perm-download { background: #dbeafe; color: #1d4ed8; }
.shared-td-action { text-align: left; padding-left: 20px; vertical-align: middle; }
.shared-td-perm { text-align: center; }
.shared-action-btn {
  padding: 5px 10px;
  border: none;
  background: transparent;
  font-size: 13px;
  color: #6b7280;
  cursor: pointer;
  border-radius: 5px;
  transition: background 0.2s, color 0.2s;
}
.shared-action-btn:hover { background: #f5f5f5; color: #111; }
.shared-action-btn-remove { color: #b91c1c; }
.shared-action-btn-remove:hover {
  background: #fef2f2;
  color: #dc2626;
}
.shared-empty {
  max-width: 400px;
  margin: 0 auto;
  text-align: center;
  padding: 56px 32px;
  background: #fff;
  border-radius: 12px;
  border: 1px dashed var(--border);
}
.shared-empty-icon-wrap {
  width: 72px;
  height: 72px;
  margin: 0 auto 20px;
  border-radius: 50%;
  background: #f9fafb;
  display: flex;
  align-items: center;
  justify-content: center;
}
.shared-empty-icon { width: 32px; height: 32px; color: #d1d5db; }
.shared-empty-title { margin: 0 0 8px 0; font-size: 17px; font-weight: 600; color: #374151; }
.shared-empty-desc { margin: 0; font-size: 14px; color: #9ca3af; line-height: 1.5; }
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
.lib-card-badge-inline {
  font-size: 11px;
  color: var(--primary);
  background: var(--primary-bg);
  padding: 2px 8px;
  border-radius: 4px;
  margin-left: 8px;
}
.lib-list-grid {
  display: flex;
  flex-direction: column;
  width: 100%;
}
.lib-list-header,
.lib-list-row {
  display: grid;
  grid-template-columns: 2fr 3fr 1fr 1fr;
  gap: 12px;
  padding: 10px 12px;
  align-items: center;
}
.lib-list-header {
  background: #f7f8fa;
  font-weight: 600;
  font-size: 13px;
  color: var(--text);
  border-bottom: 1px solid var(--border);
}
.lib-list-row {
  border-bottom: 1px solid var(--border);
}
.lib-list-row:hover {
  background: #fafbfc;
}
.lib-list-name {
  min-width: 0;
}
.lib-card-desc { font-size: 13px; color: var(--text-secondary); margin: 0 0 12px 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.add-member-row { display: flex; gap: 10px; align-items: center; margin-bottom: 16px; }
.members-table { width: 100%; border-collapse: collapse; margin-top: 12px; }
.members-table th, .members-table td { padding: 8px 12px; text-align: left; border-bottom: 1px solid var(--border); }
.lib-card-actions { display: flex; gap: 8px; flex-wrap: wrap; }
.user-modal-card { max-width: 520px; }
.user-modal-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px 16px;
  margin-top: 12px;
}
@media (max-width: 640px) {
  .user-modal-grid { grid-template-columns: 1fr; }
}
.file-main { flex: 1; min-width: 0; display: flex; flex-direction: column; min-height: 0; }
.file-main h3 { margin: 0 0 12px 0; font-size: 16px; }
.file-main-dashboard .file-content-area { flex: 1; min-height: 0; overflow: auto; background: #f9fafb; }
/* 文件库工具栏（参考 Dashboard） */
.file-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  padding: 16px 32px;
  background: #fff;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}
.file-toolbar-topbar {
  /* 顶部 Header 里的版本，左右对齐搜索框 */
  padding: 4px 0 0;
  border-bottom: none;
}
.file-toolbar-left {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  min-width: 0;
}
.file-breadcrumb-item { color: #6b7280; }
.file-breadcrumb-sep { color: #9ca3af; user-select: none; }
.file-breadcrumb-link { color: var(--primary); text-decoration: none; }
.file-breadcrumb-link:hover { text-decoration: underline; }
.file-breadcrumb-current { color: #111; font-weight: 500; max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.file-toolbar-right {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}
.file-sort-select {
  width: 180px;
  padding: 8px 12px 8px 32px;
  border: 1px solid var(--border);
  border-radius: 8px;
  font-size: 14px;
  color: var(--text);
  background: #fff url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="%236b7280" stroke-width="2"><line x1="4" y1="21" x2="4" y2="14"/><line x1="4" y1="10" x2="4" y2="3"/><line x1="12" y1="21" x2="12" y2="12"/><line x1="12" y1="8" x2="12" y2="3"/><line x1="20" y1="21" x2="20" y2="16"/><line x1="20" y1="12" x2="20" y2="3"/><line x1="1" y1="14" x2="7" y2="14"/><line x1="9" y1="8" x2="15" y2="8"/><line x1="17" y1="16" x2="23" y2="16"/></svg>') no-repeat 10px center;
  cursor: pointer;
}
.file-view-toggle {
  display: flex;
  align-items: center;
  gap: 2px;
  padding: 4px;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  background: #fff;
}
.file-view-btn {
  padding: 6px 10px;
  border: none;
  background: transparent;
  border-radius: 6px;
  cursor: pointer;
  color: #6b7280;
  display: flex;
  align-items: center;
  justify-content: center;
}
.file-view-btn:hover { color: #111; background: #f3f4f6; }
.file-view-btn.active { background: #4a90e2; color: #fff; }
.file-view-btn.active:hover { background: #357abd; color: #fff; }
.file-view-icon { width: 16px; height: 16px; }
.file-toolbar-btn { flex-shrink: 0; }
/* 文件网格卡片视图 */
.file-cards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 16px;
  padding: 24px 32px;
}
.file-card {
  position: relative;
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 16px;
  text-align: center;
  cursor: pointer;
  transition: box-shadow 0.2s, border-color 0.2s;
}
.file-card:hover { border-color: #4a90e2; box-shadow: 0 2px 8px rgba(74,144,226,0.15); }
.file-card-icon { width: 48px; height: 48px; margin: 0 auto 10px; color: #4a90e2; }
.file-card-icon .icon { width: 48px; height: 48px; }
.file-card-name {
  font-size: 13px;
  font-weight: 500;
  color: #111;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-bottom: 4px;
}
.file-card-meta { font-size: 11px; color: #6b7280; }
.file-card-up .file-card-name { color: var(--primary); }
.file-card-menu {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 28px;
  height: 28px;
  padding: 0;
  border: none;
  background: transparent;
  border-radius: 4px;
  font-size: 16px;
  color: #6b7280;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}
.file-card-menu:hover { background: #f3f4f6; color: #111; }
.file-card-dropdown { right: 0; left: auto; }
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
/* 系统管理 - AdminLayout */
.admin-layout { flex: 1; min-height: 0; display: flex; flex-direction: column; overflow: hidden; background: #f9fafb; }
.admin-permission-card { flex: 1; padding: 48px 24px; text-align: center; }
.admin-header { background: #fff; border-bottom: 1px solid var(--border); padding: 16px 32px; display: flex; align-items: center; justify-content: space-between; flex-shrink: 0; }
.admin-header-left { display: flex; align-items: center; gap: 16px; }
.admin-logo { width: 32px; height: 32px; color: #4a90e2; flex-shrink: 0; }
.admin-title { margin: 0; font-size: 20px; font-weight: 600; color: #111; }
.admin-subtitle { margin: 4px 0 0 0; font-size: 13px; color: #6b7280; }
.admin-back-btn { display: inline-flex; align-items: center; gap: 8px; padding: 8px 16px; border: 1px solid var(--border); background: #fff; border-radius: 8px; font-size: 14px; color: var(--text); cursor: pointer; }
.admin-back-btn:hover { background: #f3f4f6; }
.admin-back-icon { width: 16px; height: 16px; }
.admin-body { flex: 1; display: flex; min-height: 0; overflow: hidden; }
.admin-sidebar { width: 256px; flex-shrink: 0; background: #fff; border-right: 1px solid var(--border); overflow-y: auto; }
.admin-nav { padding: 16px; display: flex; flex-direction: column; gap: 4px; }
.admin-nav-item { display: flex; align-items: center; gap: 12px; padding: 12px 16px; border: none; background: none; width: 100%; text-align: left; font-size: 14px; font-weight: 500; color: #374151; border-radius: 8px; cursor: pointer; transition: background 0.2s, color 0.2s; }
.admin-nav-item:hover { background: #f3f4f6; color: #111; }
.admin-nav-item.active { background: #4a90e2; color: #fff; }
.admin-nav-item.disabled { opacity: 0.5; cursor: not-allowed; }
.admin-nav-icon { width: 20px; height: 20px; flex-shrink: 0; }
.admin-main { flex: 1; padding: 32px; overflow-y: auto; min-width: 0; }
.admin-page { max-width: 1200px; }
.admin-page-header { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 24px; gap: 16px; }
.admin-page-title { margin: 0; font-size: 24px; font-weight: 600; color: #111; }
.admin-page-desc { margin: 4px 0 0 0; font-size: 14px; color: #6b7280; }
.admin-btn-primary { display: inline-flex; align-items: center; gap: 8px; padding: 8px 16px; background: linear-gradient(90deg, #4a90e2, #357abd); color: #fff; border: none; border-radius: 8px; font-size: 14px; font-weight: 500; cursor: pointer; flex-shrink: 0; }
.admin-btn-primary:hover { background: linear-gradient(90deg, #357abd, #2d6ba8); }
.admin-btn-icon { width: 16px; height: 16px; }
.admin-stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }
.admin-stat-card { background: #fff; border: 1px solid var(--border); border-radius: 8px; padding: 16px; }
.admin-stat-label { font-size: 13px; color: #6b7280; }
.admin-stat-value { font-size: 24px; font-weight: 600; color: #111; margin-top: 4px; }
.admin-stat-extra { font-size: 12px; color: #6b7280; margin-top: 4px; }
.admin-stat-extra.text-green { color: #059669; }
.admin-stat-icon { width: 32px; height: 32px; margin-top: 8px; color: #4a90e2; opacity: 0.5; }
.admin-stat-icon.green { color: #059669; }
.admin-toolbar { display: flex; align-items: center; gap: 16px; flex-wrap: wrap; margin-bottom: 24px; }
.admin-search-wrap { flex: 1; min-width: 200px; max-width: 400px; position: relative; display: flex; align-items: center; }
.admin-search-icon { position: absolute; left: 12px; width: 16px; height: 16px; color: #9ca3af; }
.admin-search-input { width: 100%; padding: 8px 12px 8px 36px; border: 1px solid var(--border); border-radius: 8px; font-size: 14px; }
.admin-select { padding: 8px 12px; border: 1px solid var(--border); border-radius: 8px; font-size: 14px; min-width: 120px; }
.admin-label { font-size: 14px; color: var(--text-secondary); white-space: nowrap; }
.admin-input-sm { padding: 8px 12px; border: 1px solid var(--border); border-radius: 8px; font-size: 14px; width: 120px; }
.admin-date-input { padding: 8px 12px; border: 1px solid var(--border); border-radius: 8px; font-size: 14px; width: 140px; }
.admin-table-wrap { overflow: hidden; padding: 0; }
.admin-table { width: 100%; border-collapse: collapse; font-size: 14px; }
.admin-table thead { background: #f9fafb; border-bottom: 1px solid var(--border); }
.admin-table th { padding: 12px 24px; text-align: left; font-size: 12px; font-weight: 600; color: #6b7280; text-transform: uppercase; letter-spacing: 0.05em; }
.admin-table td { padding: 16px 24px; border-bottom: 1px solid var(--border); vertical-align: middle; }
.admin-table-row:hover { background: #f9fafb; }
.admin-table .text-right { text-align: right; }
.admin-table .text-center { text-align: center; }
/* 部门管理表头与内容对齐 */
.admin-table-dept .admin-dept-th-name { padding-left: 48px; }
.admin-table-dept .admin-dept-th-center { text-align: center; }
.admin-table-dept .admin-dept-th-action { text-align: right; }
.admin-user-info { display: flex; flex-direction: column; gap: 2px; }
.admin-user-name { font-weight: 500; color: #111; }
.admin-user-email { font-size: 13px; color: #6b7280; }
.admin-cell { color: #374151; }
.admin-cell-muted { color: #6b7280; font-size: 13px; }
.admin-badge { display: inline-flex; align-items: center; padding: 2px 10px; border-radius: 9999px; font-size: 12px; font-weight: 500; }
.admin-badge.badge-admin { background: #ede9fe; color: #5b21b6; }
.admin-badge.badge-user { background: #f3f4f6; color: #374151; }
.admin-badge.badge-ok { background: #d1fae5; color: #059669; }
.admin-badge.badge-disabled { background: #fee2e2; color: #dc2626; }
.admin-role-status-cell { white-space: nowrap; }
.admin-role-status-cell .admin-badge { margin-right: 8px; }
.admin-role-status-cell .admin-badge:last-child { margin-right: 0; }
.admin-action-btn { padding: 4px 10px; margin-left: 4px; border: none; background: transparent; font-size: 13px; color: var(--primary); cursor: pointer; border-radius: 4px; }
.admin-action-btn:hover { background: #f3f4f6; text-decoration: underline; }
.admin-action-btn.link { color: var(--primary); }
.admin-action-btn.danger { color: var(--danger); }
.admin-action-btn.danger:hover { background: #fee2e2; }
.admin-empty { padding: 24px; text-align: center; color: #6b7280; font-size: 14px; margin: 0; }
@media (max-width: 900px) { .admin-stats { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 600px) { .admin-stats { grid-template-columns: 1fr; } .admin-sidebar { width: 100%; border-right: none; border-bottom: 1px solid var(--border); } .admin-body { flex-direction: column; } }

/* 系统管理 - 旧样式保留 */
.sys-main {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.sys-topbar {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
}
.sys-topbar .sys-search-box {
  flex: 1;
  max-width: 512px;
  background: #fff;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  padding: 0 12px 0 40px;
  height: 40px;
  position: relative;
}
.sys-topbar .sys-search-box .search-icon {
  position: absolute;
  left: 12px;
  top: 50%;
  transform: translateY(-50%);
  width: 20px;
  height: 20px;
  color: #9ca3af;
}
.sys-topbar .sys-search-box:focus-within {
  border-color: #4a90e2;
  box-shadow: 0 0 0 2px rgba(74,144,226,0.2);
}
.sys-topbar .sys-search-input {
  background: transparent;
  border: none;
  padding: 0;
}
.sys-topbar .sys-btn-primary {
  background: linear-gradient(90deg, #4a90e2, #357abd) !important;
  border: none !important;
  color: #fff !important;
}
.sys-topbar .sys-btn-primary:hover {
  background: linear-gradient(90deg, #357abd, #2d6ba8) !important;
}
.sys-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-left: 24px;
}
.sys-dropdown-wrap {
  position: relative;
}
.sys-btn-primary {
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
}
.sys-btn-primary:hover { background: linear-gradient(90deg, #357abd, #2d6ba8); }
.sys-btn-icon { width: 20px; height: 20px; }
.sys-dropdown {
  position: absolute;
  top: 100%;
  left: 0;
  margin-top: 4px;
  min-width: 180px;
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
  padding: 4px;
  z-index: 50;
}
.sys-dropdown-item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 10px 12px;
  border: none;
  background: none;
  font-size: 14px;
  color: var(--text);
  text-align: left;
  border-radius: 6px;
  cursor: pointer;
}
.sys-dropdown-item:hover {
  background: #f3f4f6;
}
.sys-dropdown-icon { width: 16px; height: 16px; flex-shrink: 0; }
.sys-bell-btn {
  position: relative;
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: none;
  border-radius: 8px;
  cursor: pointer;
}
.sys-bell-btn:hover { background: #f3f4f6; }
.sys-bell-icon { width: 20px; height: 20px; color: #4b5563; }
.sys-bell-dot {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 8px;
  height: 8px;
  background: #ef4444;
  border-radius: 50%;
}
.dept-page {
  padding: 24px;
  min-height: 320px;
}
/* 部门库视图 */
.dept-files-card { overflow: hidden; }
.dept-files-header {
  display: flex;
  align-items: center;
  padding: 16px 24px;
  border-bottom: 1px solid var(--border);
}
.dept-files-title-left {
  display: flex;
  align-items: center;
  gap: 10px;
}
.dept-files-icon { width: 22px; height: 22px; color: var(--primary); flex-shrink: 0; }
.dept-files-title { margin: 0; font-size: 17px; font-weight: 600; color: #111; }
.dept-files-body { padding: 24px; }
.dept-lock { text-align: center; padding: 48px 24px; color: #6b7280; }
.dept-lock-icon { width: 48px; height: 48px; margin-bottom: 16px; opacity: 0.5; }
.dept-lib-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 20px;
}
.dept-lib-card { cursor: pointer; }
.dept-lib-meta { margin-top: 8px; }
.dept-lib-badge {
  font-size: 11px;
  color: var(--primary);
  background: var(--primary-bg);
  padding: 2px 8px;
  border-radius: 4px;
}
.dept-lib-badge.shared { color: #059669; background: #d1fae5; }
.dept-empty {
  text-align: center;
  padding: 48px 24px;
  color: #6b7280;
}
.dept-empty-icon { width: 64px; height: 64px; margin-bottom: 16px; opacity: 0.4; }
.dept-empty-text { margin: 0; font-size: 15px; }
.dept-empty-hint { margin: 8px 0 0 0; font-size: 13px; color: #9ca3af; }
.sys-content { border-top: none; }

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
.modal .form-hint { margin: 6px 0 0 0; font-size: 12px; color: #9ca3af; }
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
