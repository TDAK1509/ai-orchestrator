<script setup lang="ts">
import { ref } from "vue"
import { useSkillsStore } from "../../stores/skills"

const emit = defineEmits<{ close: [] }>()

const skills = useSkillsStore()
const name = ref("")
const description = ref("")
const instructions = ref("")
const saving = ref(false)
const error = ref("")

async function submit(): Promise<void> {
  if (!name.value || !instructions.value) return
  saving.value = true
  error.value = ""
  try {
    await skills.createSkill(name.value, description.value || undefined, instructions.value)
    emit("close")
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Could not create skill, try again"
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="fixed inset-0 z-30 flex items-center justify-center bg-black/30">
    <div class="w-96 rounded-lg bg-white p-4 shadow-xl">
      <div class="flex items-center justify-between">
        <h2 class="text-lg font-semibold">Add Skill</h2>
        <button class="text-gray-400 hover:text-gray-600" @click="$emit('close')">✕</button>
      </div>
      <input v-model="name" placeholder="Skill name" class="mt-3 w-full rounded border border-gray-300 px-2 py-1 text-sm" />
      <input v-model="description" placeholder="Description" class="mt-2 w-full rounded border border-gray-300 px-2 py-1 text-sm" />
      <textarea v-model="instructions" placeholder="Instructions" rows="6" class="mt-2 w-full rounded border border-gray-300 px-2 py-1 text-sm" />
      <p v-if="error" class="mt-2 text-sm text-red-600">{{ error }}</p>
      <div class="mt-3 flex justify-end gap-2">
        <button class="rounded border border-gray-300 px-3 py-1.5 text-sm" :disabled="saving" @click="$emit('close')">Cancel</button>
        <button
          class="rounded bg-blue-600 px-3 py-1.5 text-sm text-white disabled:opacity-50"
          :disabled="!name || !instructions || saving"
          @click="submit"
        >
          {{ saving ? "Adding..." : "Add Skill" }}
        </button>
      </div>
    </div>
  </div>
</template>
