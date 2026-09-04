import { defineStore } from "pinia"
import { api } from "../api/client"
import type { MemoryRecord, MemoryScope, MemoryType } from "../api/types"

export const useMemoryStore = defineStore("memory", {
  state: () => ({
    workspaceMemories: [] as MemoryRecord[],
  }),
  actions: {
    async fetchWorkspaceMemories() {
      this.workspaceMemories = await api.get<MemoryRecord[]>("/memory/workspace")
    },
    async createWorkspaceMemory(content: string, type: MemoryType) {
      const record = await api.post<MemoryRecord>("/memory", { scope: "workspace" as MemoryScope, content, type })
      this.workspaceMemories.push(record)
      return record
    },
    async pin(id: string) {
      await this.updateAndRefetch(id, () => api.post(`/memory/${id}/pin`))
    },
    async unpin(id: string) {
      await this.updateAndRefetch(id, () => api.post(`/memory/${id}/unpin`))
    },
    async archive(id: string) {
      await api.post(`/memory/${id}/archive`)
      this.workspaceMemories = this.workspaceMemories.filter((record) => record.id !== id)
    },
    async updateAndRefetch(id: string, action: () => Promise<unknown>) {
      const record = (await action()) as MemoryRecord
      const index = this.workspaceMemories.findIndex((existing) => existing.id === id)
      if (index !== -1) this.workspaceMemories[index] = record
    },
  },
})
