<template>
  <Teleport to="body">
    <Transition name="comment-drawer">
      <div v-if="open" class="comment-drawer-root">
        <div class="comment-drawer-backdrop" @click="$emit('close')" />
        <aside class="comment-drawer-panel" role="dialog" aria-label="文件评论">
          <header class="comment-drawer-header">
            <div class="comment-drawer-header-main">
              <span class="comment-drawer-icon" aria-hidden="true">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                </svg>
              </span>
              <div>
                <h3 class="comment-drawer-title">文件评论</h3>
                <p v-if="context && !loadingContext" class="comment-drawer-subtitle">
                  {{ comments.length ? `${comments.length} 条讨论` : '与同事一起讨论此文件' }}
                </p>
              </div>
            </div>
            <button type="button" class="comment-drawer-close" aria-label="关闭" @click="$emit('close')">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M18 6L6 18M6 6l12 12" />
              </svg>
            </button>
          </header>

          <div v-if="loadingContext" class="comment-drawer-loading">
            <span class="comment-spinner" />
            加载中…
          </div>
          <div v-else-if="contextErr" class="comment-drawer-error">{{ contextErr }}</div>
          <template v-else-if="context">
            <section class="comment-file-meta">
              <div class="comment-file-card">
                <span class="comment-file-icon" aria-hidden="true">📄</span>
                <div class="comment-file-info">
                  <div class="comment-file-name" :title="context.path">{{ context.filename }}</div>
                  <div class="comment-file-badges">
                    <span v-if="context.library_name" class="comment-badge">{{ context.library_name }}</span>
                    <span v-if="context.version_no != null" class="comment-badge muted">v{{ context.version_no }}</span>
                  </div>
                </div>
              </div>
              <dl class="comment-meta-grid">
                <div v-if="context.uploaded_by" class="comment-meta-row">
                  <dt>上传者</dt><dd>{{ context.uploaded_by }}</dd>
                </div>
                <div v-if="context.uploaded_at" class="comment-meta-row">
                  <dt>上传时间</dt><dd>{{ formatDateTimeShanghai(context.uploaded_at) }}</dd>
                </div>
              </dl>
            </section>

            <section class="comment-list-section">
              <p v-if="commentsLoading" class="comment-hint">
                <span class="comment-spinner sm" />
                评论加载中…
              </p>
              <div v-else-if="!comments.length" class="comment-empty">
                <div class="comment-empty-icon" aria-hidden="true">💬</div>
                <p class="comment-empty-title">还没有评论</p>
                <p class="comment-empty-desc">输入 @ 可提及有权限查看此文件的同事；继续输入姓名可搜索更多人</p>
              </div>
              <div v-else class="comment-list">
                <article v-for="c in comments" :key="c.id" class="comment-thread">
                  <div class="comment-card">
                    <div class="comment-item-head">
                      <span class="comment-avatar">{{ userAvatarLetter(c.author?.username) }}</span>
                      <div class="comment-item-meta">
                        <span class="comment-author">{{ c.author?.username || '用户' }}</span>
                        <span class="comment-time" :title="formatDateExact(c.created_at)">{{ formatDate(c.created_at) }}</span>
                      </div>
                    </div>
                    <div class="comment-body" v-html="renderBody(c.body, c.mentions)" />
                    <div class="comment-item-actions">
                      <button type="button" class="comment-link-btn" @click="startReply(c)">回复</button>
                      <button
                        v-if="c.can_delete"
                        type="button"
                        class="comment-link-btn danger"
                        @click="removeComment(c)"
                      >
                        删除
                      </button>
                    </div>
                  </div>
                  <div v-if="c.replies?.length" class="comment-replies">
                    <div v-for="r in c.replies" :key="r.id" class="comment-card is-nested">
                      <div class="comment-item-head">
                        <span class="comment-avatar sm">{{ userAvatarLetter(r.author?.username) }}</span>
                        <div class="comment-item-meta">
                          <span class="comment-author">{{ r.author?.username || '用户' }}</span>
                          <span class="comment-time" :title="formatDateExact(r.created_at)">{{ formatDate(r.created_at) }}</span>
                        </div>
                      </div>
                      <div class="comment-body" v-html="renderBody(r.body, r.mentions)" />
                      <div class="comment-item-actions">
                        <button type="button" class="comment-link-btn" @click="startReply(r)">回复</button>
                        <button
                          v-if="r.can_delete"
                          type="button"
                          class="comment-link-btn danger"
                          @click="removeComment(r)"
                        >
                          删除
                        </button>
                      </div>
                    </div>
                  </div>
                </article>
              </div>
            </section>

            <footer class="comment-compose">
              <div v-if="replyTo" class="comment-reply-banner">
                <span>回复 <strong>{{ replyTo.author?.username }}</strong></span>
                <button type="button" class="comment-link-btn" @click="cancelReply">取消</button>
              </div>
              <div class="comment-input-wrap">
                <textarea
                  ref="textareaRef"
                  v-model="draft"
                  class="comment-textarea"
                  rows="3"
                  :placeholder="replyTo ? '写下回复，输入 @ 可提及他人…' : '写下评论，输入 @ 可提及他人…'"
                  @input="onInput"
                  @keydown="onKeydown"
                />
                <div v-if="mentionOpen" class="comment-mention-panel">
                  <div class="comment-mention-head">提及成员</div>
                  <p v-if="mentionLoading" class="comment-mention-empty">
                    <span class="comment-spinner sm" />
                    搜索中…
                  </p>
                  <template v-else-if="mentionCandidates.length">
                    <button
                      v-for="(u, idx) in mentionCandidates"
                      :key="u.id"
                      type="button"
                      class="comment-mention-option"
                      :class="{ active: idx === mentionIndex }"
                      @mousedown.prevent="pickMention(u)"
                    >
                      <span class="comment-avatar sm">{{ userAvatarLetter(u.username) }}</span>
                      <span class="comment-mention-text">
                        <span class="comment-mention-name">{{ u.username }}</span>
                        <span v-if="u.email" class="comment-mention-email">{{ u.email }}</span>
                      </span>
                    </button>
                  </template>
                  <p v-else class="comment-mention-empty">暂无可 @ 的成员</p>
                </div>
              </div>
              <p v-if="composeErr" class="comment-compose-err">{{ composeErr }}</p>
              <button
                type="button"
                class="comment-submit-btn"
                :disabled="submitting || !draft.trim()"
                @click="submitComment"
              >
                {{ submitting ? '发送中…' : (replyTo ? '发送回复' : '发表评论') }}
              </button>
            </footer>
          </template>
        </aside>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'
