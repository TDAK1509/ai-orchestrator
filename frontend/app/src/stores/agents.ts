import { defineStore } from "pinia"
import { api } from "../api/client"
import type { Agent } from "../api/types"

export const useAgentsStore = defineStore("agents", {
  state: () => ({
    agents: [] as Agent[],
  }),
  getters: {
    byId: (state) => (id: string) => state.agents.find((agent) => agent.id === id),
    activeAgents: (state) => state.agents.filter((agent) => agent.active),
  },
  actions: {
    async fetchAgents() {
      this.agents = await api.get<Agent[]>("/agents")
    },
    async hireAgent(name: string, role: string, instructions: string) {
      const agent = await api.post<Agent>("/agents", { name, role, instructions })
      this.upsert(agent)
      return agent
    },
    async editAgent(id: string, patch: Partial<Pick<Agent, "name" | "role" | "instructions">>) {
      const agent = await api.patch<Agent>(`/agents/${id}`, patch)
      this.upsert(agent)
      return agent
    },
    async fireAgent(id: string) {
      const agent = await api.delete<Agent>(`/agents/${id}`)
      this.upsert(agent)
      return agent
    },
    upsert(agent: Agent) {
      const index = this.agents.findIndex((existing) => existing.id === agent.id)
      if (index === -1) this.agents.push(agent)
      else this.agents[index] = agent
    },
  },
})
