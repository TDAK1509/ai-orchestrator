import { defineStore } from "pinia"
import { api, pathSegment } from "../api/client"
import type { MemoryProposal, MemoryRecord, MemoryScope, MemoryType } from "../api/types"

export const useMemoryStore = defineStore("memory", {
  state: () => ({
    workspaceMemories: [] as MemoryRecord[],
    agentMemoriesByAgentId: {} as Record<string, MemoryRecord[]>,
    proposals: [] as MemoryProposal[],
  }),
  actions: {
    async fetchAgentMemories(agentId: string) {
      this.agentMemoriesByAgentId[agentId] = await api.get<MemoryRecord[]>(`/memory/agents/${pathSegment(agentId)}`)
    },
    async fetchProposals() {
      this.proposals = await api.get<MemoryProposal[]>("/memory/proposals")
    },
    async createWorkspaceMemory(content: string, type: MemoryType) {
      const record = await api.post<MemoryRecord>("/memory", { scope: "workspace" as MemoryScope, content, type })
      this.workspaceMemories.push(record)
      return record
    },
    async pin(id: string) {
      await this.updateAndRefetch(id, () => api.post(`/memory/${pathSegment(id)}/pin`))
    },
    async unpin(id: string) {
      await this.updateAndRefetch(id, () => api.post(`/memory/${pathSegment(id)}/unpin`))
    },
    async archive(id: string) {
      await api.post(`/memory/${pathSegment(id)}/archive`)
      this.workspaceMemories = this.workspaceMemories.filter((record) => record.id !== id)
    },
    async promote(id: string, agentId: string) {
      await api.post(`/memory/${pathSegment(id)}/promote`)
      this.agentMemoriesByAgentId[agentId] = (this.agentMemoriesByAgentId[agentId] ?? []).filter((record) => record.id !== id)
      await this.fetchWorkspaceMemories()
    },
    async fetchWorkspaceMemories() {
      this.workspaceMemories = await api.get<MemoryRecord[]>("/memory/workspace")
    },
    async applyProposal(id: string) {
      await api.post(`/memory/proposals/${pathSegment(id)}/apply`)
      this.proposals = this.proposals.filter((proposal) => proposal.id !== id)
    },
    async dismissProposal(id: string) {
      await api.post(`/memory/proposals/${pathSegment(id)}/dismiss`)
      this.proposals = this.proposals.filter((proposal) => proposal.id !== id)
    },
    async updateAndRefetch(id: string, action: () => Promise<unknown>) {
      const record = (await action()) as MemoryRecord
      const index = this.workspaceMemories.findIndex((existing) => existing.id === id)
      if (index !== -1) this.workspaceMemories[index] = record
    },
    receiveMemoryCreated(record: MemoryRecord) {
      if (record.scope !== "workspace") return
      if (this.workspaceMemories.some((existing) => existing.id === record.id)) return
      this.workspaceMemories.push(record)
    },
  },
})
