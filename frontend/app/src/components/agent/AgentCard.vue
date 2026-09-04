<script setup lang="ts">
import type { Agent } from "../../api/types"
import { useTasksStore } from "../../stores/tasks"

const props = defineProps<{ agent: Agent }>()
defineEmits<{ select: [agent: Agent] }>()

const tasks = useTasksStore()

const statusDot: Record<Agent["status"], string> = {
  idle: "○",
  queued: "○",
  working: "●",
  blocked: "!",
}

const statusColor: Record<Agent["status"], string> = {
  idle: "text-gray-400",
  queued: "text-amber-500",
  working: "text-green-600",
  blocked: "text-red-600",
}

function currentTaskTitle(): string | null {
  if (!props.agent.current_task_id) return null
  return tasks.byId(props.agent.current_task_id)?.title ?? null
}
</script>

<template>
  <button
    class="w-full text-left rounded-lg border border-gray-200 bg-white p-3 shadow-sm hover:border-gray-300"
    :class="{ 'border-red-300 bg-red-50': agent.needs_attention }"
    @click="$emit('select', agent)"
  >
    <div class="flex items-center gap-2 font-medium">
      <span :class="statusColor[agent.status]">{{ statusDot[agent.status] }}</span>
      <span>{{ agent.name }}</span>
    </div>
    <div class="text-sm text-gray-500">{{ agent.role }}</div>
    <div class="mt-1 text-xs uppercase tracking-wide text-gray-400">{{ agent.status }}</div>
    <div v-if="currentTaskTitle()" class="mt-1 text-sm text-gray-700">{{ currentTaskTitle() }}</div>
  </button>
</template>
