<script setup lang="ts">
import type { AttentionEvent } from "../../api/types"
import { useAttentionStore } from "../../stores/attention"

const emit = defineEmits<{ close: []; open: [event: AttentionEvent] }>()

const attention = useAttentionStore()

function unresolved(): AttentionEvent[] {
  return attention.attentionEvents.filter((event) => !event.resolved)
}
</script>

<template>
  <div class="absolute right-4 top-12 z-30 w-80 rounded-lg border border-gray-200 bg-white p-3 shadow-xl">
    <h3 class="text-xs font-semibold uppercase tracking-wide text-gray-400">Needs your attention</h3>
    <div v-if="unresolved().length === 0" class="mt-2 text-sm text-gray-400">Nothing pending.</div>
    <div v-for="event in unresolved()" :key="event.id" class="mt-2 border-t border-gray-100 pt-2">
      <p class="text-sm font-medium">{{ event.title }}</p>
      <p class="text-sm text-gray-500">{{ event.message }}</p>
      <button class="mt-1 text-sm text-blue-600" @click="emit('open', event)">Open</button>
    </div>
    <div class="mt-3 border-t border-gray-100 pt-2 text-xs text-gray-400">{{ unresolved().length }} unresolved</div>
  </div>
</template>
