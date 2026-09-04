import { defineStore } from "pinia"
import type { RuntimeEventPayload } from "../api/types"

const MAX_EVENTS_PER_AGENT = 20

export const useActivityStore = defineStore("activity", {
  state: () => ({
    byAgentId: {} as Record<string, RuntimeEventPayload[]>,
  }),
  getters: {
    forAgent: (state) => (agentId: string) => state.byAgentId[agentId] ?? [],
  },
  actions: {
    receiveRuntimeEvent(payload: RuntimeEventPayload) {
      const existing = this.byAgentId[payload.agentId] ?? []
      this.byAgentId[payload.agentId] = [...existing, payload].slice(-MAX_EVENTS_PER_AGENT)
    },
  },
})
