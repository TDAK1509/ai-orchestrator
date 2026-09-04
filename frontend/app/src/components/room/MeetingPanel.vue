<script setup lang="ts">
import { onMounted, ref } from "vue"
import type { Meeting } from "../../api/types"
import { useAgentsStore } from "../../stores/agents"
import { useMeetingsStore } from "../../stores/meetings"
import MeetingOutcomeList from "./MeetingOutcomeList.vue"

const props = defineProps<{ meeting: Meeting; participantIds: string[] }>()

const meetings = useMeetingsStore()
const agents = useAgentsStore()
const draft = ref("")

onMounted(() => {
  if (props.meeting.status === "active") meetings.fetchMessages(props.meeting.id)
})

function messages() {
  return meetings.messagesByMeetingId[props.meeting.id] ?? []
}

function speakerLabel(agentId: string | null): string {
  if (!agentId) return "Human"
  return agents.byId(agentId)?.name ?? "Unknown"
}

async function post(): Promise<void> {
  if (!draft.value) return
  await meetings.addHumanMessage(props.meeting.id, draft.value)
  draft.value = ""
}
</script>

<template>
  <div class="mt-2 border-t border-gray-100 pt-2">
    <div v-if="meeting.goal" class="text-xs text-gray-500">Goal: {{ meeting.goal }}</div>
    <div v-if="meeting.status === 'active'">
      <div class="mt-1 text-xs text-gray-400">
        Round {{ meeting.current_round + 1 }} of {{ meeting.max_rounds }} · {{ meeting.loop_state }} · next: {{ speakerLabel(meeting.next_speaker_id) }}
      </div>
      <div v-for="message in messages()" :key="message.id" class="mt-1 text-sm">
        <span class="font-medium">{{ speakerLabel(message.agent_id) }}</span>
        <span class="text-gray-600"> {{ message.content }}</span>
      </div>
      <div class="mt-2 flex gap-2">
        <input v-model="draft" class="flex-1 rounded border border-gray-300 px-2 py-1 text-sm" placeholder="Say something to the room..." @keyup.enter="post" />
        <button class="rounded bg-gray-100 px-2 py-1 text-sm" @click="post">Send</button>
      </div>
      <div class="mt-3 flex flex-wrap gap-2">
        <button class="rounded bg-blue-600 px-2 py-1 text-sm text-white" @click="meetings.start(meeting.id)">Start</button>
        <button class="rounded bg-gray-100 px-2 py-1 text-sm" @click="meetings.runRound(meeting.id)">Run one round</button>
        <button class="rounded bg-gray-100 px-2 py-1 text-sm" @click="meetings.pause(meeting.id)">Pause</button>
        <button class="rounded bg-gray-100 px-2 py-1 text-sm" @click="meetings.stop(meeting.id)">Stop</button>
        <button class="rounded bg-red-600 px-2 py-1 text-sm text-white" @click="meetings.summarize(meeting.id)">Finish</button>
      </div>
    </div>
    <div v-else class="text-sm text-gray-600">
      <p>{{ meeting.summary }}</p>
      <MeetingOutcomeList label="Decisions" :items="meeting.decisions" />
      <MeetingOutcomeList label="Action items" :items="meeting.action_items" />
      <MeetingOutcomeList label="Unresolved questions" :items="meeting.unresolved_questions" />
    </div>
  </div>
</template>
