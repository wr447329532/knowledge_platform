<template>
  <div class="app-content">
    <div class="card" style="max-width: 800px;">
      <h3>回收站</h3>
      <p>
        <select :value="trashLibId" @change="emit('lib-change', $event.target.value)" style="min-width: 200px;">
          <option value="">选择资料库</option>
          <option v-for="lib in libraries" :key="lib.id" :value="lib.id">{{ lib.name }}</option>
        </select>
      </p>
      <p v-if="trashLoading" class="empty-hint">加载中...</p>
      <table v-else-if="trashList.length">
        <thead>
          <tr><th>路径</th><th>删除时间</th><th>操作</th></tr>
        </thead>
        <tbody>
          <tr v-for="f in trashList" :key="f.id">
            <td>{{ f.path }}</td>
            <td>{{ formatDate(f.deleted_at) }}</td>
            <td>
              <button @click="emit('restore', f.id)">恢复</button>
              <button class="danger" @click="emit('perm-delete', f.id)">彻底删除</button>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-else-if="trashLibId">该库回收站为空</p>
      <p v-else class="empty-hint">请选择资料库查看回收站。</p>
    </div>
  </div>
</template>

<script setup>
defineProps({
  libraries: Array,
  trashLibId: [String, Number],
  trashList: Array,
  trashLoading: Boolean,
  formatDate: Function,
})

const emit = defineEmits(['lib-change', 'restore', 'perm-delete'])
</script>

<style scoped>
.app-content { flex: 1; min-height: 0; padding: 24px; overflow: auto; }
.app-content .card { background: #fff; }
.empty-hint { color: var(--text-secondary); font-size: 14px; margin: 12px 0; }
</style>
