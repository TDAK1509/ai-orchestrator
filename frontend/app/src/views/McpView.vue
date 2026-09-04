<script setup lang="ts">
import { onMounted, ref } from "vue"
import { useAgentsStore } from "../stores/agents"
import { useMcpStore } from "../stores/mcp"

const mcp = useMcpStore()
const agents = useAgentsStore()
const selectedAgentId = ref<string>("")

onMounted(async () => {
  await mcp.fetchPool()
  await Promise.all(agents.activeAgents.map((agent) => mcp.fetchAgentPermissions(agent.id)))
})

function isGranted(serverName: string): boolean {
  const permissions = mcp.permissionsByAgentId[selectedAgentId.value] ?? []
  return permissions.some((p) => p.mcp_server_name === serverName && p.allowed)
}

function toggle(serverName: string): void {
  if (!selectedAgentId.value) return
  if (isGranted(serverName)) mcp.revoke(selectedAgentId.value, serverName)
  else mcp.grant(selectedAgentId.value, serverName)
}
</script>

<template>
  <div class="p-4">
    <div class="flex items-center justify-between">
      <h2 class="text-xs font-semibold uppercase tracking-wide text-gray-400">MCP Servers · Managed in the terminal</h2>
      <button class="text-sm text-blue-600" @click="mcp.fetchPool()">Refresh</button>
    </div>
    <select v-model="selectedAgentId" class="mt-3 rounded border border-gray-300 px-2 py-1 text-sm">
      <option value="">Select an agent to manage access...</option>
      <option v-for="agent in agents.activeAgents" :key="agent.id" :value="agent.id">{{ agent.name }}</option>
    </select>
    <div class="mt-3 flex flex-col gap-2">
      <div v-for="server in mcp.pool" :key="server.name" class="flex items-center justify-between rounded-lg border border-gray-200 bg-white p-3">
        <div>
          <p class="font-medium">{{ server.name }}</p>
          <p class="text-sm text-gray-500">{{ server.transport }} · {{ mcp.grantedAgentCount(server.name) }} agents</p>
        </div>
        <label v-if="selectedAgentId" class="flex items-center gap-2 text-sm">
          <input type="checkbox" :checked="isGranted(server.name)" @change="toggle(server.name)" />
          Allowed
        </label>
      </div>
    </div>
  </div>
</template>
