<script setup lang="ts">
import { ref } from "vue"
import type { Skill } from "../../api/types"
import { useAgentsStore } from "../../stores/agents"
import { useSkillsStore } from "../../stores/skills"

const props = defineProps<{ skill: Skill }>()

const agents = useAgentsStore()
const skills = useSkillsStore()
const expanded = ref(false)
const instructionsDraft = ref(props.skill.instructions)

async function saveInstructions(): Promise<void> {
  await skills.editSkill(props.skill.id, { instructions: instructionsDraft.value })
}

function assignTo(agentId: string): void {
  if (agentId) skills.assignToAgent(props.skill.id, agentId)
}
</script>

<template>
  <div class="rounded-lg border border-gray-200 bg-white p-3 shadow-sm">
    <div class="flex items-start justify-between">
      <div>
        <p class="font-medium">{{ skill.name }}</p>
        <p class="text-sm text-gray-500">{{ skill.description }}</p>
      </div>
      <div class="flex gap-2 text-sm">
        <button class="text-blue-600" @click="expanded = !expanded">{{ expanded ? "Collapse" : "Edit" }}</button>
        <button class="text-red-600" @click="skills.deleteSkill(skill.id)">Delete</button>
      </div>
    </div>
    <div v-if="expanded" class="mt-2">
      <textarea v-model="instructionsDraft" rows="4" class="w-full rounded border border-gray-300 px-2 py-1 text-sm" />
      <button class="mt-1 rounded bg-blue-600 px-2 py-1 text-sm text-white" @click="saveInstructions">Save</button>
    </div>
    <select class="mt-2 w-full rounded border border-gray-300 text-xs" @change="assignTo(($event.target as HTMLSelectElement).value)">
      <option value="">Assign to agent...</option>
      <option v-for="agent in agents.activeAgents" :key="agent.id" :value="agent.id">{{ agent.name }}</option>
    </select>
  </div>
</template>
