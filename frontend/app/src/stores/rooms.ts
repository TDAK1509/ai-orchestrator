import { defineStore } from "pinia"
import { api } from "../api/client"
import type { Agent, Room } from "../api/types"

export const useRoomsStore = defineStore("rooms", {
  state: () => ({
    rooms: [] as Room[],
    agentsByRoomId: {} as Record<string, Agent[]>,
  }),
  actions: {
    async fetchRooms() {
      this.rooms = await api.get<Room[]>("/rooms")
      await Promise.all(this.rooms.map((room) => this.fetchRoomAgents(room.id)))
    },
    async fetchRoomAgents(roomId: string) {
      this.agentsByRoomId[roomId] = await api.get<Agent[]>(`/rooms/${roomId}/agents`)
    },
  },
})
