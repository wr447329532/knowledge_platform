<template>
  <div class="dept-node" :class="'dept-node-' + variant">
    <div
      class="dept-node-row"
      :class="{ 'dept-node-active': activeDeptId === node.id }"
      :style="{ paddingLeft: (level * 12 + 8) + 'px' }"
      @click.stop="$emit('select', node)"
    >
      <span class="dept-node-toggle">
        <button
          v-if="node.children?.length"
          type="button"
          class="dept-toggle-btn"
          @click.stop="$emit('toggle', node.id)"
        >
          <Icons
            :name="expanded ? 'chevron-down' : 'chevron-right'"
            class="icon-chevron"
          />
        </button>
        <span v-else class="dept-node-spacer"></span>
      </span>
      <Icons :name="level === 0 ? 'building' : 'users'" class="dept-node-icon" />
      <span class="dept-node-name">{{ node.name }}</span>
      <Icons
        v-if="node.has_access === false"
        name="lock"
        class="dept-node-lock"
      />
      <span
        v-if="node.user_count !== undefined"
        class="dept-node-count"
      >
        {{ node.user_count }}
      </span>
      <div v-if="me?.is_superuser && variant === 'content'" class="dept-node-actions" @click.stop>
        <button type="button" class="dept-node-btn" title="新建子部门" @click="$emit('add', node.id)">+</button>
        <button type="button" class="dept-node-btn" title="编辑" @click="$emit('edit', node)">编辑</button>
        <button type="button" class="dept-node-btn danger" title="删除" @click="$emit('delete', node)">删除</button>
      </div>
    </div>
    <template v-if="node.children?.length && expanded">
      <DepartmentTreeNode
        v-for="child in node.children"
        :key="child.id"
        :node="child"
        :me="me"
        :variant="variant"
        :level="level + 1"
        :expanded-ids="expandedIds"
        :active-dept-id="activeDeptId"
        @toggle="$emit('toggle', $event)"
        @add="$emit('add', $event)"
        @edit="$emit('edit', $event)"
        @delete="$emit('delete', $event)"
        @refresh="$emit('refresh')"
      />
    </template>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import Icons from './Icons.vue'

const props = defineProps({
  node: { type: Object, required: true },
  me: Object,
  level: { type: Number, default: 0 },
  expandedIds: { type: Array, default: () => [] },
  variant: { type: String, default: 'sidebar' },
  activeDeptId: { type: Number, default: null },
})

defineEmits(['toggle', 'add', 'edit', 'delete', 'refresh', 'select'])

const expanded = computed(() => Array.isArray(props.expandedIds) && props.expandedIds.includes(props.node.id))
</script>

<style scoped>
.dept-node-row {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 8px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
  min-height: 32px;
}
.dept-node-sidebar .dept-node-row { color: rgba(209, 213, 219); }
.dept-node-sidebar .dept-node-row:hover { background: rgba(75, 85, 99, 0.5); color: #fff; }
.dept-node-sidebar .dept-node-row.dept-node-active { background: rgba(74, 144, 226, 0.4); color: #fff; }
.dept-node-sidebar .dept-node-row.dept-node-active:hover { background: rgba(74, 144, 226, 0.5); }
.dept-node-content .dept-node-row { color: var(--text); }
.dept-node-content .dept-node-row:hover { background: #f3f4f6; color: var(--text); }
.dept-node-toggle {
  width: 16px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.dept-toggle-btn {
  padding: 2px;
  border: none;
  background: transparent;
  cursor: pointer;
  border-radius: 4px;
}
.dept-toggle-btn:hover { background: rgba(107, 114, 128, 0.2); }
.icon-chevron { width: 14px; height: 14px; opacity: 0.8; }
.dept-node-spacer { width: 14px; height: 14px; display: inline-block; }
.dept-node-icon { width: 16px; height: 16px; flex-shrink: 0; opacity: 0.9; }
.dept-node-name { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.dept-node-lock { width: 14px; height: 14px; opacity: 0.6; margin-left: 4px; }
.dept-node-count { font-size: 11px; color: rgba(156, 163, 175); margin-left: 6px; }
.dept-node-actions {
  display: flex;
  align-items: center;
  gap: 2px;
  opacity: 0;
  transition: opacity 0.2s;
}
.dept-node-row:hover .dept-node-actions { opacity: 1; }
.dept-node-btn {
  padding: 2px 6px;
  font-size: 12px;
  border: none;
  background: transparent;
  border-radius: 4px;
  cursor: pointer;
}
.dept-node-sidebar .dept-node-btn { color: rgba(156, 163, 175); }
.dept-node-sidebar .dept-node-btn:hover { background: rgba(75, 85, 99, 0.8); color: #fff; }
.dept-node-content .dept-node-btn { color: var(--text-secondary); }
.dept-node-content .dept-node-btn:hover { background: #e5e7eb; color: var(--text); }
.dept-node-btn.danger:hover { color: #f87171; }
</style>
