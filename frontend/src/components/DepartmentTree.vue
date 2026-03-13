<template>
  <div class="dept-tree" :data-variant="variant">
    <div class="dept-tree-header">
      <span class="dept-tree-title">组织架构</span>
      <button
        v-if="me?.is_superuser && variant === 'content'"
        type="button"
        class="dept-tree-add"
        title="新建根部门"
        @click="openAdd(null)"
      >
        <Icons name="plus" class="icon-sm" />
      </button>
    </div>
    <p v-if="treeErr" class="dept-tree-err">{{ treeErr }}</p>
    <div v-if="loading" class="dept-tree-loading">加载中...</div>
    <div v-else-if="tree.length === 0" class="dept-tree-empty">暂无部门</div>
    <div v-else class="dept-tree-list">
      <DepartmentTreeNode
        v-for="node in tree"
        :key="node.id"
        :node="node"
        :me="me"
        :variant="variant"
        :expanded-ids="expandedIds"
        :active-dept-id="activeDeptId"
        @toggle="toggle"
        @add="openAdd"
        @edit="openEdit"
        @delete="doDelete"
        @refresh="loadTree"
        @select="onSelect"
      />
    </div>
    <!-- 新建/编辑部门 -->
    <div v-if="showModal" class="modal">
      <div class="card dept-modal-card">
        <h3>{{ editId ? '编辑部门' : '新建部门' }}</h3>
        <div class="form-group">
          <label>名称</label>
          <input v-model="formName" placeholder="部门名称" />
        </div>
        <div v-if="!editId" class="form-group">
          <label>上级部门</label>
          <select v-model="formParentId" class="dept-select">
            <option :value="null">无（根部门）</option>
            <option v-for="opt in parentOptions" :key="opt.id" :value="opt.id">{{ opt.label }}</option>
          </select>
        </div>
        <p v-if="modalErr" class="text-danger">{{ modalErr }}</p>
        <div class="modal-actions">
          <button class="primary" @click="submitModal">确定</button>
          <button @click="closeModal">取消</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import Icons from './Icons.vue'
import DepartmentTreeNode from './DepartmentTreeNode.vue'
import * as api from '../api/client'

const props = defineProps({
  me: Object,
  refreshTrigger: { type: Number, default: 0 },
  variant: { type: String, default: 'sidebar' },
  activeDeptId: { type: Number, default: null },
})
const emit = defineEmits(['select'])
const tree = ref([])
const loading = ref(false)
const expandedIds = ref([])
const showModal = ref(false)
const editId = ref(null)
const formName = ref('')
const formParentId = ref(null)
const modalErr = ref('')
const treeErr = ref('')

function toggle(id) {
  const cur = expandedIds.value
  if (cur.includes(id)) expandedIds.value = cur.filter((x) => x !== id)
  else expandedIds.value = [...cur, id]
}

function flatten(nodes, level = 0) {
  const out = []
  for (const n of nodes) {
    out.push({ id: n.id, name: n.name, level })
    if (n.children?.length) out.push(...flatten(n.children, level + 1))
  }
  return out
}

const parentOptions = computed(() => {
  const flat = flatten(tree.value)
  if (!editId.value) return flat.map(({ id, name, level }) => ({ id, label: '　'.repeat(level) + name }))
  return flat.filter(({ id }) => id !== editId.value).map(({ id, name, level }) => ({ id, label: '　'.repeat(level) + name }))
})

async function loadTree() {
  loading.value = true
  treeErr.value = ''
  try {
    tree.value = await api.getDepartmentTree()
  } catch (e) {
    tree.value = []
    treeErr.value = e.message || '加载失败'
  } finally {
    loading.value = false
  }
}

function onSelect(node) {
  emit('select', node)
}

function openAdd(parentId) {
  editId.value = null
  formName.value = ''
  formParentId.value = parentId
  modalErr.value = ''
  showModal.value = true
}

function openEdit(node) {
  editId.value = node.id
  formName.value = node.name
  formParentId.value = node.parent_id
  modalErr.value = ''
  showModal.value = true
}

function closeModal() {
  showModal.value = false
  editId.value = null
  formName.value = ''
  formParentId.value = null
  modalErr.value = ''
}

async function submitModal() {
  modalErr.value = ''
  const name = formName.value?.trim()
  if (!name) {
    modalErr.value = '请输入部门名称'
    return
  }
  try {
    if (editId.value) {
      await api.updateDepartment(editId.value, { name })
    } else {
      await api.createDepartment(name, formParentId.value, 0)
    }
    closeModal()
    await loadTree()
  } catch (e) {
    modalErr.value = e.message || '操作失败'
  }
}

async function doDelete(node) {
  if (!confirm(`确定删除部门「${node.name}」？其子部门将一并删除。`)) return
  treeErr.value = ''
  try {
    await api.deleteDepartment(node.id)
    await loadTree()
  } catch (e) {
    treeErr.value = e.message || '删除失败'
  }
}

onMounted(loadTree)
watch(() => props.refreshTrigger, () => { if (props.refreshTrigger > 0) loadTree() })
</script>

<style scoped>
.dept-tree {
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.dept-tree-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
  padding: 0 4px;
}
.dept-tree-title {
  font-size: 13px;
  font-weight: 600;
}
.dept-tree[data-variant="sidebar"] .dept-tree-title { color: rgba(156, 163, 175); }
.dept-tree[data-variant="content"] .dept-tree-title { color: var(--text-secondary); }
.dept-tree-add {
  width: 24px;
  height: 24px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: transparent;
  color: rgba(156, 163, 175);
  border-radius: 6px;
  cursor: pointer;
}
.dept-tree-add:hover {
  background: rgba(75, 85, 99, 0.5);
  color: #fff;
}
.icon-sm { width: 14px; height: 14px; }
.dept-tree-err {
  font-size: 12px;
  color: #f87171;
  padding: 4px 4px 8px;
  margin: 0;
}
.dept-tree-loading,
.dept-tree-empty {
  font-size: 13px;
  padding: 8px 4px;
}
.dept-tree[data-variant="sidebar"] .dept-tree-loading,
.dept-tree[data-variant="sidebar"] .dept-tree-empty { color: rgba(156, 163, 175); }
.dept-tree[data-variant="content"] .dept-tree-loading,
.dept-tree[data-variant="content"] .dept-tree-empty { color: var(--text-secondary); }
.dept-tree-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}
.dept-modal-card { min-width: 320px; }
.dept-select { width: 100%; padding: 8px; border-radius: 6px; border: 1px solid var(--border); }
</style>
