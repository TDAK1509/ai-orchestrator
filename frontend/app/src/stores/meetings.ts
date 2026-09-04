import { defineStore } from "pinia"
import { api } from "../api/client"
import type { Meeting, MeetingMessage } from "../api/types"

export const useMeetingsStore = defineStore("meetings", {
  state: () => ({
    meetings: [] as Meeting[],
    messagesByMeetingId: {} as Record<string, MeetingMessage[]>,
  }),
  getters: {
    active: (state) => state.meetings.filter((meeting) => meeting.status === "active"),
    byRoomId: (state) => (roomId: string) => state.meetings.find((meeting) => meeting.room_id === roomId),
  },
  actions: {
    async fetchMeetings() {
      this.meetings = await api.get<Meeting[]>("/meetings")
    },
    async createMeeting(topic: string, goal: string | undefined, participantAgentIds: string[]) {
      const meeting = await api.post<Meeting>("/meetings", { topic, goal, participant_agent_ids: participantAgentIds })
      this.meetings.push(meeting)
      return meeting
    },
    async addMessage(meetingId: string, agentId: string, content: string) {
      await api.post(`/meetings/${meetingId}/messages`, { agent_id: agentId, content })
      await this.fetchMessages(meetingId)
    },
    async fetchMessages(meetingId: string) {
      this.messagesByMeetingId[meetingId] = await api.get<MeetingMessage[]>(`/meetings/${meetingId}/messages`)
    },
    async endMeeting(meetingId: string, summary: string) {
      const meeting = await api.post<Meeting>(`/meetings/${meetingId}/end`, { summary })
      this.upsertMeeting(meeting)
      return meeting
    },
    upsertMeeting(meeting: Meeting) {
      const index = this.meetings.findIndex((existing) => existing.id === meeting.id)
      if (index === -1) this.meetings.push(meeting)
      else this.meetings[index] = meeting
    },
  },
})
