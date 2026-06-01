<template>
  <span class="library-type-tags">
    <span
      class="shared-library-type"
      :class="libraryCategoryClass(lib)"
      :title="categoryTitle"
    >{{ libraryCategoryText(lib) }}</span>
    <span
      class="shared-library-type"
      :class="libraryAccessModeClass(lib)"
      :title="accessTitle"
    >{{ libraryAccessModeText(lib) }}</span>
  </span>
</template>

<script setup>
import { computed } from 'vue'
import {
  libraryAccessModeClass,
  libraryAccessModeText,
  libraryCategoryClass,
  libraryCategoryText,
} from '../utils/libraryDisplay.js'

const props = defineProps({
  lib: { type: Object, required: true },
})

const categoryTitle = computed(() => (
  props.lib?.department_name
    ? `归属：${props.lib.department_name}`
    : '个人创建的文件库'
))

const accessTitle = computed(() => {
  const names = props.lib?.access_department_names
  if (Array.isArray(names) && names.length) {
    return `指定部门：${names.join('、')}`
  }
  return '文件库访问权限'
})
</script>
