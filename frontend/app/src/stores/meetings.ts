import { defineStore } from "pinia"
import { api, pathSegment } from "../api/client"
import type { Meeting, MeetingMessage } from "../api/types"
import { useRoomsStore } from "./rooms"

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
      await useRoomsStore().fetchRooms()
      return meeting
    },
    async addMessage(meetingId: string, agentId: string, content: string) {
      const message = await api.post<MeetingMessage>(`/meetings/${pathSegment(meetingId)}/messages`, { agent_id: agentId, content })
      this.receiveMessage(message)
    },
    async fetchMessages(meetingId: string) {
      this.messagesByMeetingId[meetingId] = await api.get<MeetingMessage[]>(`/meetings/${pathSegment(meetingId)}/messages`)
    },
    receiveMessage(message: MeetingMessage) {
      const existing = this.messagesByMeetingId[message.meeting_id] ?? []
      if (existing.some((m) => m.id === message.id)) return
      this.messagesByMeetingId[message.meeting_id] = [...existing, message]
    },
    async endMeeting(meetingId: string, outcome: MeetingOutcome) {
      const meeting = await api.post<Meeting>(`/meetings/${pathSegment(meetingId)}/end`, outcome)
      this.upsertMeeting(meeting)
      await useRoomsStore().fetchRooms()
      return meeting
    },
    upsertMeeting(meeting: Meeting) {
      const index = this.meetings.findIndex((existing) => existing.id === meeting.id)
      if (index === -1) this.meetings.push(meeting)
      else this.meetings[index] = meeting
    },
  },
})

export interface MeetingOutcome {
  summary: string
  decisions?: string[]
  action_items?: string[]
  unresolved_questions?: string[]
}
