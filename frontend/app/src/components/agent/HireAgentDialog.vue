<script setup lang="ts">
import { onMounted, ref } from "vue"
import type { AgentEffort } from "../../api/types"
import { useAgentsStore } from "../../stores/agents"
import { useSkillsStore } from "../../stores/skills"
import { useTeamsStore } from "../../stores/teams"

defineEmits<{ close: [] }>()

const agents = useAgentsStore()
const teams = useTeamsStore()
const skills = useSkillsStore()
const name = ref("")
const role = ref("")
const instructions = ref("")
const teamId = ref("")
const model = ref("")
const effort = ref<AgentEffort | "">("")
const skillIds = ref<string[]>([])
const submitting = ref(false)
const submitError = ref("")

const MODEL_OPTIONS = ["claude-opus-5", "claude-sonnet-5", "claude-haiku-4-5", "claude-fable-5-1"]
const EFFORT_OPTIONS = ["low", "medium", "high", "xhigh", "max"]

onMounted(() => {
  if (!teams.teams.length) teams.fetchTeams()
  if (!skills.skills.length) skills.fetchSkills()
})

function canSubmit(): boolean {
  return Boolean(name.value && role.value)
}

async function submit(onDone: () => void): Promise<void> {
  if (!canSubmit()) return
  submitting.value = true
  submitError.value = ""
  try {
    await agents.hireAgent({
      name: name.value,
      role: role.value,
      instructions: instructions.value,
      teamId: teamId.value || null,
      model: model.value || null,
      effort: effort.value || null,
      skillIds: skillIds.value,
    })
    onDone()
  } catch (err) {
    submitError.value = err instanceof Error ? err.message : "Failed to hire agent"
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
      <label class="mt-3 block text-sm font-medium">Skills</label>
      <div class="mt-1 max-h-32 overflow-y-auto rounded border border-gray-300 p-2">
        <label v-for="skill in skills.skills" :key="skill.id" class="flex items-center gap-2 text-sm">
          <input v-model="skillIds" type="checkbox" :value="skill.id" />
          {{ skill.name }}
        </label>
      </div>
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
      <p v-if="submitError" class="mt-3 text-sm text-red-600">{{ submitError }}</p>
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
