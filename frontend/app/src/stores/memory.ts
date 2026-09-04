import { defineStore } from "pinia"
import { api, pathSegment } from "../api/client"
import type { MemoryProposal, MemoryRecord, MemoryScope, MemoryType } from "../api/types"

export const useMemoryStore = defineStore("memory", {
  state: () => ({
    workspaceMemories: [] as MemoryRecord[],
    agentMemoriesByAgentId: {} as Record<string, MemoryRecord[]>,
    teamMemoriesByTeamId: {} as Record<string, MemoryRecord[]>,
    proposals: [] as MemoryProposal[],
  }),
  actions: {
    async fetchAgentMemories(agentId: string) {
      this.agentMemoriesByAgentId[agentId] = await api.get<MemoryRecord[]>(`/memory/agents/${pathSegment(agentId)}`)
    },
    async fetchTeamMemories(teamId: string) {
      this.teamMemoriesByTeamId[teamId] = await api.get<MemoryRecord[]>(`/memory/teams/${pathSegment(teamId)}`)
    },
    async fetchProposals() {
      this.proposals = await api.get<MemoryProposal[]>("/memory/proposals")
    },
    async createWorkspaceMemory(content: string, type: MemoryType) {
      const record = await api.post<MemoryRecord>("/memory", { scope: "workspace" as MemoryScope, content, type })
      this.workspaceMemories.push(record)
      return record
    },
    async createTeamMemory(teamId: string, content: string, type: MemoryType) {
      const record = await api.post<MemoryRecord>("/memory", { scope: "team" as MemoryScope, content, type, team_id: teamId })
      const list = this.teamMemoriesByTeamId[teamId] ?? (this.teamMemoriesByTeamId[teamId] = [])
      list.push(record)
      return record
    },
    async pin(id: string) {
      this.applyRecordUpdate(await api.post<MemoryRecord>(`/memory/${pathSegment(id)}/pin`))
    },
    async unpin(id: string) {
      this.applyRecordUpdate(await api.post<MemoryRecord>(`/memory/${pathSegment(id)}/unpin`))
    },
    async archive(id: string) {
      this.removeRecord(await api.post<MemoryRecord>(`/memory/${pathSegment(id)}/archive`))
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
    applyRecordUpdate(record: MemoryRecord) {
      const list = this.collectionFor(record)
      const index = list?.findIndex((existing) => existing.id === record.id)
      if (list && index !== undefined && index !== -1) list[index] = record
    },
    removeRecord(record: MemoryRecord) {
      const list = this.collectionFor(record)
      const index = list?.findIndex((existing) => existing.id === record.id)
      if (list && index !== undefined && index !== -1) list.splice(index, 1)
    },
    collectionFor(record: MemoryRecord): MemoryRecord[] | undefined {
      // allow-comment: the three scopes that reach here (workspace/agent/team) each own exactly one collection; a fourth scope (task) has none yet and returns undefined on purpose.
      if (record.scope === "workspace") return this.workspaceMemories
      if (record.scope === "agent" && record.agent_id) return this.agentMemoriesByAgentId[record.agent_id]
      if (record.scope === "team" && record.team_id) return this.teamMemoriesByTeamId[record.team_id]
      return undefined
    },
    receiveMemoryCreated(record: MemoryRecord) {
      if (record.scope !== "workspace") return
      if (this.workspaceMemories.some((existing) => existing.id === record.id)) return
      this.workspaceMemories.push(record)
    },
  },
})
