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
const summaryDraft = ref("")
const decisionsDraft = ref("")
const actionItemsDraft = ref("")
const unresolvedDraft = ref("")
const speakerId = ref(props.participantIds[0] ?? "")

onMounted(() => {
  if (props.meeting.status === "active") meetings.fetchMessages(props.meeting.id)
})

function messages() {
  return meetings.messagesByMeetingId[props.meeting.id] ?? []
}

function agentName(agentId: string): string {
  return agents.byId(agentId)?.name ?? "Unknown"
}

async function post(): Promise<void> {
  if (!draft.value || !speakerId.value) return
  await meetings.addMessage(props.meeting.id, speakerId.value, draft.value)
  draft.value = ""
}

function splitLines(value: string): string[] {
  return value.split("\n").map((line) => line.trim()).filter(Boolean)
}

async function end(): Promise<void> {
  if (!summaryDraft.value) return
  await meetings.endMeeting(props.meeting.id, {
    summary: summaryDraft.value,
    decisions: splitLines(decisionsDraft.value),
    action_items: splitLines(actionItemsDraft.value),
    unresolved_questions: splitLines(unresolvedDraft.value),
  })
}
</script>

<template>
  <div class="mt-2 border-t border-gray-100 pt-2">
    <div v-if="meeting.status === 'active'">
      <div v-for="message in messages()" :key="message.id" class="mt-1 text-sm">
        <span class="font-medium">{{ agentName(message.agent_id) }}</span>
        <span class="text-gray-600"> {{ message.content }}</span>
      </div>
      <div class="mt-2 flex gap-2">
        <select v-model="speakerId" class="rounded border border-gray-300 text-xs">
          <option v-for="id in participantIds" :key="id" :value="id">{{ agentName(id) }}</option>
        </select>
        <input v-model="draft" class="flex-1 rounded border border-gray-300 px-2 py-1 text-sm" placeholder="Message..." />
        <button class="rounded bg-gray-100 px-2 py-1 text-sm" @click="post">Send</button>
      </div>
      <div class="mt-3 flex flex-col gap-1">
        <input v-model="summaryDraft" class="rounded border border-gray-300 px-2 py-1 text-sm" placeholder="Summary to end the meeting..." />
        <textarea v-model="decisionsDraft" class="rounded border border-gray-300 px-2 py-1 text-sm" rows="2" placeholder="Decisions, one per line" />
        <textarea v-model="actionItemsDraft" class="rounded border border-gray-300 px-2 py-1 text-sm" rows="2" placeholder="Action items, one per line" />
        <textarea v-model="unresolvedDraft" class="rounded border border-gray-300 px-2 py-1 text-sm" rows="2" placeholder="Unresolved questions, one per line" />
        <button class="self-start rounded bg-red-600 px-2 py-1 text-sm text-white" @click="end">End Meeting</button>
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
