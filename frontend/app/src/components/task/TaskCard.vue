<script setup lang="ts">
import type { Task } from "../../api/types"
import { useAgentsStore } from "../../stores/agents"
import { useTasksStore } from "../../stores/tasks"

const props = defineProps<{ task: Task }>()

const agents = useAgentsStore()
const tasks = useTasksStore()

function assigneeLabel(): string {
  if (!props.task.assignee_id) return "Unassigned"
  const agent = agents.byId(props.task.assignee_id)
  return agent ? `${agent.name} · ${agent.role}` : "Unassigned"
}

function idleAgents() {
  return agents.agents.filter((agent) => agent.status === "idle")
}

function assignTo(agentId: string): void {
  if (agentId) tasks.assignTask(props.task.id, agentId)
}
</script>

<template>
  <div class="rounded-lg border border-gray-200 bg-white p-3 shadow-sm">
    <p class="font-medium">{{ task.title }}</p>
    <p class="mt-1 text-sm text-gray-500">{{ assigneeLabel() }}</p>
    <p class="mt-1 text-xs uppercase tracking-wide text-gray-400">{{ task.priority }}</p>
    <select
      v-if="task.status === 'backlog'"
      class="mt-2 w-full rounded border border-gray-300 text-xs"
      @change="assignTo(($event.target as HTMLSelectElement).value)"
    >
      <option value="">Assign agent...</option>
      <option v-for="agent in idleAgents()" :key="agent.id" :value="agent.id">{{ agent.name }}</option>
    </select>
  </div>
</template>
