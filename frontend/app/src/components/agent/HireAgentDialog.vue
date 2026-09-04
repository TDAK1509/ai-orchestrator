<script setup lang="ts">
import { ref } from "vue"
import { useAgentsStore } from "../../stores/agents"

defineEmits<{ close: [] }>()

const agents = useAgentsStore()
const name = ref("")
const role = ref("")
const instructions = ref("")
const submitting = ref(false)

function canSubmit(): boolean {
  return Boolean(name.value && role.value)
}

async function submit(onDone: () => void): Promise<void> {
  if (!canSubmit()) return
  submitting.value = true
  try {
    await agents.hireAgent(name.value, role.value, instructions.value)
    onDone()
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="fixed inset-0 z-30 flex items-center justify-center bg-black/30">
    <div class="w-96 rounded-lg bg-white p-4 shadow-xl">
      <div class="flex items-center justify-between">
        <h2 class="text-lg font-semibold">Hire Agent</h2>
        <button class="text-gray-400 hover:text-gray-600" @click="$emit('close')">✕</button>
      </div>
      <label class="mt-3 block text-sm font-medium">Name</label>
      <input v-model="name" class="mt-1 w-full rounded border border-gray-300 px-2 py-1" />
      <label class="mt-3 block text-sm font-medium">Role</label>
      <input v-model="role" class="mt-1 w-full rounded border border-gray-300 px-2 py-1" />
      <label class="mt-3 block text-sm font-medium">Instructions</label>
      <textarea v-model="instructions" class="mt-1 w-full rounded border border-gray-300 px-2 py-1" rows="3" />
      <div class="mt-4 flex justify-end gap-2">
        <button class="rounded border border-gray-300 px-3 py-1.5 text-sm" @click="$emit('close')">Cancel</button>
        <button
          class="rounded bg-blue-600 px-3 py-1.5 text-sm text-white disabled:opacity-50"
          :disabled="!canSubmit() || submitting"
          @click="submit(() => $emit('close'))"
        >
          Hire Agent
        </button>
      </div>
    </div>
  </div>
</template>
