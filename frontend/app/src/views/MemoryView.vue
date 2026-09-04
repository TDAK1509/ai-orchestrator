<script setup lang="ts">
import { onMounted, ref } from "vue"
import type { MemoryType } from "../api/types"
import { useMemoryStore } from "../stores/memory"

const memory = useMemoryStore()
const content = ref("")
const type = ref<MemoryType>("fact")

onMounted(() => {
  memory.fetchWorkspaceMemories()
  memory.fetchProposals()
})

async function addMemory(): Promise<void> {
  if (!content.value) return
  await memory.createWorkspaceMemory(content.value, type.value)
  content.value = ""
}
</script>

<template>
  <div class="p-4">
    <h2 class="text-xs font-semibold uppercase tracking-wide text-gray-400">Workspace Memory</h2>
    <div class="mt-3 flex gap-2 rounded-lg border border-gray-200 bg-white p-3">
      <input v-model="content" placeholder="New fact every agent should know..." class="flex-1 rounded border border-gray-300 px-2 py-1 text-sm" />
      <select v-model="type" class="rounded border border-gray-300 px-2 py-1 text-sm">
        <option value="fact">Fact</option>
        <option value="convention">Convention</option>
        <option value="architecture">Architecture</option>
        <option value="preference">Preference</option>
      </select>
      <button class="rounded bg-blue-600 px-3 py-1.5 text-sm text-white" @click="addMemory">Add</button>
    </div>
    <div class="mt-4 flex flex-col gap-2">
      <div v-for="record in memory.workspaceMemories" :key="record.id" class="flex items-start justify-between rounded-lg border border-gray-200 bg-white p-3">
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

    <h2 v-if="memory.proposals.length" class="mt-6 text-xs font-semibold uppercase tracking-wide text-gray-400">Consolidation Proposals</h2>
    <div v-if="memory.proposals.length" class="mt-2 flex flex-col gap-2">
      <div v-for="proposal in memory.proposals" :key="proposal.id" class="flex items-center justify-between rounded-lg border border-gray-200 bg-white p-3 text-sm">
        <p>Similar memories found ({{ Math.round(proposal.similarity * 100) }}% match) -- supersede the older one?</p>
        <div class="flex shrink-0 gap-2">
          <button class="text-blue-600" @click="memory.applyProposal(proposal.id)">Apply</button>
          <button class="text-gray-500" @click="memory.dismissProposal(proposal.id)">Dismiss</button>
        </div>
      </div>
    </div>
  </div>
</template>