import * as api from '../api/client'
import { avatarLetter as userAvatarLetter } from '../utils/userAvatar'
import { formatRelativeTimeZh, formatDateTimeShanghai } from '../utils/dateTime'

const props = defineProps({
  open: { type: Boolean, default: false },
  entryId: { type: [Number, String, null], default: null },
})

defineEmits(['close'])

const loadingContext = ref(false)
const contextErr = ref('')
const context = ref(null)
const comments = ref([])
const commentsLoading = ref(false)
const draft = ref('')
const composeErr = ref('')
const submitting = ref(false)
const replyTo = ref(null)
const textareaRef = ref(null)

const mentionOpen = ref(false)
const mentionLoading = ref(false)
const mentionCandidates = ref([])
const mentionIndex = ref(0)
const mentionIds = ref([])
const mentionStart = ref(-1)

function renderBody(body, mentions) {
  let text = escapeHtml(body || '')
  for (const m of mentions || []) {
    const name = escapeHtml(m.username || '')
    text = text.replace(
      new RegExp(`@${name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}`, 'g'),
      `<span class="comment-mention">@${name}</span>`,
    )
  }
  return text.replace(/\n/g, '<br/>')
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function formatDate(s) {
  return formatRelativeTimeZh(s)
}

function formatDateExact(s) {
  return formatDateTimeShanghai(s, '')
}

async function loadAll() {
  const id = props.entryId
  if (!id) return
  loadingContext.value = true
  contextErr.value = ''
  context.value = null
  comments.value = []
  try {
    const [ctx, list] = await Promise.all([
      api.getFileCommentContext(id),
      api.listFileComments(id),
    ])
    context.value = ctx
    comments.value = Array.isArray(list) ? list : []
  } catch (e) {
    contextErr.value = e.message || '加载失败'
  } finally {
    loadingContext.value = false
    commentsLoading.value = false
  }
}

watch(
  () => [props.open, props.entryId],
  ([open, id]) => {
    if (open && id) {
      draft.value = ''
      replyTo.value = null
      mentionIds.value = []
      mentionOpen.value = false
      composeErr.value = ''
      loadAll()
    }
  },
)

function startReply(c) {
  replyTo.value = c
  draft.value = `@${c.author?.username || ''} `
  if (c.author?.id && !mentionIds.value.includes(c.author.id)) {
    mentionIds.value.push(c.author.id)
  }
  nextTick(() => textareaRef.value?.focus())
}

function cancelReply() {
  replyTo.value = null
}

async function removeComment(c) {
  if (!c?.id) return
  if (!window.confirm('确定删除这条评论吗？')) return
  try {
    await api.deleteFileComment(c.id)
    await loadAll()
  } catch (e) {
    composeErr.value = e.message || '删除失败'
  }
}

function onInput() {
  syncMentionsFromDraft()
  const el = textareaRef.value
  if (!el) return
  const pos = el.selectionStart
  const before = draft.value.slice(0, pos)
  const at = before.lastIndexOf('@')
  if (at >= 0) {
    const seg = before.slice(at + 1)
    if (!seg.includes(' ') && !seg.includes('\n')) {
      mentionStart.value = at
      fetchMentions(seg)
      return
    }
  }
  mentionOpen.value = false
}

function onKeydown(e) {
  if (!mentionOpen.value) return
  if (mentionLoading.value) return
  if (!mentionCandidates.value.length) return
  if (e.key === 'ArrowDown') {
    e.preventDefault()
    mentionIndex.value = (mentionIndex.value + 1) % mentionCandidates.value.length
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    mentionIndex.value = (mentionIndex.value - 1 + mentionCandidates.value.length) % mentionCandidates.value.length
  } else if (e.key === 'Enter') {
    e.preventDefault()
    pickMention(mentionCandidates.value[mentionIndex.value])
  } else if (e.key === 'Escape') {
    mentionOpen.value = false
  }
}

let mentionTimer = null
function fetchMentions(q) {
  clearTimeout(mentionTimer)
  mentionOpen.value = true
  mentionLoading.value = true
  mentionTimer = setTimeout(async () => {
    if (!props.entryId) {
      mentionLoading.value = false
      mentionOpen.value = false
      return
    }
    try {
      const rows = await api.listFileCommentMentionCandidates(props.entryId, q)
      mentionCandidates.value = Array.isArray(rows) ? rows : []
      mentionIndex.value = 0
    } catch {
      mentionCandidates.value = []
    } finally {
      mentionLoading.value = false
    }
  }, 150)
}

function pickMention(u) {
  if (!u) return
  const start = mentionStart.value
  const el = textareaRef.value
  const pos = el?.selectionStart ?? draft.value.length
  const name = u.username || ''
  draft.value = `${draft.value.slice(0, start)}@${name} ${draft.value.slice(pos)}`
  if (!mentionIds.value.includes(u.id)) mentionIds.value.push(u.id)
  mentionOpen.value = false
  nextTick(() => {
    if (el) {
      const np = start + name.length + 2
      el.focus()
      el.setSelectionRange(np, np)
    }
  })
}

function syncMentionsFromDraft() {
  const ids = [...mentionIds.value]
  mentionIds.value = ids.filter(id => {
    const hit = mentionCandidates.value.find(u => u.id === id)
    if (hit?.username && draft.value.includes(`@${hit.username}`)) return true
    return draft.value.includes('@')
  })
}

async function submitComment() {
  const id = props.entryId
  const text = draft.value.trim()
  if (!id || !text) return
  submitting.value = true
  composeErr.value = ''
  try {
    const ids = new Set(mentionIds.value)
    const mentionTokens = [...text.matchAll(/@([^\s@]+)/g)].map(m => m[1]).filter(Boolean)
    for (const token of mentionTokens) {
      try {
        const rows = await api.listFileCommentMentionCandidates(id, token)
        for (const u of rows || []) {
          if (u.username === token || u.email === token) ids.add(u.id)
        }
      } catch {
        /* 忽略单条搜索失败 */
      }
    }
    await api.createFileComment(id, {
      body: text,
      parent_id: replyTo.value?.id ?? null,
      mention_user_ids: [...ids],
    })
    draft.value = ''
    replyTo.value = null
    mentionIds.value = []
    await loadAll()
  } catch (e) {
    composeErr.value = e.message || '发送失败'
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.comment-drawer-root {
  position: fixed;
  inset: 0;
  z-index: 1200;
  pointer-events: none;
}
.comment-drawer-backdrop {
  position: absolute;
  inset: 0;
  background: rgba(15, 23, 42, 0.4);
  backdrop-filter: blur(2px);
  pointer-events: auto;
}
.comment-drawer-panel {
  position: absolute;
  top: 0;
  right: 0;
  width: min(440px, 100vw);
  height: 100%;
  background: #f8fafc;
  box-shadow: -12px 0 40px rgba(15, 23, 42, 0.14);
  display: flex;
  flex-direction: column;
  pointer-events: auto;
}
.comment-drawer-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 18px 20px;
  background: linear-gradient(135deg, #1e40af 0%, #2563eb 55%, #3b82f6 100%);
  color: #fff;
}
.comment-drawer-header-main {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  min-width: 0;
}
.comment-drawer-icon {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.18);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.comment-drawer-icon svg {
  width: 20px;
  height: 20px;
}
.comment-drawer-title {
  margin: 0;
  font-size: 17px;
  font-weight: 600;
  letter-spacing: 0.02em;
}
.comment-drawer-subtitle {
  margin: 4px 0 0;
  font-size: 12px;
  opacity: 0.85;
}
.comment-drawer-close {
  border: none;
  background: rgba(255, 255, 255, 0.15);
  width: 32px;
  height: 32px;
  border-radius: 8px;
  color: #fff;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: background 0.15s;
}
.comment-drawer-close:hover {
  background: rgba(255, 255, 255, 0.25);
}
.comment-drawer-close svg {
  width: 16px;
  height: 16px;
}
.comment-drawer-loading,
.comment-drawer-error {
  padding: 32px 20px;
  color: #64748b;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}
.comment-drawer-error { color: #dc2626; }
.comment-spinner {
  width: 18px;
  height: 18px;
  border: 2px solid #e2e8f0;
  border-top-color: #2563eb;
  border-radius: 50%;
  animation: comment-spin 0.7s linear infinite;
}
.comment-spinner.sm {
  width: 14px;
  height: 14px;
}
@keyframes comment-spin {
  to { transform: rotate(360deg); }
}
.comment-file-meta {
  padding: 16px 20px;
  background: #fff;
  border-bottom: 1px solid #e2e8f0;
}
.comment-file-card {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px 14px;
  background: #f1f5f9;
  border-radius: 12px;
  border: 1px solid #e2e8f0;
}
.comment-file-icon {
  font-size: 22px;
  line-height: 1;
  flex-shrink: 0;
}
.comment-file-info {
  min-width: 0;
  flex: 1;
}
.comment-file-name {
  font-size: 15px;
  font-weight: 600;
  color: #0f172a;
  word-break: break-all;
  line-height: 1.4;
}
.comment-file-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}
.comment-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 500;
  color: #1d4ed8;
  background: #dbeafe;
}
.comment-badge.muted {
  color: #475569;
  background: #e2e8f0;
}
.comment-meta-grid {
  margin: 12px 0 0;
  display: grid;
  gap: 6px;
}
.comment-meta-row {
  display: grid;
  grid-template-columns: 64px 1fr;
  gap: 8px;
  font-size: 12px;
}
.comment-meta-row dt { color: #94a3b8; margin: 0; }
.comment-meta-row dd { color: #475569; margin: 0; }
.comment-list-section {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px;
}
.comment-hint {
  color: #94a3b8;
  font-size: 13px;
  text-align: center;
  padding: 32px 0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}
.comment-empty {
  text-align: center;
  padding: 40px 16px;
}
.comment-empty-icon {
  font-size: 36px;
  margin-bottom: 12px;
  opacity: 0.7;
}
.comment-empty-title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: #334155;
}
.comment-empty-desc {
  margin: 6px 0 0;
  font-size: 13px;
  color: #94a3b8;
}
.comment-thread + .comment-thread {
  margin-top: 14px;
}
.comment-card {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 12px 14px;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}
.comment-card.is-nested {
  background: #f8fafc;
}
.comment-replies {
  margin: 10px 0 0 20px;
  padding-left: 14px;
  border-left: 2px solid #cbd5e1;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.comment-item-head {
  display: flex;
  align-items: center;
  gap: 10px;
}
.comment-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: #4a90e2;
  color: #fff;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
  flex-shrink: 0;
}
.comment-avatar.sm {
  width: 28px;
  height: 28px;
  font-size: 12px;
}
.comment-item-meta {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.comment-author {
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
}
.comment-time {
  font-size: 11px;
  color: #94a3b8;
}
.comment-body {
  margin: 10px 0 0;
  font-size: 14px;
  line-height: 1.6;
  color: #334155;
  word-break: break-word;
}
.comment-body :deep(.comment-mention) {
  color: #2563eb;
  font-weight: 600;
  background: #eff6ff;
  padding: 1px 4px;
  border-radius: 4px;
}
.comment-item-actions {
  margin-top: 8px;
  display: flex;
  gap: 14px;
}
.comment-link-btn {
  border: none;
  background: none;
  padding: 0;
  font-size: 12px;
  color: #2563eb;
  cursor: pointer;
  font-weight: 500;
}
.comment-link-btn:hover {
  text-decoration: underline;
}
.comment-link-btn.danger { color: #dc2626; }
.comment-compose {
  border-top: 1px solid #e2e8f0;
  padding: 14px 20px 20px;
  background: #fff;
  box-shadow: 0 -4px 16px rgba(15, 23, 42, 0.04);
}
.comment-reply-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 10px;
  padding: 8px 12px;
  border-radius: 8px;
  background: #eff6ff;
  font-size: 12px;
  color: #475569;
}
.comment-reply-banner strong {
  color: #1d4ed8;
}
.comment-input-wrap {
  position: relative;
}
.comment-textarea {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid #cbd5e1;
  border-radius: 12px;
  padding: 12px 14px;
  font-size: 14px;
  line-height: 1.5;
  resize: vertical;
  min-height: 80px;
  background: #f8fafc;
  transition: border-color 0.15s, box-shadow 0.15s, background 0.15s;
}
.comment-textarea:focus {
  outline: none;
  border-color: #3b82f6;
  background: #fff;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.15);
}
.comment-mention-panel {
  position: absolute;
  left: 0;
  right: 0;
  bottom: calc(100% + 6px);
  max-height: 220px;
  overflow-y: auto;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  box-shadow: 0 12px 32px rgba(15, 23, 42, 0.14);
  z-index: 2;
}
.comment-mention-head {
  padding: 8px 12px 6px;
  font-size: 11px;
  font-weight: 600;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  border-bottom: 1px solid #f1f5f9;
}
.comment-mention-empty {
  margin: 0;
  padding: 14px 12px;
  font-size: 12px;
  color: #94a3b8;
  display: flex;
  align-items: center;
  gap: 6px;
}
.comment-mention-option {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  border: none;
  background: #fff;
  padding: 10px 12px;
  text-align: left;
  cursor: pointer;
  transition: background 0.12s;
}
.comment-mention-option:hover,
.comment-mention-option.active {
  background: #eff6ff;
}
.comment-mention-text {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
}
.comment-mention-name {
  font-size: 13px;
  font-weight: 600;
  color: #0f172a;
}
.comment-mention-email {
  font-size: 11px;
  color: #94a3b8;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.comment-compose-err {
  margin: 8px 0 0;
  font-size: 12px;
  color: #dc2626;
}
.comment-submit-btn {
  margin-top: 12px;
  width: 100%;
  border: none;
  border-radius: 10px;
  padding: 11px 14px;
  font-size: 14px;
  font-weight: 600;
  color: #fff;
  background: linear-gradient(135deg, #2563eb, #1d4ed8);
  cursor: pointer;
  box-shadow: 0 4px 12px rgba(37, 99, 235, 0.28);
  transition: opacity 0.15s, transform 0.12s;
}
.comment-submit-btn:hover:not(:disabled) {
  transform: translateY(-1px);
}
.comment-submit-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  box-shadow: none;
  transform: none;
}
.comment-drawer-enter-active,
.comment-drawer-leave-active {
  transition: opacity 0.2s ease;
}
.comment-drawer-enter-active .comment-drawer-panel,
.comment-drawer-leave-active .comment-drawer-panel {
  transition: transform 0.24s ease;
}
.comment-drawer-enter-from,
.comment-drawer-leave-to {
  opacity: 0;
}
.comment-drawer-enter-from .comment-drawer-panel,
.comment-drawer-leave-to .comment-drawer-panel {
  transform: translateX(100%);
}
</style>
