<script setup lang="ts">
import type { Agent } from "../../api/types"
import { useAgentsStore } from "../../stores/agents"
import AgentCard from "../agent/AgentCard.vue"

defineEmits<{ select: [agent: Agent] }>()

const agents = useAgentsStore()
</script>

<template>
  <aside class="w-72 shrink-0 border-r border-gray-200 bg-gray-50 p-3 overflow-y-auto">
    <h2 class="mb-3 text-xs font-semibold uppercase tracking-wide text-gray-400">Agents</h2>
    <div class="flex flex-col gap-2">
      <AgentCard v-for="agent in agents.agents" :key="agent.id" :agent="agent" @select="$emit('select', $event)" />
    </div>
  </aside>
</template>
