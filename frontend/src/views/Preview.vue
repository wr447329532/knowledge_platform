<template>
  <div class="preview-page">
    <div class="preview-header">
      <button type="button" class="btn-back" @click="goBack">← 返回</button>
      <div class="preview-title">
        <div class="preview-filename" :title="meta?.filename || ''">{{ meta?.filename || '预览' }}</div>
        <div class="preview-sub">
          <span v-if="meta?.preview_type === 'pdf'">{{
            fileTypeLabel(meta.filename)
          }} · 共 {{ meta.page_count || 0 }} 页 · 第 {{ pdfVisiblePage }} 页</span>
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

      <template v-else-if="meta?.preview_type === 'pdf'">
        <div
          ref="pdfScrollRef"
          class="pdf-scroll"
          @scroll.passive="schedulePdfScroll"
        >
          <div
            class="pdf-vlist-phantom"
            :style="{ height: pdfTotalHeightPx + 'px' }"
          >
            <div
              v-for="pn in visiblePdfPagesRender"
              :key="pn"
              class="pdf-page-slot-wrap"
              :style="{
                top: pdfPageTopPx(pn) + 'px',
                left: '12px',
                right: '12px',
              }"
            >
              <div class="pdf-page-slot-inner">
                <div class="pdf-page-head">
                  第 {{ pn }} / {{ meta.page_count }} 页
                </div>
                <div
                  v-if="pdfPageErr[pn]"
                  class="pdf-page-error"
                >
                  {{ pdfPageErr[pn] }}
                </div>
                <img
                  v-else-if="pdfPageUrls[pn]"
                  :src="pdfPageUrls[pn]"
                  class="preview-img pdf-page-img"
                  :alt="`第${pn}页`"
                  @load="(e) => recordPdfMeasuredHeight(pn, e)"
                />
                <div
                  v-else
                  class="pdf-page-skeleton"
                  :style="{ minHeight: Math.max(200, skeletonMinHeightPx) + 'px' }"
                >
                  第 {{ pn }} 页加载中…
                </div>
              </div>
            </div>
          </div>
        </div>
      </template>

      <template v-else-if="meta?.preview_type === 'image'">
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
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter, onBeforeRouteLeave } from 'vue-router'
import * as api from '../api/client'

/** 两侧留白与卡片内边，与样式一致时可微调 */
const PDF_SCROLL_HORIZONTAL_GUTTER = 48

const OVERSCAN_RENDER = 4
/** 滚动时顺带预取的页缓冲（不参与 DOM 挂载） */
const PREFETCH_EXTRA = 10
/** 收回远离视图的 blob URL，避免超长文档占用内存过大 */
const EVICT_MARGIN_PAGES = 45
/** 同域预览并发上限，避免霸占浏览器 HTTP/1 连接槽（常见于 6）导致返回首页后 listFiles/getDepartmentTree 长时间挂起 */
const PREVIEW_BLOB_FETCH_CAP = 4

const route = useRoute()
const router = useRouter()

const loading = ref(true)
const err = ref('')
const meta = ref(null)
const imgUrl = ref('')
const textContent = ref('')
const me = ref(null)

const pdfScrollRef = ref(null)
/** @type {import('vue').Ref<Record<number, string>>} */
const pdfPageUrls = ref({})
/** @type {import('vue').Ref<Record<number, string>>} */
const pdfPageErr = ref({})
/** @type {import('vue').Ref<Record<number, number>>} px，整卡实际高度（含卡片 margin） */
const pdfMeasuredSlotHeights = ref({})

const pdfScrollTop = ref(0)
const pdfViewportH = ref(600)
/** 用于估算未测量页高度的内容区宽度（与 .pdf-scroll 可视宽度对齐） */
const pdfInnerWidth = ref(780)

const pdfVisiblePage = ref(1)

const pdfEstimatedSlotPx = computed(() => {
  const w = Math.max(
    360,
    (pdfInnerWidth.value || pdfScrollRef.value?.clientWidth || 800)
      - PDF_SCROLL_HORIZONTAL_GUTTER,
  )
  /** 粗略按 A4 竖向比例预估图片区高度（head + padding 已折算进常数） */
  return Math.ceil(54 + (w * 11) / 8.5)
})

const skeletonMinHeightPx = computed(() =>
  Math.max(180, pdfEstimatedSlotPx.value - 48),
)

const pdfTotalHeightPx = computed(() => {
  const n = meta.value?.page_count ?? 0
  const cum = pdfCumulativeTopsInternal.value.arr
  if (n <= 0) return 0
  return cum[n]
})

function pdfPageTopPx(pn) {
  const cum = pdfCumulativeTopsInternal.value.arr
  return cum[pn - 1] ?? 0
}

