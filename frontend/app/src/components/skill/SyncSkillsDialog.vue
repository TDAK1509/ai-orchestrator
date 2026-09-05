<script setup lang="ts">
import { onMounted, ref } from "vue"
import type { Skill, SkillAvailableEntry, SkillImportSummary } from "../../api/types"
import { useSkillsStore } from "../../stores/skills"
import SkillRemovalWarning from "./SkillRemovalWarning.vue"

const emit = defineEmits<{ close: []; synced: [summary: SkillImportSummary] }>()

const skills = useSkillsStore()
const loading = ref(true)
const entries = ref<SkillAvailableEntry[]>([])
const ticked = ref<Set<string>>(new Set())
const removalWarnings = ref<{ slug: string; name: string; agentNames: string[] }[] | null>(null)
const syncing = ref(false)
const error = ref("")

onMounted(async () => {
  entries.value = await skills.fetchAvailableSkills()
  ticked.value = new Set(entries.value.filter((entry) => entry.in_catalog).map((entry) => entry.slug))
  loading.value = false
})

function toggle(slug: string): void {
  if (ticked.value.has(slug)) ticked.value.delete(slug)
  else ticked.value.add(slug)
}

function selectAll(): void {
  ticked.value = new Set(entries.value.map((entry) => entry.slug))
}

function selectNone(): void {
  ticked.value = new Set()
}

function findRemovedEntries(): SkillAvailableEntry[] {
  return entries.value.filter((entry) => entry.in_catalog && !ticked.value.has(entry.slug))
}

async function startSync(): Promise<void> {
  const removed = findRemovedEntries()
  if (removed.length === 0) {
    await runSync()
    return
  }
  removalWarnings.value = await Promise.all(removed.map((entry) => buildRemovalWarning(entry)))
}

async function buildRemovalWarning(entry: SkillAvailableEntry) {
  const skill = findImportedSkillBySlug(entry.slug)
  const agents = skill ? await skills.fetchAssignedAgents(skill.id) : []
  return { slug: entry.slug, name: entry.name, agentNames: agents.map((agent) => agent.name) }
}

function findImportedSkillBySlug(slug: string): Skill | undefined {
  return skills.skills.find((skill) => skill.slug === slug && skill.source === "imported")
}

async function runSync(): Promise<void> {
  syncing.value = true
  error.value = ""
  try {
    const summary = await skills.importFromClaudeCode([...ticked.value])
    emit("synced", summary)
    emit("close")
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Sync failed"
  } finally {
    syncing.value = false
  }
}
</script>

<template>
  <div class="fixed inset-0 z-30 flex items-center justify-center bg-black/30">
    <div class="w-[28rem] rounded-lg bg-white p-4 shadow-xl">
      <div class="flex items-center justify-between">
        <h2 class="text-lg font-semibold">Sync skills</h2>
        <button class="text-gray-400 hover:text-gray-600" @click="$emit('close')">✕</button>
      </div>

      <div v-if="loading" class="mt-3 text-sm text-gray-500">Loading...</div>

      <template v-else-if="removalWarnings === null">
        <div class="mt-2 flex gap-2 text-xs">
          <button class="text-blue-600" @click="selectAll">All</button>
          <button class="text-blue-600" @click="selectNone">None</button>
        </div>
        <div class="mt-2 max-h-72 space-y-1 overflow-y-auto">
          <label v-for="entry in entries" :key="entry.slug" class="flex items-center gap-2 text-sm">
            <input type="checkbox" :checked="ticked.has(entry.slug)" @change="toggle(entry.slug)" />
            <span>{{ entry.name }}</span>
            <span v-if="!entry.on_disk" class="text-xs text-amber-600">(missing)</span>
          </label>
        </div>
        <p v-if="error" class="mt-2 text-sm text-red-600">{{ error }}</p>
        <div class="mt-4 flex justify-end gap-2">
          <button class="rounded border border-gray-300 px-3 py-1.5 text-sm" @click="$emit('close')">Cancel</button>
          <button class="rounded bg-blue-600 px-3 py-1.5 text-sm text-white disabled:opacity-50" :disabled="syncing" @click="startSync">
            {{ syncing ? "Syncing..." : "Sync" }}
          </button>
        </div>
      </template>

      <template v-else>
        <p class="mt-3 text-sm text-gray-600">Removing these will unassign them from every agent that holds them.</p>
        <div class="mt-2 max-h-72 space-y-2 overflow-y-auto rounded border border-red-200 bg-red-50 p-2 text-sm">
          <div v-for="warning in removalWarnings" :key="warning.slug">
            <p class="font-medium">{{ warning.name }}</p>
            <SkillRemovalWarning :agent-names="warning.agentNames" />
          </div>
        </div>
        <p v-if="error" class="mt-2 text-sm text-red-600">{{ error }}</p>
        <div class="mt-4 flex justify-end gap-2">
          <button class="rounded border border-gray-300 px-3 py-1.5 text-sm" :disabled="syncing" @click="removalWarnings = null">
            Back
          </button>
          <button class="rounded bg-red-600 px-3 py-1.5 text-sm text-white disabled:opacity-50" :disabled="syncing" @click="runSync">
            {{ syncing ? "Syncing..." : "Sync" }}
          </button>
        </div>
      </template>
    </div>
  </div>
</template>
