<script setup lang="ts">
import { onMounted, ref } from "vue"
import type { AgentEffort } from "../../api/types"
import { useAgentsStore } from "../../stores/agents"
import { useTeamsStore } from "../../stores/teams"

defineEmits<{ close: [] }>()

const agents = useAgentsStore()
const teams = useTeamsStore()
const name = ref("")
const role = ref("")
const instructions = ref("")
const teamId = ref("")
const model = ref("")
const effort = ref<AgentEffort | "">("")
const submitting = ref(false)

const MODEL_OPTIONS = ["claude-opus-5", "claude-sonnet-5", "claude-haiku-4-5", "claude-fable-5-1"]
const EFFORT_OPTIONS = ["low", "medium", "high", "xhigh", "max"]

onMounted(() => {
  if (!teams.teams.length) teams.fetchTeams()
})

function canSubmit(): boolean {
  return Boolean(name.value && role.value)
}

async function submit(onDone: () => void): Promise<void> {
  if (!canSubmit()) return
  submitting.value = true
  try {
    await agents.hireAgent(name.value, role.value, instructions.value, teamId.value || null, model.value || null, effort.value || null)
    onDone()
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="fixed inset-0 z-30 flex items-center justify-center bg-black/30">
    <div class="w-96 rounded-lg bg-white p-4 shadow-xl">
      <div class="flex items-center justify-between">
        <h2 class="text-lg font-semibold">Hire Agent</h2>
        <button class="text-gray-400 hover:text-gray-600" @click="$emit('close')">✕</button>
      </div>
      <label class="mt-3 block text-sm font-medium">Name</label>
      <input v-model="name" class="mt-1 w-full rounded border border-gray-300 px-2 py-1" />
      <label class="mt-3 block text-sm font-medium">Role</label>
      <input v-model="role" class="mt-1 w-full rounded border border-gray-300 px-2 py-1" />
      <label class="mt-3 block text-sm font-medium">Instructions</label>
      <textarea v-model="instructions" class="mt-1 w-full rounded border border-gray-300 px-2 py-1" rows="3" />
      <label class="mt-3 block text-sm font-medium">Team</label>
      <select v-model="teamId" class="mt-1 w-full rounded border border-gray-300 px-2 py-1">
        <option value="">No team</option>
        <option v-for="team in teams.teams" :key="team.id" :value="team.id">{{ team.name }}</option>
      </select>
      <label class="mt-3 block text-sm font-medium">Model</label>
      <select v-model="model" class="mt-1 w-full rounded border border-gray-300 px-2 py-1">
        <option value="">Workspace default</option>
        <option v-for="option in MODEL_OPTIONS" :key="option" :value="option">{{ option }}</option>
      </select>
      <label class="mt-3 block text-sm font-medium">Effort</label>
      <select v-model="effort" class="mt-1 w-full rounded border border-gray-300 px-2 py-1">
        <option value="">Workspace default</option>
        <option v-for="option in EFFORT_OPTIONS" :key="option" :value="option">{{ option }}</option>
      </select>
      <div class="mt-4 flex justify-end gap-2">
        <button class="rounded border border-gray-300 px-3 py-1.5 text-sm" @click="$emit('close')">Cancel</button>
        <button
          class="rounded bg-blue-600 px-3 py-1.5 text-sm text-white disabled:opacity-50"
          :disabled="!canSubmit() || submitting"
          @click="submit(() => $emit('close'))"
        >
          Hire Agent
        </button>
      </div>
    </div>
  </div>
</template>
