<script setup lang="ts">
defineProps<{ label: string; items: string[] }>()
</script>

<template>
  <div v-if="items.length" class="mt-1">
    <span class="font-medium">{{ label }}:</span> {{ items.join("; ") }}
  </div>
</template>
