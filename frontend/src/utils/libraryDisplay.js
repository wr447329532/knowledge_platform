/**
 * 文件库「类型」文案与样式类 — 与 SharedPage「共享文件库」表格一致。
 * visibility：public / department / private；列表接口可能仅返回 department_id / department_name。
 */
export function libraryTypeText(lib) {
  const vis = String(lib?.visibility || '').toLowerCase()
  if (vis === 'public') return '公开库'
  if (
    vis === 'department' ||
    lib?.department_id != null ||
    lib?.department_name
  ) {
    return '部门库'
  }
  return '个人库'
}

/** 对应全局样式：.shared-library-type.type-public | .type-dept | .type-personal */
export function libraryTypeClass(lib) {
  const vis = String(lib?.visibility || '').toLowerCase()
  if (vis === 'public') return 'type-public'
  if (
    vis === 'department' ||
    lib?.department_id != null ||
    lib?.department_name
  ) {
    return 'type-dept'
  }
  return 'type-personal'
}
