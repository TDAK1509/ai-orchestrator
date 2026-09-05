<script setup lang="ts">
import { computed, onMounted, ref } from "vue"
import CreateSkillDialog from "../components/skill/CreateSkillDialog.vue"
import SkillDetailDialog from "../components/skill/SkillDetailDialog.vue"
import SkillRow from "../components/skill/SkillRow.vue"
import SyncSkillsDialog from "../components/skill/SyncSkillsDialog.vue"
import type { SkillImportSummary } from "../api/types"
import { useSkillsStore } from "../stores/skills"

const skills = useSkillsStore()
const showSyncDialog = ref(false)
const showCreateDialog = ref(false)
const detailSkillId = ref<string | null>(null)
const importSummary = ref<SkillImportSummary | null>(null)

const detailSkill = computed(() => skills.skills.find((skill) => skill.id === detailSkillId.value) ?? null)

onMounted(() => {
  skills.fetchSkills()
})

function onSynced(summary: SkillImportSummary): void {
  importSummary.value = summary
}
</script>

<template>
  <div class="p-4">
    <div class="flex items-center justify-between">
      <h2 class="text-xs font-semibold uppercase tracking-wide text-gray-400">Skill Catalog</h2>
      <div class="flex gap-2">
        <button class="rounded border border-gray-300 px-2 py-1 text-xs" @click="showSyncDialog = true">Sync from Claude Code</button>
        <button class="rounded bg-blue-600 px-2 py-1 text-xs text-white" @click="showCreateDialog = true">Add Skill</button>
      </div>
    </div>
    <SyncSkillsDialog v-if="showSyncDialog" @close="showSyncDialog = false" @synced="onSynced" />
    <CreateSkillDialog v-if="showCreateDialog" @close="showCreateDialog = false" />
    <div v-if="importSummary" class="mt-2 rounded border border-gray-200 bg-gray-50 p-2 text-sm text-gray-600">
      {{ importSummary.created.length }} created, {{ importSummary.updated.length }} updated,
      {{ importSummary.removed.length }} removed, {{ importSummary.skipped.length }} skipped (custom skill owns that slug),
      {{ importSummary.errors.length }} errors.
    </div>
    <div class="mt-4 flex flex-col gap-2">
      <SkillRow v-for="skill in skills.skills" :key="skill.id" :skill="skill" @click="detailSkillId = skill.id" />
    </div>
    <SkillDetailDialog v-if="detailSkill" :skill="detailSkill" @close="detailSkillId = null" />
  </div>
</template>
