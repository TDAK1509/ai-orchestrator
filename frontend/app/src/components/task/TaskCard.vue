<script setup lang="ts">
import { ref } from "vue"
import type { Task } from "../../api/types"
import { useAgentsStore } from "../../stores/agents"
import { useAttentionStore } from "../../stores/attention"
import { useTasksStore } from "../../stores/tasks"
import EditTaskDialog from "./EditTaskDialog.vue"

const props = defineProps<{ task: Task; selected?: boolean }>()
defineEmits<{ toggle: [] }>()

const agents = useAgentsStore()
const tasks = useTasksStore()
const attention = useAttentionStore()
const editing = ref(false)
const confirmingArchive = ref(false)
const retrying = ref(false)

function assigneeLabel(): string {
  if (!props.task.assignee_id) return "Unassigned"
  const agent = agents.byId(props.task.assignee_id)
  return agent ? `${agent.name} · ${agent.role}` : "Unassigned"
}

function createdByLabel(): string | null {
  if (!props.task.created_by_agent_id) return null
  const agent = agents.byId(props.task.created_by_agent_id)
  return agent ? `Filed by ${agent.name}` : "Filed by an agent"
}

function idleAgents() {
  return agents.activeAgents.filter((agent) => agent.status === "idle")
}

function assignTo(agentId: string): void {
  if (agentId) tasks.assignTask(props.task.id, agentId)
}

async function archive(): Promise<void> {
  await tasks.archiveTask(props.task.id)
  confirmingArchive.value = false
}

async function retry(): Promise<void> {
  retrying.value = true
  try {
    await tasks.retryTask(props.task.id)
  } finally {
    retrying.value = false
  }
}
</script>

<template>
  <div class="rounded-lg border border-gray-200 bg-white p-3 shadow-sm">
    <div class="flex items-start justify-between gap-2">
      <div class="flex items-start gap-2">
        <input type="checkbox" class="mt-1" :checked="selected" @change="$emit('toggle')" />
        <p class="font-medium">{{ task.title }}</p>
      </div>
      <div class="flex shrink-0 gap-2 text-xs">
        <button class="text-blue-600" @click="editing = true">Edit</button>
        <button class="text-red-600" @click="confirmingArchive = true">Archive</button>
      </div>
    </div>
    <p class="mt-1 text-sm text-gray-500">{{ assigneeLabel() }}</p>
    <p v-if="createdByLabel()" class="mt-1 text-xs text-gray-400">{{ createdByLabel() }}</p>
    <p class="mt-1 text-xs uppercase tracking-wide text-gray-400">{{ task.priority }}</p>
    <select
      v-if="task.status === 'backlog'"
      class="mt-2 w-full rounded border border-gray-300 text-xs"
      @change="assignTo(($event.target as HTMLSelectElement).value)"
    >
      <option value="">Assign agent...</option>
      <option v-for="agent in idleAgents()" :key="agent.id" :value="agent.id">{{ agent.name }}</option>
    </select>

    <div v-if="task.status === 'blocked'" class="mt-2 rounded border border-amber-200 bg-amber-50 p-2 text-xs text-amber-800">
      <p v-if="attention.attentionForTask(task.id)">{{ attention.attentionForTask(task.id)?.message }}</p>
      <button class="mt-1 font-medium text-amber-900 disabled:opacity-50" :disabled="retrying" @click="retry">Retry</button>
    </div>

    <div v-if="confirmingArchive" class="mt-2 rounded border border-red-200 bg-red-50 p-2 text-xs">
      <p>Archive this task? It leaves the board, and any uncommitted work in its worktree is discarded.</p>
      <div class="mt-2 flex gap-2">
        <button class="rounded bg-red-600 px-2 py-1 text-white" @click="archive">Archive</button>
        <button class="rounded border border-gray-300 px-2 py-1" @click="confirmingArchive = false">Cancel</button>
      </div>
    </div>

    <EditTaskDialog v-if="editing" :task="task" @close="editing = false" />
  </div>
</template>
