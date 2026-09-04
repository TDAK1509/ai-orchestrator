<script setup lang="ts">
import { computed, onMounted, ref } from "vue"
import type { MemoryType } from "../api/types"
import { useAgentsStore } from "../stores/agents"
import { useMemoryStore } from "../stores/memory"
import { useTeamsStore } from "../stores/teams"

const teams = useTeamsStore()
const agents = useAgentsStore()
const memory = useMemoryStore()
const newTeamName = ref("")
const newTeamDescription = ref("")
const draftContentByTeamId = ref<Record<string, string>>({})
const draftTypeByTeamId = ref<Record<string, MemoryType>>({})
const draftAssigneeByTeamId = ref<Record<string, string>>({})
const confirmingArchive = ref<string | null>(null)

const membersByTeamId = computed(() => {
  const grouped: Record<string, typeof agents.agents> = {}
  for (const agent of agents.activeAgents) {
    if (!agent.team_id) continue
    ;(grouped[agent.team_id] ??= []).push(agent)
  }
  return grouped
})

const unassignedAgents = computed(() => (teamId: string) => agents.activeAgents.filter((agent) => agent.team_id !== teamId))

onMounted(async () => {
  await teams.fetchTeams()
  await Promise.all(teams.teams.map((team) => memory.fetchTeamMemories(team.id)))
})

async function createTeam(): Promise<void> {
  if (!newTeamName.value) return
  await teams.createTeam(newTeamName.value, newTeamDescription.value)
  newTeamName.value = ""
  newTeamDescription.value = ""
}

async function addTeamMemory(teamId: string): Promise<void> {
  const content = draftContentByTeamId.value[teamId]
  if (!content) return
  await memory.createTeamMemory(teamId, content, draftTypeByTeamId.value[teamId] ?? "fact")
  draftContentByTeamId.value[teamId] = ""
}

async function assignAgent(teamId: string): Promise<void> {
  const agentId = draftAssigneeByTeamId.value[teamId]
  if (!agentId) return
  await teams.assignAgent(teamId, agentId)
  draftAssigneeByTeamId.value[teamId] = ""
}

async function confirmArchive(teamId: string): Promise<void> {
  await teams.archiveTeam(teamId)
  confirmingArchive.value = null
}
</script>

<template>
  <div class="p-4">
    <h2 class="text-xs font-semibold uppercase tracking-wide text-gray-400">Teams</h2>
    <div class="mt-3 flex gap-2 rounded-lg border border-gray-200 bg-white p-3">
      <input v-model="newTeamName" placeholder="Team name..." class="flex-1 rounded border border-gray-300 px-2 py-1 text-sm" />
      <input v-model="newTeamDescription" placeholder="Description..." class="flex-1 rounded border border-gray-300 px-2 py-1 text-sm" />
      <button class="rounded bg-blue-600 px-3 py-1.5 text-sm text-white" @click="createTeam">Add Team</button>
    </div>

    <div v-for="team in teams.teams" :key="team.id" class="mt-4 rounded-lg border border-gray-200 bg-white p-3">
      <div class="flex items-start justify-between">
        <div>
          <h3 class="font-medium">{{ team.name }}</h3>
          <p v-if="team.description" class="text-sm text-gray-500">{{ team.description }}</p>
        </div>
        <button v-if="confirmingArchive !== team.id" class="text-xs text-red-600" @click="confirmingArchive = team.id">Archive Team</button>
        <div v-else class="flex shrink-0 gap-2 text-xs">
          <button class="text-red-600" @click="confirmArchive(team.id)">Confirm</button>
          <button class="text-gray-500" @click="confirmingArchive = null">Cancel</button>
        </div>
      </div>

      <h4 class="mt-3 text-xs font-semibold uppercase tracking-wide text-gray-400">Members</h4>
      <ul class="mt-1 flex flex-col gap-1 text-sm">
        <li v-for="agent in membersByTeamId[team.id] ?? []" :key="agent.id" class="flex items-center justify-between">
          <span>{{ agent.name }} -- {{ agent.role }}</span>
          <button class="text-xs text-red-600" @click="teams.unassignAgent(team.id, agent.id)">Remove</button>
        </li>
        <li v-if="!(membersByTeamId[team.id] ?? []).length" class="text-gray-400">No members yet.</li>
      </ul>
      <div class="mt-1 flex gap-2">
        <select v-model="draftAssigneeByTeamId[team.id]" class="flex-1 rounded border border-gray-300 px-2 py-1 text-sm">
          <option value="">Add an existing agent...</option>
          <option v-for="agent in unassignedAgents(team.id)" :key="agent.id" :value="agent.id">{{ agent.name }}</option>
        </select>
        <button class="rounded border border-gray-300 px-3 py-1.5 text-sm" @click="assignAgent(team.id)">Add</button>
      </div>

      <h4 class="mt-3 text-xs font-semibold uppercase tracking-wide text-gray-400">Team Memory</h4>
      <div class="mt-1 flex gap-2">
        <input
          v-model="draftContentByTeamId[team.id]"
          placeholder="New fact this team should know..."
          class="flex-1 rounded border border-gray-300 px-2 py-1 text-sm"
        />
        <select v-model="draftTypeByTeamId[team.id]" class="rounded border border-gray-300 px-2 py-1 text-sm">
          <option value="fact">Fact</option>
          <option value="convention">Convention</option>
          <option value="architecture">Architecture</option>
          <option value="preference">Preference</option>
        </select>
        <button class="rounded bg-blue-600 px-3 py-1.5 text-sm text-white" @click="addTeamMemory(team.id)">Add</button>
      </div>
      <div class="mt-2 flex flex-col gap-2">
        <div
          v-for="record in memory.teamMemoriesByTeamId[team.id] ?? []"
          :key="record.id"
          class="flex items-start justify-between rounded-lg border border-gray-200 bg-white p-3"
        >
          <div>
            <p class="text-sm">{{ record.content }}</p>
            <p class="mt-1 text-xs uppercase tracking-wide text-gray-400">{{ record.type }}</p>
          </div>
          <div class="flex gap-2 text-sm">
            <button v-if="!record.pinned" class="text-blue-600" @click="memory.pin(record.id)">Pin</button>
            <button v-else class="text-blue-600" @click="memory.unpin(record.id)">Unpin</button>
            <button class="text-red-600" @click="memory.archive(record.id)">Archive</button>
          </div>
        </div>
      </div>
    </div>
    <p v-if="!teams.teams.length" class="mt-4 text-sm text-gray-400">No teams yet.</p>
  </div>
</template>
