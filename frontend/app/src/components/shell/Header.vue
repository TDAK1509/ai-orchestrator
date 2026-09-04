<script setup lang="ts">
import { ref } from "vue"
import { useAttentionStore } from "../../stores/attention"
import NotificationInbox from "./NotificationInbox.vue"
import type { AttentionEvent } from "../../api/types"

const emit = defineEmits<{ createTask: []; hireAgent: []; openAttention: [event: AttentionEvent] }>()

const attention = useAttentionStore()
const inboxOpen = ref(false)

function openEvent(event: AttentionEvent): void {
  inboxOpen.value = false
  emit("openAttention", event)
}
</script>

<template>
  <header class="relative flex items-center justify-between border-b border-gray-200 bg-white px-4 py-2">
    <h1 class="text-sm font-semibold tracking-wide">AGENT OFFICE</h1>
    <div class="flex items-center gap-3">
      <button class="text-sm" @click="inboxOpen = !inboxOpen">🔔 {{ attention.unresolvedCount }}</button>
      <button class="text-sm" @click="attention.toggleSound()">{{ attention.soundEnabled ? "🔊 On" : "🔇 Off" }}</button>
      <button class="rounded bg-gray-100 px-2 py-1 text-sm" @click="emit('createTask')">+ Task</button>
      <button class="rounded bg-gray-100 px-2 py-1 text-sm" @click="emit('hireAgent')">+ Hire Agent</button>
    </div>
    <NotificationInbox v-if="inboxOpen" @close="inboxOpen = false" @open="openEvent" />
  </header>
</template>
