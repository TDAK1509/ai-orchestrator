import { defineStore } from "pinia"
import { api } from "../api/client"
import type { AttentionEvent, DecisionRequest } from "../api/types"
import { playPing } from "../soundPing"

const SOUND_STORAGE_KEY = "agent-office.sound-enabled"

export const useAttentionStore = defineStore("attention", {
  state: () => ({
    pendingDecisions: [] as DecisionRequest[],
    attentionEvents: [] as AttentionEvent[],
    soundEnabled: loadSoundPreference(),
  }),
  getters: {
    unresolvedCount: (state) => state.attentionEvents.filter((event) => !event.resolved).length,
    decisionForAgent: (state) => (agentId: string) => state.pendingDecisions.find((d) => d.agent_id === agentId),
  },
  actions: {
    async fetchPendingDecisions() {
      this.pendingDecisions = await api.get<DecisionRequest[]>("/decisions")
    },
    async fetchAttentionEvents() {
      this.attentionEvents = await api.get<AttentionEvent[]>("/attention")
    },
    async answerDecision(decisionId: string, answer: string) {
      const decision = await api.post<DecisionRequest>(`/decisions/${decisionId}/answer`, { answer })
      this.pendingDecisions = this.pendingDecisions.filter((d) => d.id !== decisionId)
      return decision
    },
    toggleSound() {
      this.soundEnabled = !this.soundEnabled
      localStorage.setItem(SOUND_STORAGE_KEY, String(this.soundEnabled))
    },
    receiveDecisionCreated(decision: DecisionRequest) {
      this.pendingDecisions.push(decision)
    },
    receiveDecisionAnswered(decision: DecisionRequest) {
      this.pendingDecisions = this.pendingDecisions.filter((d) => d.id !== decision.id)
    },
    receiveAttentionCreated(event: AttentionEvent) {
      this.upsertAttentionEvent(event)
      if (this.soundEnabled) playPing()
    },
    receiveAttentionResolved(event: AttentionEvent) {
      this.upsertAttentionEvent(event)
    },
    upsertAttentionEvent(event: AttentionEvent) {
      const index = this.attentionEvents.findIndex((existing) => existing.id === event.id)
      if (index === -1) this.attentionEvents.push(event)
      else this.attentionEvents[index] = event
    },
  },
})

function loadSoundPreference(): boolean {
  try {
    return localStorage.getItem(SOUND_STORAGE_KEY) !== "false"
  } catch {
    return true
  }
}
