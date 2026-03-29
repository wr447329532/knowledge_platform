<template>
  <div class="preview-page">
    <div class="preview-header">
      <button type="button" class="btn-back" @click="goBack">← 返回</button>
      <div class="preview-title">
        <div class="preview-filename" :title="meta?.filename || ''">{{ meta?.filename || '预览' }}</div>
        <div class="preview-sub">
          <span v-if="meta?.preview_type === 'pdf'">PDF · {{ page }}/{{ meta.page_count }}</span>
          <span v-else-if="meta?.preview_type === 'image'">图片</span>
          <span v-else-if="meta?.preview_type === 'text'">文本</span>
          <span v-else>不支持预览</span>
        </div>
      </div>
      <div class="preview-actions">
        <button
          v-if="meta?.can_download"
          type="button"
          class="btn-primary"
          @click="download"
        >
          下载原文件
        </button>
        <span v-else class="download-hint">只读预览（不提供原文件下载）</span>
      </div>
    </div>

    <div class="preview-body">
      <div v-if="loading" class="preview-loading">加载中...</div>
      <div v-else-if="err" class="preview-error">{{ err }}</div>

      <template v-else-if="meta?.preview_type === 'pdf' || meta?.preview_type === 'image'">
        <div v-if="meta?.preview_type === 'pdf'" class="pdf-toolbar">
          <button type="button" class="btn-small" :disabled="page <= 1" @click="prevPage">上一页</button>
          <button type="button" class="btn-small" :disabled="page >= (meta?.page_count || 1)" @click="nextPage">下一页</button>
        </div>
        <div class="img-wrap">
          <img v-if="imgUrl" :src="imgUrl" class="preview-img" alt="preview" />
        </div>
      </template>

      <template v-else-if="meta?.preview_type === 'text'">
        <pre class="preview-text">{{ textContent }}</pre>
      </template>

      <template v-else>
        <div class="preview-unsupported">该文件类型暂不支持受控预览</div>
      </template>

      <!-- Watermark overlay: only for text/markdown to avoid blocking reading on images/PDF -->
      <div
        v-if="meta?.preview_type === 'text' && watermarkBg"
        class="preview-watermark"
        :style="{ backgroundImage: watermarkBg }"
        aria-hidden="true"
      />
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import * as api from '../api/client'

const route = useRoute()
const router = useRouter()

const loading = ref(true)
const err = ref('')
const meta = ref(null)
const page = ref(1)
const imgUrl = ref('')
const textContent = ref('')
const me = ref(null)

