/** 与 AppTopbar 用户头像一致：中文取首字，英文取大写首字母 */
export function avatarLetter(name) {
  const n = String(name || '').trim()
  if (!n) return '?'
  const first = n[0]
  if (/[\u4e00-\u9fa5]/.test(first)) return first
  return (first || '?').toUpperCase()
}
