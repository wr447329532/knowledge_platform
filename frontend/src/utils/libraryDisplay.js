/**
 * 文件库类型与访问权限标签 — 供 LibraryPage / DepartmentFiles / SharedPage 等共用。
 * 展示为「库类型 + 访问权限」双标签，便于区分仅自己 / 指定成员 / 指定部门 / 所属部门 / 公开等模式。
 */

function normVis(lib) {
  return String(lib?.visibility || '').toLowerCase()
}

export function isDepartmentLibrary(lib) {
  const vis = normVis(lib)
  if (vis === 'department') return true
  return lib?.department_id != null || !!lib?.department_name
}

export function hasLibraryMembers(lib) {
  return Number(lib?.member_count || 0) > 0
}

export function accessDepartmentCount(lib) {
  const ids = lib?.access_department_ids
  if (Array.isArray(ids) && ids.length) return ids.length
  const names = lib?.access_department_names
  if (Array.isArray(names) && names.length) return names.length
  return 0
}

/** 库归属：个人库 / 部门库 */
export function libraryCategoryText(lib) {
  return isDepartmentLibrary(lib) ? '部门库' : '个人库'
}

export function libraryCategoryClass(lib) {
  return isDepartmentLibrary(lib) ? 'type-dept' : 'type-personal'
}

/** 访问权限模式文案 */
export function libraryAccessModeText(lib) {
  const vis = normVis(lib)
  const hasMembers = hasLibraryMembers(lib)
  const deptCount = accessDepartmentCount(lib)

  if (vis === 'public') return '公开'
  if (vis === 'departments') {
    const base = deptCount > 0 ? `指定部门·${deptCount}` : '指定部门'
    return hasMembers ? `${base}+成员` : base
  }
  if (vis === 'department') {
    return hasMembers ? '所属部门+成员' : '所属部门'
  }
  return hasMembers ? '指定成员' : '仅自己'
}

/** 访问权限模式样式 */
export function libraryAccessModeClass(lib) {
  const vis = normVis(lib)
  const hasMembers = hasLibraryMembers(lib)
  if (vis === 'public') return 'type-access-public'
  if (vis === 'departments') {
    return hasMembers ? 'type-access-departments-members' : 'type-access-departments'
  }
  if (vis === 'department') {
    return hasMembers ? 'type-access-dept-members' : 'type-access-dept'
  }
  return hasMembers ? 'type-access-members' : 'type-access-self'
}

/** @deprecated 单标签兼容；新界面请用 LibraryTypeTags 双标签 */
export function libraryTypeText(lib) {
  return `${libraryCategoryText(lib)} · ${libraryAccessModeText(lib)}`
}

/** @deprecated 请用 libraryCategoryClass / libraryAccessModeClass */
export function libraryTypeClass(lib) {
  return libraryCategoryClass(lib)
}
