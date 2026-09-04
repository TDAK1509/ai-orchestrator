<script setup lang="ts">
import { onMounted, ref } from "vue"
import type { Agent, AttentionEvent } from "./api/types"
import AgentSheet from "./components/agent/AgentSheet.vue"
import HireAgentDialog from "./components/agent/HireAgentDialog.vue"
import Header from "./components/shell/Header.vue"
import AgentSidebar from "./components/shell/AgentSidebar.vue"
import TabBar from "./components/shell/TabBar.vue"
import CreateTaskDialog from "./components/task/CreateTaskDialog.vue"
import KanbanBoard from "./components/task/KanbanBoard.vue"
import RoomsView from "./views/RoomsView.vue"
import SkillsView from "./views/SkillsView.vue"
import McpView from "./views/McpView.vue"
import MemoryView from "./views/MemoryView.vue"
import { startRealtimeDispatch } from "./realtime/dispatch"
import { useAgentsStore } from "./stores/agents"
import { useAttentionStore } from "./stores/attention"
import { useMcpStore } from "./stores/mcp"
import { useMeetingsStore } from "./stores/meetings"
import { useMemoryStore } from "./stores/memory"
import { useRoomsStore } from "./stores/rooms"
import { useSkillsStore } from "./stores/skills"
import { useTasksStore } from "./stores/tasks"

const agents = useAgentsStore()
const tasks = useTasksStore()
const attention = useAttentionStore()
const skills = useSkillsStore()
const mcp = useMcpStore()
const memory = useMemoryStore()
const rooms = useRoomsStore()
const meetings = useMeetingsStore()

const selectedAgent = ref<Agent | null>(null)
const showCreateTask = ref(false)
const showHireAgent = ref(false)
const activeTab = ref("tasks")
const TABS = [
  { key: "rooms", label: "Rooms" },
  { key: "tasks", label: "Tasks" },
  { key: "skills", label: "Skills" },
  { key: "mcp", label: "MCP" },
  { key: "memory", label: "Workspace Memory" },
]

onMounted(() => {
  startRealtimeDispatch(loadSnapshots)
})

async function loadSnapshots(): Promise<void> {
  await Promise.all([
    agents.fetchAgents(),
    tasks.fetchTasks(),
    attention.fetchPendingDecisions(),
    attention.fetchAttentionEvents(),
    skills.fetchSkills(),
    mcp.fetchPool(),
    memory.fetchWorkspaceMemories(),
    rooms.fetchRooms(),
    meetings.fetchMeetings(),
  ])
}

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
      <main class="flex flex-1 flex-col overflow-hidden">
        <TabBar :active="activeTab" :tabs="TABS" @select="activeTab = $event" />
        <div class="flex-1 overflow-y-auto">
          <RoomsView v-if="activeTab === 'rooms'" />
          <KanbanBoard v-else-if="activeTab === 'tasks'" />
          <SkillsView v-else-if="activeTab === 'skills'" />
          <McpView v-else-if="activeTab === 'mcp'" />
          <MemoryView v-else-if="activeTab === 'memory'" />
        </div>
      </main>
    </div>

    <AgentSheet v-if="selectedAgent" :agent="agents.byId(selectedAgent.id) ?? selectedAgent" @close="selectedAgent = null" />
    <CreateTaskDialog v-if="showCreateTask" @close="showCreateTask = false" />
    <HireAgentDialog v-if="showHireAgent" @close="showHireAgent = false" />
  </div>
</template>
