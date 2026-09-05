<script setup lang="ts">
import { computed, onMounted, ref } from "vue"
import SkillCard from "../components/skill/SkillCard.vue"
import type { SkillImportSummary } from "../api/types"
import { useSkillsStore } from "../stores/skills"

const skills = useSkillsStore()
const name = ref("")
const description = ref("")
const instructions = ref("")
const confirmingImport = ref(false)
const importSummary = ref<SkillImportSummary | null>(null)
const importedSkillCount = computed(() => skills.skills.filter((skill) => skill.source === "imported").length)

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

async function runImport(): Promise<void> {
  importSummary.value = await skills.importFromClaudeCode()
  confirmingImport.value = false
}
</script>

<template>
  <div class="p-4">
    <div class="flex items-center justify-between">
      <h2 class="text-xs font-semibold uppercase tracking-wide text-gray-400">Skill Catalog</h2>
      <button class="rounded border border-gray-300 px-2 py-1 text-xs" @click="confirmingImport = true">Sync from Claude Code</button>
    </div>
    <div v-if="confirmingImport" class="mt-2 rounded border border-amber-200 bg-amber-50 p-2 text-sm">
      <p v-if="importedSkillCount">{{ importedSkillCount }} imported skill(s) may be overwritten with the version from ~/.claude/skills.</p>
      <p v-else>Skills from ~/.claude/skills will be imported.</p>
      <div class="mt-2 flex gap-2">
        <button class="rounded bg-blue-600 px-2 py-1 text-white" @click="runImport">Sync</button>
        <button class="rounded border border-gray-300 px-2 py-1" @click="confirmingImport = false">Cancel</button>
      </div>
    </div>
    <div v-if="importSummary" class="mt-2 rounded border border-gray-200 bg-gray-50 p-2 text-sm text-gray-600">
      {{ importSummary.created.length }} created, {{ importSummary.updated.length }} updated,
      {{ importSummary.skipped.length }} skipped (custom skill owns that slug), {{ importSummary.errors.length }} errors.
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
