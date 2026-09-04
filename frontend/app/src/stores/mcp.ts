import { defineStore } from "pinia"
import { api } from "../api/client"
import type { AgentMcpPermission, McpServerRef } from "../api/types"

export const useMcpStore = defineStore("mcp", {
  state: () => ({
    pool: [] as McpServerRef[],
    permissionsByAgentId: {} as Record<string, AgentMcpPermission[]>,
  }),
  getters: {
    grantedAgentCount: (state) => (serverName: string) =>
      Object.values(state.permissionsByAgentId).filter((permissions) => permissions.some((p) => p.mcp_server_name === serverName && p.allowed)).length,
  },
  actions: {
    async fetchPool() {
      this.pool = await api.get<McpServerRef[]>("/mcp/pool")
    },
    async grant(agentId: string, serverName: string) {
      await api.post(`/mcp/agents/${agentId}/grant`, { server_name: serverName })
      await this.fetchAgentPermissions(agentId)
    },
    async revoke(agentId: string, serverName: string) {
      await api.delete(`/mcp/agents/${agentId}/revoke/${serverName}`)
      await this.fetchAgentPermissions(agentId)
    },
    async fetchAgentPermissions(agentId: string) {
      this.permissionsByAgentId[agentId] = await api.get<AgentMcpPermission[]>(`/mcp/agents/${agentId}`)
    },
  },
})
