<script setup lang="ts">
defineProps<{ items: { key: string; label: string; suffix?: string }[]; ticked: Set<string> }>()
defineEmits<{ toggle: [key: string] }>()
</script>

<template>
  <div class="max-h-72 space-y-1 overflow-y-auto">
    <label v-for="item in items" :key="item.key" class="flex items-center gap-2 text-sm">
      <input type="checkbox" :checked="ticked.has(item.key)" @change="$emit('toggle', item.key)" />
      <span>{{ item.label }}</span>
      <span v-if="item.suffix" class="text-xs text-amber-600">{{ item.suffix }}</span>
    </label>
  </div>
</template>
