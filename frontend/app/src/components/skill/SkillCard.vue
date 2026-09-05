<script setup lang="ts">
import { computed, ref } from "vue"
import type { Skill } from "../../api/types"
import { useAgentsStore } from "../../stores/agents"
import { useSkillsStore } from "../../stores/skills"

const props = defineProps<{ skill: Skill }>()

const agents = useAgentsStore()
const skills = useSkillsStore()
const expanded = ref(false)
const instructionsDraft = ref(props.skill.instructions)
const confirmingDelete = ref(false)
const isImported = computed(() => props.skill.source === "imported")

async function saveInstructions(): Promise<void> {
  await skills.editSkill(props.skill.id, { instructions: instructionsDraft.value })
}

function assignTo(agentId: string): void {
  if (agentId) skills.assignToAgent(props.skill.id, agentId)
}

async function startDeleteConfirmation(): Promise<void> {
  await skills.fetchAssignedAgents(props.skill.id)
  confirmingDelete.value = true
}

function assignedAgents() {
  return skills.assignedAgentsBySkillId[props.skill.id] ?? []
}

async function confirmDelete(): Promise<void> {
  await skills.deleteSkill(props.skill.id)
  confirmingDelete.value = false
}
</script>

<template>
  <div class="rounded-lg border border-gray-200 bg-white p-3 shadow-sm">
    <div class="flex items-start justify-between">
      <div>
        <div class="flex items-center gap-2">
          <p class="font-medium">{{ skill.name }}</p>
          <span v-if="isImported" class="rounded bg-gray-100 px-1.5 py-0.5 text-xs text-gray-500">Imported from Claude Code</span>
        </div>
        <p class="text-sm text-gray-500">{{ skill.description }}</p>
      </div>
      <div class="flex gap-2 text-sm">
        <button class="text-blue-600" @click="expanded = !expanded">{{ expanded ? "Collapse" : "Edit" }}</button>
        <button class="text-red-600" @click="startDeleteConfirmation">Delete</button>
      </div>
    </div>
    <div v-if="expanded" class="mt-2">
      <textarea v-model="instructionsDraft" rows="4" class="w-full rounded border border-gray-300 px-2 py-1 text-sm" />
      <button class="mt-1 rounded bg-blue-600 px-2 py-1 text-sm text-white" @click="saveInstructions">Save</button>
    </div>
    <div v-if="confirmingDelete" class="mt-2 rounded border border-red-200 bg-red-50 p-2 text-sm">
      <p v-if="assignedAgents().length">
        Assigned to {{ assignedAgents().map((a) => a.name).join(", ") }}. They will lose this skill.
      </p>
      <p v-else>No agents are assigned to this skill.</p>
      <div class="mt-2 flex gap-2">
        <button class="rounded bg-red-600 px-2 py-1 text-white" @click="confirmDelete">Delete Skill</button>
        <button class="rounded border border-gray-300 px-2 py-1" @click="confirmingDelete = false">Cancel</button>
      </div>
    </div>
    <select class="mt-2 w-full rounded border border-gray-300 text-xs" @change="assignTo(($event.target as HTMLSelectElement).value)">
      <option value="">Assign to agent...</option>
      <option v-for="agent in agents.activeAgents" :key="agent.id" :value="agent.id">{{ agent.name }}</option>
    </select>
  </div>
</template>