/**
 * cumulativeStart[i] = 第 i+1 页顶边距 phantom 顶的偏移；cumulativeStart[0]=0；
 * cumulativeStart[p] = 第 p+1 页起点 = 前 p 页高度之和。页码 pn 顶端 = arr[pn-1]。
 */
const pdfCumulativeTopsInternal = computed(() => {
  const total = meta.value?.page_count || 0
  const measured = pdfMeasuredSlotHeights.value
  const est = pdfEstimatedSlotPx.value
  const arr = new Array(total + 1)
  arr[0] = 0
  for (let p = 1; p <= total; p++) {
    const slotH =
      measured[p] != null && measured[p] > 0 ? measured[p] : est
    arr[p] = arr[p - 1] + slotH
  }
  return { arr, total }
})

function findVisibleRange(scrollTopVal, viewportHVal, cumulativeArr, n) {
  if (n <= 0) return { first: 1, last: 1 }

  if (scrollTopVal >= cumulativeArr[n]) {
    const first = Math.max(1, n - OVERSCAN_RENDER)
    return { first, last: n, focusFirst: n }
  }

  let lo = 1
  let hi = n
  let first = n
  while (lo <= hi) {
    const mid = (lo + hi) >> 1
    if (cumulativeArr[mid] > scrollTopVal) {
      first = mid
      hi = mid - 1
    } else lo = mid + 1
  }

  const bottom = scrollTopVal + viewportHVal
  lo = first
  hi = n
  let last = first
  while (lo <= hi) {
    const mid = (lo + hi) >> 1
    /** 页 mid 占位 [cum[mid-1], cum[mid]) */
    const topY = cumulativeArr[mid - 1]
    if (topY < bottom) {
      last = mid
      lo = mid + 1
    } else hi = mid - 1
  }

  let a = Math.max(1, first - OVERSCAN_RENDER)
  let b = Math.min(n, last + OVERSCAN_RENDER)
  if (first > last) {
    const t = Math.max(1, Math.min(n, first))
    a = Math.max(1, t - OVERSCAN_RENDER)
    b = Math.min(n, t + OVERSCAN_RENDER)
  }
  return { first: a, last: b, focusFirst: first }
}

function visiblePnRange(scrollTopVal, viewportHVal) {
  const n = meta.value?.page_count || 0
  const cumulativeArr = pdfCumulativeTopsInternal.value.arr
  return findVisibleRange(scrollTopVal, viewportHVal, cumulativeArr, n)
}

const visiblePdfPagesRender = computed(() => {
  const n = meta.value?.page_count || 0
  if (meta.value?.preview_type !== 'pdf' || n < 1) return []

  const { first, last } = visiblePnRange(pdfScrollTop.value, pdfViewportH.value)

  const out = []
  for (let pn = first; pn <= last; pn++) out.push(pn)
  return out
})

