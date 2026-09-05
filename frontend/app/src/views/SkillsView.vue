<script setup lang="ts">
import { onMounted, ref } from "vue"
import SkillCard from "../components/skill/SkillCard.vue"
import SyncSkillsDialog from "../components/skill/SyncSkillsDialog.vue"
import type { SkillImportSummary } from "../api/types"
import { useSkillsStore } from "../stores/skills"

const skills = useSkillsStore()
const name = ref("")
const description = ref("")
const instructions = ref("")
const showSyncDialog = ref(false)
const importSummary = ref<SkillImportSummary | null>(null)

onMounted(() => {
  skills.fetchSkills()
})

async function createSkill(): Promise<void> {
  if (!name.value || !instructions.value) return
  await skills.createSkill(name.value, description.value || undefined, instructions.value)
  name.value = ""
  description.value = ""
  instructions.value = ""
}

function onSynced(summary: SkillImportSummary): void {
  importSummary.value = summary
}
</script>

<template>
  <div class="p-4">
    <div class="flex items-center justify-between">
      <h2 class="text-xs font-semibold uppercase tracking-wide text-gray-400">Skill Catalog</h2>
      <button class="rounded border border-gray-300 px-2 py-1 text-xs" @click="showSyncDialog = true">Sync from Claude Code</button>
    </div>
    <SyncSkillsDialog v-if="showSyncDialog" @close="showSyncDialog = false" @synced="onSynced" />
    <div v-if="importSummary" class="mt-2 rounded border border-gray-200 bg-gray-50 p-2 text-sm text-gray-600">
      {{ importSummary.created.length }} created, {{ importSummary.updated.length }} updated,
      {{ importSummary.removed.length }} removed, {{ importSummary.skipped.length }} skipped (custom skill owns that slug),
      {{ importSummary.errors.length }} errors.
    </div>
    <div class="mt-3 rounded-lg border border-gray-200 bg-white p-3">
      <input v-model="name" placeholder="Skill name" class="w-full rounded border border-gray-300 px-2 py-1 text-sm" />
      <input v-model="description" placeholder="Description" class="mt-2 w-full rounded border border-gray-300 px-2 py-1 text-sm" />
      <textarea v-model="instructions" placeholder="Instructions" rows="3" class="mt-2 w-full rounded border border-gray-300 px-2 py-1 text-sm" />
      <button class="mt-2 rounded bg-blue-600 px-3 py-1.5 text-sm text-white" @click="createSkill">Add Skill</button>
    </div>
    <div class="mt-4 grid grid-cols-2 gap-3">
      <SkillCard v-for="skill in skills.skills" :key="skill.id" :skill="skill" />
    </div>
  </div>
</template>
