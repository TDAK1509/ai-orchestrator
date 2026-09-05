<script setup lang="ts">
import { computed, onMounted, ref } from "vue"
import type { Agent } from "../../api/types"
import { useSkillsStore } from "../../stores/skills"
import SkillCheckboxList from "../skill/SkillCheckboxList.vue"

const props = defineProps<{ agent: Agent }>()
const emit = defineEmits<{ close: [] }>()

const skills = useSkillsStore()
const loading = ref(true)
const loadFailed = ref(false)
const initialSkillIds = ref<string[]>([])
const ticked = ref<Set<string>>(new Set())
const saving = ref(false)
const error = ref("")

onMounted(async () => {
  try {
    const [, agentSkills] = await Promise.all([skills.fetchSkills(), skills.fetchAgentSkills(props.agent.id)])
    initialSkillIds.value = agentSkills.map((skill) => skill.id)
    ticked.value = new Set(initialSkillIds.value)
  } catch (err) {
    loadFailed.value = true
    error.value = err instanceof Error ? err.message : "Could not load skills"
  } finally {
    loading.value = false
  }
})

const checklistItems = computed(() => skills.skills.map((skill) => ({ key: skill.id, label: skill.name })))

function toggle(skillId: string): void {
  if (ticked.value.has(skillId)) ticked.value.delete(skillId)
  else ticked.value.add(skillId)
}

function selectAll(): void {
  ticked.value = new Set(skills.skills.map((skill) => skill.id))
}

function selectNone(): void {
  ticked.value = new Set()
}

async function save(): Promise<void> {
  saving.value = true
  error.value = ""
  try {
    await applyChanges()
    emit("close")
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Some changes could not be saved; the list below reflects what actually took effect."
  } finally {
    await skills.fetchAgentSkills(props.agent.id)
    saving.value = false
  }
}

async function applyChanges(): Promise<void> {
  // Sequential, not Promise.all: a failure partway through must stop before firing the remaining
  // mutations, and the always-run refetch above is what keeps the sheet honest either way.
  const current = new Set(initialSkillIds.value)
  for (const id of ticked.value) {
    if (!current.has(id)) await skills.assignToAgent(id, props.agent.id)
  }
  for (const id of current) {
    if (!ticked.value.has(id)) await skills.unassignFromAgent(id, props.agent.id)
  }
}
</script>

<template>
  <div class="fixed inset-0 z-30 flex items-center justify-center bg-black/30">
    <div class="w-[28rem] rounded-lg bg-white p-4 shadow-xl">
      <div class="flex items-center justify-between">
        <h2 class="text-lg font-semibold">Assign skills</h2>
        <button class="text-gray-400 hover:text-gray-600" @click="$emit('close')">✕</button>
      </div>

      <div v-if="loading" class="mt-3 text-sm text-gray-500">Loading...</div>

      <template v-else-if="loadFailed">
        <p class="mt-3 text-sm text-red-600">{{ error }}</p>
        <div class="mt-4 flex justify-end">
          <button class="rounded border border-gray-300 px-3 py-1.5 text-sm" @click="$emit('close')">Close</button>
        </div>
      </template>

      <template v-else>
        <div class="mt-2 flex gap-2 text-xs">
          <button class="text-blue-600" @click="selectAll">All</button>
          <button class="text-blue-600" @click="selectNone">None</button>
        </div>
        <SkillCheckboxList class="mt-2" :items="checklistItems" :ticked="ticked" @toggle="toggle" />
        <p v-if="error" class="mt-2 text-sm text-red-600">{{ error }}</p>
        <div class="mt-4 flex justify-end gap-2">
          <button class="rounded border border-gray-300 px-3 py-1.5 text-sm" :disabled="saving" @click="$emit('close')">Cancel</button>
          <button class="rounded bg-blue-600 px-3 py-1.5 text-sm text-white disabled:opacity-50" :disabled="saving" @click="save">
            {{ saving ? "Saving..." : "Save" }}
          </button>
        </div>
      </template>
    </div>
  </div>
</template>
