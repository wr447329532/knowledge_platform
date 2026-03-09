<template>
  <tr class="dept-row hover-row">
      <td class="dept-name-cell" :style="{ paddingLeft: (level * 24 + 24) + 'px' }">
        <div class="dept-name-inner">
          <button
            v-if="node.children?.length"
            type="button"
            class="dept-toggle"
            @click="isExpanded = !isExpanded"
          >
            <Icons :name="isExpanded ? 'chevron-down' : 'chevron-right'" class="dept-toggle-icon" />
          </button>
          <span v-else class="dept-toggle-placeholder"></span>
          <Icons name="building" class="dept-row-icon" />
          <span class="dept-row-name">{{ node.name }}</span>
        </div>
      </td>
      <td class="dept-cell dept-cell-center text-sm text-gray-900">{{ node.leader_name || '-' }}</td>
      <td class="dept-cell dept-cell-center text-sm text-gray-900">
        {{ typeof node.user_count === 'number' ? node.user_count : '-' }}
      </td>
      <td class="dept-cell dept-cell-center text-sm text-gray-900">-</td>
      <td class="dept-actions-cell">
        <div v-if="me?.is_superuser" class="dept-actions">
          <button type="button" class="icon-btn" @click="$emit('add', node)" title="新建子部门">
            <Icons name="plus" class="icon-sm" />
          </button>
          <button type="button" class="icon-btn" @click="$emit('edit', node)" title="编辑">
            <Icons name="edit" class="icon-sm" />
          </button>
          <button
            type="button"
            class="icon-btn danger"
            @click="$emit('delete', node)"
            title="删除"
          >
            <Icons name="trash" class="icon-sm" />
          </button>
        </div>
      </td>
    </tr>
    <template v-if="node.children?.length && isExpanded">
      <DepartmentTableRow
        v-for="child in node.children"
        :key="child.id"
        :node="child"
        :level="level + 1"
        :me="me"
        @add="$emit('add', $event)"
        @edit="$emit('edit', $event)"
        @delete="$emit('delete', $event)"
        @refresh="$emit('refresh')"
      />
    </template>
</template>

<script setup>
import { ref } from 'vue'
import Icons from './Icons.vue'
import DepartmentTableRow from './DepartmentTableRow.vue'

defineProps({ node: Object, level: Number, me: Object })
defineEmits(['add', 'edit', 'delete', 'refresh'])

const isExpanded = ref(true)
</script>

<style scoped>
.hover-row {
  border-bottom: 1px solid #e5e7eb;
}
.hover-row:hover {
  background: #f9fafb;
}
.dept-name-cell {
  padding-top: 12px;
  padding-bottom: 12px;
}
.dept-name-inner {
  display: flex;
  align-items: center;
  gap: 8px;
}
.dept-toggle {
  padding: 4px;
  border: none;
  background: none;
  cursor: pointer;
  border-radius: 4px;
  display: inline-flex;
}
.dept-toggle:hover {
  background: #e5e7eb;
}
.dept-toggle-icon {
  width: 16px;
  height: 16px;
  color: #6b7280;
}
.dept-toggle-placeholder {
  width: 24px;
  display: inline-block;
}
.dept-row-icon {
  width: 20px;
  height: 20px;
  color: #4a90e2;
  flex-shrink: 0;
}
.dept-row-name {
  font-weight: 500;
  color: #111827;
}
.dept-cell {
  padding: 12px 24px;
}
.dept-cell-center {
  text-align: center;
}
.dept-actions-cell {
  padding: 12px 24px;
  text-align: right;
}
.dept-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
}
.icon-btn {
  border: none;
  background: transparent;
  padding: 4px;
  border-radius: 6px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #6b7280;
}
.icon-btn:hover {
  background: #f3f4f6;
  color: #111827;
}
.icon-btn.danger {
  color: #dc2626;
}
.icon-btn.danger:hover {
  background: #fee2e2;
  color: #b91c1c;
}
.icon-sm {
  width: 16px;
  height: 16px;
}
</style>