const watermarkText = computed(() => me.value?.email || '')
const watermarkBg = computed(() => {
  if (!watermarkText.value) return ''
  const text = watermarkText.value
  // SVG watermark pattern, repeatable. Keep ASCII-only to avoid font tofu issues.
  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="420" height="260">
      <g opacity="0.08" transform="translate(0,0) rotate(-30 210 130)">
        <text x="20" y="95" font-size="16" fill="#111827" font-family="Arial, DejaVu Sans, sans-serif">${text}</text>
        <text x="20" y="155" font-size="16" fill="#111827" font-family="Arial, DejaVu Sans, sans-serif">${text}</text>
      </g>
    </svg>
  `.trim()
  const encoded = encodeURIComponent(svg)
  return `url("data:image/svg+xml,${encoded}")`
})

function entryId() {
  const v = route.query.entry_id
  return v ? Number(v) : null
}
function versionNo() {
  const v = route.query.version_no
  if (v == null || v === '') return null
  const n = Number(v)
  return Number.isFinite(n) ? n : null
}

function revokeImgUrl() {
  if (imgUrl.value) {
    URL.revokeObjectURL(imgUrl.value)
    imgUrl.value = ''
  }
}

async function loadMeta() {
  const id = entryId()
  if (!id) {
    err.value = '缺少 entry_id'
    loading.value = false
    return
  }
  loading.value = true
  err.value = ''
  revokeImgUrl()
  textContent.value = ''
  page.value = 1
  try {
    if (!me.value) {
      // 用于水印叠加（仅邮箱）
      me.value = await api.getMe()
    }
    meta.value = await api.getRenderedPreviewMeta(id, versionNo())
    await loadContent()
  } catch (e) {
    err.value = e.message || '加载失败'
  } finally {
    loading.value = false
  }
}

async function loadContent() {
  const id = entryId()
  if (!id || !meta.value) return
  revokeImgUrl()
  textContent.value = ''

  const t = meta.value.preview_type
  if (t === 'text') {
    textContent.value = await api.fetchRenderedPreviewText(id, versionNo())
    return
  }
  if (t === 'pdf' || t === 'image') {
    const blob = await api.fetchRenderedPreviewBlob(id, { version_no: versionNo(), page: t === 'pdf' ? page.value : null })
    imgUrl.value = URL.createObjectURL(blob)
  }
}

function prevPage() {
  if (page.value <= 1) return
  page.value -= 1
}
function nextPage() {
  if (!meta.value) return
  const max = meta.value.page_count || 1
  if (page.value >= max) return
  page.value += 1
}

async function download() {
  const id = entryId()
  if (!id) return
  try {
    await api.downloadFile(id, versionNo())
  } catch (e) {
    err.value = e.message || '下载失败'
  }
}

function goBack() {
  // 优先按来源上下文回到文件库页面
  const q = route.query || {}
  if (q.return_to === 'lib' && q.return_lib_id != null) {
    const nextQuery = {
      return_to: 'lib',
      return_lib_id: String(q.return_lib_id),
    }
    if (q.return_path != null) nextQuery.return_path = String(q.return_path)
    if (q.return_dept_id != null) nextQuery.return_dept_id = String(q.return_dept_id)
    router.push({ path: '/', query: nextQuery })
    return
  }
  // 无上下文时退回上一页，否则回主页
  if (window.history.length > 1) router.back()
  else router.push('/')
}

watch(page, async () => {
  if (meta.value?.preview_type === 'pdf') {
    try {
      await loadContent()
    } catch (e) {
      err.value = e.message || '加载失败'
    }
  }
})

onMounted(loadMeta)
watch(() => route.fullPath, loadMeta)
onUnmounted(revokeImgUrl)
</script>

<style scoped>
.preview-page {
  min-height: 100vh;
  background: var(--bg-page);
  display: flex;
  flex-direction: column;
}
.preview-header {
  background: #fff;
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 10px 16px;
}
.btn-back {
  border-radius: 999px;
  padding: 6px 12px;
}
.preview-title {
  min-width: 0;
  flex: 1;
}
.preview-filename {
  font-weight: 600;
  color: #111827;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.preview-sub {
  font-size: 12px;
  color: #6b7280;
  margin-top: 2px;
}
.preview-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}
.btn-primary {
  background: var(--primary);
  color: #fff;
  border: none;
  border-radius: 999px;
  padding: 8px 14px;
}
.btn-primary:hover {
  background: var(--primary-dark);
}
.download-hint {
  font-size: 12px;
  color: #6b7280;
}
.preview-body {
  flex: 1;
  min-height: 0;
  padding: 14px 16px 20px;
  position: relative;
}
.preview-loading,
.preview-error,
.preview-unsupported {
  padding: 14px;
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 10px;
}
.preview-error {
  color: #b91c1c;
  background: #fef2f2;
  border-color: #fecaca;
}
.pdf-toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 10px;
}
.btn-small {
  padding: 6px 12px;
  border-radius: 999px;
  font-size: 13px;
}
.img-wrap {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 12px;
  overflow: auto;
}
.preview-img {
  max-width: 100%;
  display: block;
  margin: 0 auto;
}
.preview-text {
  white-space: pre-wrap;
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 12px;
  overflow: auto;
  min-height: 200px;
}

.preview-watermark {
  position: absolute;
  inset: 14px 16px 20px 16px;
  pointer-events: none;
  background-repeat: repeat;
  background-size: 420px 260px;
  mix-blend-mode: multiply;
  opacity: 1;
  z-index: 2;
}
</style>

