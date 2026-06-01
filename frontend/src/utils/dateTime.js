/** 解析后端时间（SQLite 常返回无时区的 UTC 字符串） */
export function parseApiDate(s) {
  if (s == null || s === '') return null
  let raw = String(s).trim()
  if (!raw) return null
  if (!raw.endsWith('Z') && !/[+-]\d{2}:\d{2}$/.test(raw)) {
    raw = raw.replace(' ', 'T') + 'Z'
  }
  const d = new Date(raw)
  return Number.isNaN(d.getTime()) ? null : d
}

export function formatDateTimeShanghai(s, fallback = '-') {
  const d = parseApiDate(s)
  if (!d) return s ? String(s) : fallback
  return d.toLocaleString('zh-CN', {
    timeZone: 'Asia/Shanghai',
    hour12: false,
  })
}

/** 评论等场景：优先相对时间，超过 7 天显示绝对时间 */
export function formatRelativeTimeZh(s) {
  const d = parseApiDate(s)
  if (!d) return s ? String(s) : ''
  const diffMs = Date.now() - d.getTime()
  if (diffMs < 60_000) return '刚刚'
  if (diffMs < 3_600_000) return `${Math.floor(diffMs / 60_000)} 分钟前`
  if (diffMs < 86_400_000) {
    const now = new Date()
    const shOpts = { timeZone: 'Asia/Shanghai', hour12: false }
    const dayFmt = new Intl.DateTimeFormat('zh-CN', { ...shOpts, year: 'numeric', month: '2-digit', day: '2-digit' })
    if (dayFmt.format(d) === dayFmt.format(now)) {
      return d.toLocaleTimeString('zh-CN', { ...shOpts, hour: '2-digit', minute: '2-digit' })
    }
  }
  if (diffMs < 7 * 86_400_000) {
    return d.toLocaleString('zh-CN', {
      timeZone: 'Asia/Shanghai',
      weekday: 'short',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    })
  }
  return formatDateTimeShanghai(s, '')
}
