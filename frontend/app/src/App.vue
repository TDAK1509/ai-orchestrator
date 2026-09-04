<script setup lang="ts">
import { onMounted, ref } from "vue"
import type { Agent, AttentionEvent } from "./api/types"
import AgentSheet from "./components/agent/AgentSheet.vue"
import HireAgentDialog from "./components/agent/HireAgentDialog.vue"
import Header from "./components/shell/Header.vue"
import AgentSidebar from "./components/shell/AgentSidebar.vue"
import CreateTaskDialog from "./components/task/CreateTaskDialog.vue"
import KanbanBoard from "./components/task/KanbanBoard.vue"
import { startRealtimeDispatch } from "./realtime/dispatch"
import { useAgentsStore } from "./stores/agents"
import { useAttentionStore } from "./stores/attention"
import { useTasksStore } from "./stores/tasks"

const agents = useAgentsStore()
const tasks = useTasksStore()
const attention = useAttentionStore()

const selectedAgent = ref<Agent | null>(null)
const showCreateTask = ref(false)
const showHireAgent = ref(false)

onMounted(async () => {
  await Promise.all([agents.fetchAgents(), tasks.fetchTasks(), attention.fetchPendingDecisions(), attention.fetchAttentionEvents()])
  startRealtimeDispatch()
})

function openAttentionEvent(event: AttentionEvent): void {
  const agent = event.agent_id ? agents.byId(event.agent_id) : undefined
  if (agent) selectedAgent.value = agent
}
</script>

<template>
  <div class="flex h-screen flex-col">
    <Header @create-task="showCreateTask = true" @hire-agent="showHireAgent = true" @open-attention="openAttentionEvent" />
    <div class="flex flex-1 overflow-hidden">
      <AgentSidebar @select="selectedAgent = $event" />
      <main class="flex-1 overflow-y-auto">
        <KanbanBoard />
      </main>
    </div>

    <AgentSheet v-if="selectedAgent" :agent="agents.byId(selectedAgent.id) ?? selectedAgent" @close="selectedAgent = null" />
    <CreateTaskDialog v-if="showCreateTask" @close="showCreateTask = false" />
    <HireAgentDialog v-if="showHireAgent" @close="showHireAgent = false" />
  </div>
</template>
