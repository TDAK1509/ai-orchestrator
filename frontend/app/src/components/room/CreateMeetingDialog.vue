<script setup lang="ts">
import { ref } from "vue"
import { useAgentsStore } from "../../stores/agents"
import { useMeetingsStore } from "../../stores/meetings"

defineEmits<{ close: [] }>()

const agents = useAgentsStore()
const meetings = useMeetingsStore()
const topic = ref("")
const goal = ref("")
const selected = ref<Set<string>>(new Set())

function toggle(agentId: string): void {
  if (selected.value.has(agentId)) selected.value.delete(agentId)
  else selected.value.add(agentId)
}

async function submit(onDone: () => void): Promise<void> {
  if (!topic.value || selected.value.size === 0) return
  await meetings.createMeeting(topic.value, goal.value || undefined, [...selected.value])
  onDone()
}
</script>

<template>
  <div class="fixed inset-0 z-30 flex items-center justify-center bg-black/30">
    <div class="w-96 rounded-lg bg-white p-4 shadow-xl">
      <div class="flex items-center justify-between">
        <h2 class="text-lg font-semibold">Create Meeting</h2>
        <button class="text-gray-400 hover:text-gray-600" @click="$emit('close')">✕</button>
      </div>
      <label class="mt-3 block text-sm font-medium">Topic</label>
      <input v-model="topic" class="mt-1 w-full rounded border border-gray-300 px-2 py-1" />
      <label class="mt-3 block text-sm font-medium">Participants</label>
      <div class="mt-1 flex flex-col gap-1">
        <label v-for="agent in agents.activeAgents" :key="agent.id" class="flex items-center gap-2 text-sm">
          <input type="checkbox" :checked="selected.has(agent.id)" @change="toggle(agent.id)" />
          {{ agent.name }} · {{ agent.role }}
        </label>
      </div>
      <label class="mt-3 block text-sm font-medium">Goal / Instructions</label>
      <textarea v-model="goal" class="mt-1 w-full rounded border border-gray-300 px-2 py-1" rows="2" />
      <div class="mt-4 flex justify-end gap-2">
        <button class="rounded border border-gray-300 px-3 py-1.5 text-sm" @click="$emit('close')">Cancel</button>
        <button class="rounded bg-blue-600 px-3 py-1.5 text-sm text-white" @click="submit(() => $emit('close'))">Create</button>
      </div>
    </div>
  </div>
</template>
