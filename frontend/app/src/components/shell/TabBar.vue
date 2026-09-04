<script setup lang="ts">
defineProps<{ active: string; tabs: { key: string; label: string }[] }>()
defineEmits<{ select: [key: string] }>()
</script>

<template>
  <nav class="flex gap-1 border-b border-gray-200 bg-white px-4 py-2">
    <button
      v-for="tab in tabs"
      :key="tab.key"
      class="rounded px-3 py-1 text-sm"
      :class="active === tab.key ? 'bg-gray-900 text-white' : 'text-gray-600 hover:bg-gray-100'"
      @click="$emit('select', tab.key)"
    >
      {{ tab.label }}
    </button>
  </nav>
</template>
