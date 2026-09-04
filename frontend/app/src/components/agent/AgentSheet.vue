<script setup lang="ts">
import { computed, ref } from "vue"
import type { Agent } from "../../api/types"
import { useAgentsStore } from "../../stores/agents"
import { useAttentionStore } from "../../stores/attention"
import { useTasksStore } from "../../stores/tasks"
import DecisionPanel from "./DecisionPanel.vue"

const props = defineProps<{ agent: Agent }>()
defineEmits<{ close: [] }>()

const tasks = useTasksStore()
const agentsStore = useAgentsStore()
const attention = useAttentionStore()
const confirmingFire = ref(false)

const currentTask = computed(() => (props.agent.current_task_id ? tasks.byId(props.agent.current_task_id) : undefined))
const decision = computed(() => attention.decisionForAgent(props.agent.id))

async function confirmFire(): Promise<void> {
  await agentsStore.fireAgent(props.agent.id)
  confirmingFire.value = false
}
</script>

<template>
  <div class="fixed inset-y-0 right-0 z-20 w-96 overflow-y-auto border-l border-gray-200 bg-white p-4 shadow-xl">
    <div class="flex items-start justify-between">
      <div>
        <h2 class="text-lg font-semibold">{{ agent.name }}</h2>
        <p class="text-sm text-gray-500">{{ agent.role }}</p>
      </div>
      <button class="text-gray-400 hover:text-gray-600" @click="$emit('close')">✕</button>
    </div>

    <p class="mt-2 text-sm font-medium uppercase tracking-wide text-gray-500">{{ agent.status }}</p>

    <DecisionPanel v-if="decision" :decision="decision" class="mt-4" />

    <div v-if="currentTask" class="mt-4 border-t border-gray-100 pt-4">
      <h3 class="text-xs font-semibold uppercase tracking-wide text-gray-400">Current Task</h3>
      <p class="mt-1 font-medium">{{ currentTask.title }}</p>
      <p class="mt-1 text-sm text-gray-600">{{ currentTask.description }}</p>
    </div>

    <div class="mt-6 border-t border-gray-100 pt-4">
      <h3 class="text-xs font-semibold uppercase tracking-wide text-gray-400">Agent Settings</h3>
      <button v-if="!confirmingFire" class="mt-2 text-sm text-red-600" @click="confirmingFire = true">Fire Agent</button>
      <div v-else class="mt-2 rounded border border-red-200 bg-red-50 p-2 text-sm">
        <p>Fire {{ agent.name }}? Unfinished work returns to Backlog.</p>
        <div class="mt-2 flex gap-2">
          <button class="rounded bg-red-600 px-2 py-1 text-white" @click="confirmFire">Fire Agent</button>
          <button class="rounded border border-gray-300 px-2 py-1" @click="confirmingFire = false">Cancel</button>
        </div>
      </div>
    </div>
  </div>
</template>
