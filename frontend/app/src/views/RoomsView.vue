<script setup lang="ts">
import { onMounted, ref } from "vue"
import MeetingPanel from "../components/room/MeetingPanel.vue"
import CreateMeetingDialog from "../components/room/CreateMeetingDialog.vue"
import { useMeetingsStore } from "../stores/meetings"
import { useRoomsStore } from "../stores/rooms"

const rooms = useRoomsStore()
const meetings = useMeetingsStore()
const showCreateMeeting = ref(false)

onMounted(async () => {
  await Promise.all([rooms.fetchRooms(), meetings.fetchMeetings()])
})

function agentsIn(roomId: string) {
  return rooms.agentsByRoomId[roomId] ?? []
}
</script>

<template>
  <div class="p-4">
    <div class="flex items-center justify-between">
      <h2 class="text-xs font-semibold uppercase tracking-wide text-gray-400">Rooms</h2>
      <button class="rounded bg-gray-100 px-2 py-1 text-sm" @click="showCreateMeeting = true">+ Meeting</button>
    </div>
    <div class="mt-3 flex flex-col gap-3">
      <div v-for="room in rooms.rooms" :key="room.id" class="rounded-lg border border-gray-200 bg-white p-3">
        <p class="font-medium">{{ room.type === "main" ? "🏢" : "💬" }} {{ room.name }}</p>
        <p class="text-sm text-gray-500">{{ agentsIn(room.id).length }} agents</p>
        <div class="mt-1 flex flex-wrap gap-3">
          <div v-for="agent in agentsIn(room.id)" :key="agent.id" class="text-sm">
            {{ agent.name }} <span class="text-gray-400">· {{ agent.status }}</span>
          </div>
        </div>
        <MeetingPanel
          v-if="meetings.byRoomId(room.id)"
          :meeting="meetings.byRoomId(room.id)!"
          :participant-ids="agentsIn(room.id).map((a) => a.id)"
        />
      </div>
    </div>
    <CreateMeetingDialog v-if="showCreateMeeting" @close="showCreateMeeting = false" />
  </div>
</template>
