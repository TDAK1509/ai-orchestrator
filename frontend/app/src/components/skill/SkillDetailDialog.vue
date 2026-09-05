<script setup lang="ts">
import { computed, ref } from "vue"
import type { Skill } from "../../api/types"
import { useSkillsStore } from "../../stores/skills"
import SkillRemovalWarning from "./SkillRemovalWarning.vue"

const props = defineProps<{ skill: Skill }>()
const emit = defineEmits<{ close: [] }>()

const skills = useSkillsStore()
const editing = ref(false)
const nameDraft = ref(props.skill.name)
const descriptionDraft = ref(props.skill.description ?? "")
const instructionsDraft = ref(props.skill.instructions)
const savingEdits = ref(false)
const editError = ref("")
const confirmingDelete = ref(false)
const isImported = computed(() => props.skill.source === "imported")

function startEditing(): void {
  nameDraft.value = props.skill.name
  descriptionDraft.value = props.skill.description ?? ""
  instructionsDraft.value = props.skill.instructions
  editError.value = ""
  editing.value = true
}

async function saveEdits(): Promise<void> {
  savingEdits.value = true
  editError.value = ""
  try {
    await skills.editSkill(props.skill.id, { name: nameDraft.value, description: descriptionDraft.value, instructions: instructionsDraft.value })
    editing.value = false
  } catch (err) {
    editError.value = err instanceof Error ? err.message : "Could not save, try again"
  } finally {
    savingEdits.value = false
  }
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
  emit("close")
}
</script>

<template>
  <div class="fixed inset-0 z-30 flex items-center justify-center bg-black/30">
    <div class="max-h-[80vh] w-[32rem] overflow-y-auto rounded-lg bg-white p-4 shadow-xl">
      <div class="flex items-start justify-between">
        <div class="flex items-center gap-2">
          <h2 class="text-lg font-semibold">{{ skill.name }}</h2>
          <span v-if="isImported" class="rounded bg-gray-100 px-1.5 py-0.5 text-xs text-gray-500">Imported from Claude Code</span>
        </div>
        <button class="text-gray-400 hover:text-gray-600" @click="$emit('close')">✕</button>
      </div>

      <div v-if="!editing">
        <p v-if="skill.description" class="mt-1 text-sm text-gray-500">{{ skill.description }}</p>
        <p class="mt-3 whitespace-pre-wrap rounded border border-gray-200 bg-gray-50 p-2 text-sm text-gray-700">{{ skill.instructions }}</p>
        <div class="mt-3 flex gap-2 text-sm">
          <button class="text-blue-600" @click="startEditing">Edit</button>
          <button class="text-red-600" @click="startDeleteConfirmation">Delete</button>
        </div>
      </div>
      <div v-else class="mt-2 space-y-1">
        <input v-model="nameDraft" placeholder="Name" class="w-full rounded border border-gray-300 px-2 py-1 text-sm" />
        <input v-model="descriptionDraft" placeholder="Description" class="w-full rounded border border-gray-300 px-2 py-1 text-sm" />
        <textarea v-model="instructionsDraft" rows="10" class="w-full rounded border border-gray-300 px-2 py-1 font-mono text-sm" />
        <p v-if="editError" class="text-sm text-red-600">{{ editError }}</p>
        <div class="mt-1 flex gap-2">
          <button
            class="rounded bg-blue-600 px-2 py-1 text-sm text-white disabled:opacity-50"
            :disabled="savingEdits || !nameDraft.trim() || !instructionsDraft.trim()"
            @click="saveEdits"
          >
            Save
          </button>
          <button class="rounded border border-gray-300 px-2 py-1 text-sm" @click="editing = false">Cancel</button>
        </div>
      </div>

      <div v-if="confirmingDelete" class="mt-3 rounded border border-red-200 bg-red-50 p-2 text-sm">
        <SkillRemovalWarning :agent-names="assignedAgents().map((a) => a.name)" />
        <div class="mt-2 flex gap-2">
          <button class="rounded bg-red-600 px-2 py-1 text-white" @click="confirmDelete">Delete Skill</button>
          <button class="rounded border border-gray-300 px-2 py-1" @click="confirmingDelete = false">Cancel</button>
        </div>
      </div>
    </div>
  </div>
</template>