const watermarkText = computed(() => me.value?.email || '')
const watermarkBg = computed(() => {
  if (!watermarkText.value) return ''
  const text = watermarkText.value
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

function revokeAllPdfUrls() {
  Object.values(pdfPageUrls.value).forEach((u) => {
    try {
      URL.revokeObjectURL(u)
    } catch {
      /* ignore */
    }
  })
  pdfPageUrls.value = {}
  pdfPageErr.value = {}
  pdfMeasuredSlotHeights.value = {}
}

const inflightPdf = new Set()
/** @type {AbortController | null} */
let previewBlobAbortController = null
let previewBlobSlots = 0

function teardownPreviewNetwork() {
  previewBlobAbortController?.abort()
  previewBlobAbortController = null
  previewBlobSlots = 0
  inflightPdf.clear()
}

async function loadPdfPage(pn) {
  const id = entryId()
  if (!id || !meta.value || meta.value.preview_type !== 'pdf') return
  const n = meta.value.page_count || 0
  if (pn < 1 || pn > n) return
  if (
    previewBlobAbortController == null ||
    previewBlobAbortController.signal.aborted
  ) return
  if (inflightPdf.has(pn) || pdfPageUrls.value[pn]) return
  if (previewBlobSlots >= PREVIEW_BLOB_FETCH_CAP) return

  previewBlobSlots++
  inflightPdf.add(pn)
  const signal = previewBlobAbortController.signal
  try {
    const blob = await api.fetchRenderedPreviewBlob(id, {
      version_no: versionNo(),
      page: pn,
      signal,
    })
    const url = URL.createObjectURL(blob)
    pdfPageUrls.value = { ...pdfPageUrls.value, [pn]: url }
  } catch (e) {
    if (e?.name === 'AbortError') return
    pdfPageErr.value = {
      ...pdfPageErr.value,
      [pn]: e.message || '加载失败',
    }
  } finally {
    inflightPdf.delete(pn)
    previewBlobSlots = Math.max(0, previewBlobSlots - 1)
  }
}

/** 卸载远离视图的 blob，保留实测高度以降低来回滚动时滚动条抖动 */
function evictPdfPagesOutside(prefetchLo, prefetchHi) {
  const total = meta.value?.page_count || 0
  if (total <= 0) return
  const safeLo = Math.max(1, prefetchLo - EVICT_MARGIN_PAGES)
  const safeHi = Math.min(total, prefetchHi + EVICT_MARGIN_PAGES)
  const urls = pdfPageUrls.value
  /** @type {Record<number, string>} */
  const next = { ...urls }
  /** @type {Record<number, string>} */
  const nextErr = { ...pdfPageErr.value }

  Object.keys(next).forEach((k) => {
    const pn = Number(k)
    if (pn >= safeLo && pn <= safeHi) return
    try {
      URL.revokeObjectURL(next[pn])
    } catch {
      /* ignore */
    }
    delete next[pn]
    delete nextErr[pn]
  })
  pdfPageUrls.value = next
  pdfPageErr.value = nextErr
}

function schedulePdfLoadsForRange(prefetchLo, prefetchHi) {
  const total = meta.value?.page_count || 0
  const lo = Math.max(1, prefetchLo)
  const hi = Math.min(total, prefetchHi)
  for (let p = lo; p <= hi; p++) void loadPdfPage(p)
}

let pdfScrollFrame = 0

function flushPdfScroll() {
  pdfScrollFrame = 0
  const el = pdfScrollRef.value
  if (!el || meta.value?.preview_type !== 'pdf') return
  pdfScrollTop.value = el.scrollTop
  pdfViewportH.value = el.clientHeight
  pdfInnerWidth.value = el.clientWidth

  const n = meta.value.page_count || 0
  if (n < 1) return

  const { first: visFirst, last: visLast, focusFirst } = visiblePnRange(
    pdfScrollTop.value,
    pdfViewportH.value,
  )

  pdfVisiblePage.value = focusFirst

  const prefetchLo = Math.max(1, visFirst - PREFETCH_EXTRA)
  const prefetchHi = Math.min(n, visLast + PREFETCH_EXTRA)
  schedulePdfLoadsForRange(prefetchLo, prefetchHi)
  evictPdfPagesOutside(prefetchLo, prefetchHi)
}

function schedulePdfScroll() {
  if (pdfScrollFrame) return
  pdfScrollFrame = requestAnimationFrame(flushPdfScroll)
}

/** 图片就位后校准该页占位高度（减少滚动条拖动） */
function recordPdfMeasuredHeight(pn, ev) {
  const img = ev?.target
  if (!img || img.tagName !== 'IMG') return
  const wrap = img.closest('.pdf-page-slot-wrap')
  if (!wrap) return
  const el = wrap.querySelector('.pdf-page-slot-inner')
  const hRaw = el ? el.offsetHeight : wrap.offsetHeight
  const mb = getPdfSlotMarginBelowPx()
  const h = Math.ceil(hRaw + mb)
  const prev = pdfMeasuredSlotHeights.value[pn]
  if (prev != null && Math.abs(prev - h) <= 2) return
  pdfMeasuredSlotHeights.value = { ...pdfMeasuredSlotHeights.value, [pn]: h }

  queueMicrotask(() => {
    schedulePdfScroll()
  })
}

/** 对应 .pdf-page-slot-wrap:last-child{margin-bottom:0} 以外卡片的下边距（与 CSS mb 对齐） */
function getPdfSlotMarginBelowPx() {
  return PDF_SLOT_MARGIN_CSS
}

/** 必须与下方样式 .pdf-page-slot-wrap { margin-bottom } 保持一致 */
const PDF_SLOT_MARGIN_CSS = 14

let pdfResizeObserver = null

function attachPdfObservers() {
  detachPdfObservers()
  const el = pdfScrollRef.value
  if (!el) return
  pdfResizeObserver = new ResizeObserver(() => {
    pdfInnerWidth.value = el.clientWidth
    pdfViewportH.value = el.clientHeight
    schedulePdfScroll()
  })
  pdfResizeObserver.observe(el)
}

function detachPdfObservers() {
  pdfResizeObserver?.disconnect()
  pdfResizeObserver = null
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
  teardownPreviewNetwork()
  previewBlobAbortController = new AbortController()
  revokeImgUrl()
  revokeAllPdfUrls()
  textContent.value = ''
  pdfVisiblePage.value = 1
  pdfScrollTop.value = 0
  detachPdfObservers()
  pdfScrollFrame && cancelAnimationFrame(pdfScrollFrame)
  pdfScrollFrame = 0

  try {
    if (!me.value) me.value = await api.getMe()
    meta.value = await api.getRenderedPreviewMeta(id, versionNo())

    const t = meta.value.preview_type
    if (t === 'text') {
      textContent.value = await api.fetchRenderedPreviewText(id, versionNo())
    } else if (t === 'image') {
      const blob = await api.fetchRenderedPreviewBlob(id, {
        version_no: versionNo(),
        page: null,
        signal: previewBlobAbortController.signal,
      })
      imgUrl.value = URL.createObjectURL(blob)
    }
  } catch (e) {
    if (e?.name !== 'AbortError') err.value = e.message || '加载失败'
  } finally {
    loading.value = false
  }
}

watch(
  () => [loading.value, meta.value?.preview_type, meta.value?.page_count, route.fullPath],
  async () => {
    if (loading.value) return
    if (meta.value?.preview_type !== 'pdf') {
      detachPdfObservers()
      pdfScrollFrame && cancelAnimationFrame(pdfScrollFrame)
      pdfScrollFrame = 0
      return
    }
    await nextTick()
    const el = pdfScrollRef.value
    if (el) el.scrollTop = 0
    pdfScrollTop.value = 0
    pdfViewportH.value = el?.clientHeight ?? pdfViewportH.value
    pdfInnerWidth.value = el?.clientWidth ?? pdfInnerWidth.value
    attachPdfObservers()
    schedulePdfScroll()
    await flushPdfScrollWrapped()
    const n = meta.value.page_count || 1
    /** 首批与 PREVIEW_BLOB_FETCH_CAP 对齐，避免瞬间超过并发上限导致大量页永远不发起请求 */
    const eagerCount = Math.min(PREVIEW_BLOB_FETCH_CAP, n)
    await Promise.all(
      Array.from({ length: eagerCount }, (_, i) => loadPdfPage(i + 1)),
    )
    schedulePdfScroll()
  },
  { flush: 'post' },
)

async function flushPdfScrollWrapped() {
  await nextTick()
  flushPdfScroll()
}

watch(
  () => pdfEstimatedSlotPx.value,
  () => {
    if (loading.value || meta.value?.preview_type !== 'pdf') return
    schedulePdfScroll()
  },
)

async function download() {
  const id = entryId()
  if (!id) return
  try {
    await api.downloadFile(id, versionNo())
  } catch (e) {
    err.value = e.message || '下载失败'
  }
}

function fileTypeLabel(filename) {
  if (!filename) return 'PDF'
  const ext = filename.split('.').pop()?.toLowerCase()
  const map = {
    pptx: 'PPT',
    ppt: 'PPT',
    docx: 'Word',
    doc: 'Word',
    xlsx: 'Excel',
    xls: 'Excel',
  }
  return map[ext] || 'PDF'
}

function goBack() {
  teardownPreviewNetwork()
  detachPdfObservers()
  if (pdfScrollFrame) cancelAnimationFrame(pdfScrollFrame)
  pdfScrollFrame = 0
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
  if (window.history.length > 1) router.back()
  else router.push('/')
}

onMounted(loadMeta)
watch(() => route.fullPath, loadMeta)
onBeforeRouteLeave(() => {
  teardownPreviewNetwork()
  detachPdfObservers()
  if (pdfScrollFrame) cancelAnimationFrame(pdfScrollFrame)
  pdfScrollFrame = 0
})
onUnmounted(() => {
  teardownPreviewNetwork()
  revokeImgUrl()
  revokeAllPdfUrls()
  detachPdfObservers()
  if (pdfScrollFrame) cancelAnimationFrame(pdfScrollFrame)
})
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
  flex-shrink: 0;
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
  display: flex;
  flex-direction: column;
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

.pdf-scroll {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  background: #f3f4f6;
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 12px;
}

.pdf-vlist-phantom {
  position: relative;
  width: 100%;
  box-sizing: border-box;
}

.pdf-page-slot-wrap {
  position: absolute;
  left: 0;
  right: 0;
  box-sizing: border-box;
}

.pdf-page-slot-inner {
  background: #fff;
  border-radius: 10px;
  padding: 10px 12px 14px;
  border: 1px solid #e5e7eb;
}

.pdf-page-head {
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 8px;
}

.pdf-page-skeleton {
  min-height: 200px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #9ca3af;
  font-size: 14px;
  background: #f9fafb;
  border-radius: 8px;
}

.pdf-page-error {
  color: #b91c1c;
  padding: 24px;
  text-align: center;
  font-size: 14px;
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

.pdf-page-img {
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
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