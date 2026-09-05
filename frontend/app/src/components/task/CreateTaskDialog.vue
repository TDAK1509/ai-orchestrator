<script setup lang="ts">
import { ref } from "vue"
import type { TaskPriority } from "../../api/types"
import { useRepositoriesStore } from "../../stores/repositories"
import { useTasksStore } from "../../stores/tasks"
import RegisterRepositoryDialog from "./RegisterRepositoryDialog.vue"

defineEmits<{ close: [] }>()

const tasks = useTasksStore()
const repositories = useRepositoriesStore()
const title = ref("")
const description = ref("")
const priority = ref<TaskPriority>("medium")
const repositoryId = ref("")
const submitting = ref(false)
const showRegisterRepository = ref(false)

async function submit(onDone: () => void): Promise<void> {
  if (!title.value) return
  submitting.value = true
  try {
    await tasks.createTask(title.value, description.value || undefined, priority.value, repositoryId.value || undefined)
    onDone()
  } finally {
    submitting.value = false
  }
}

function onRepositoryRegistered(newRepositoryId: string): void {
  repositoryId.value = newRepositoryId
  showRegisterRepository.value = false
}
</script>

<template>
  <div class="fixed inset-0 z-30 flex items-center justify-center bg-black/30">
    <div class="w-96 rounded-lg bg-white p-4 shadow-xl">
      <div class="flex items-center justify-between">
        <h2 class="text-lg font-semibold">Create Task</h2>
        <button class="text-gray-400 hover:text-gray-600" @click="$emit('close')">✕</button>
      </div>
      <label class="mt-3 block text-sm font-medium">Title</label>
      <input v-model="title" class="mt-1 w-full rounded border border-gray-300 px-2 py-1" />
      <label class="mt-3 block text-sm font-medium">Description</label>
      <textarea v-model="description" class="mt-1 w-full rounded border border-gray-300 px-2 py-1" rows="3" />
      <label class="mt-3 block text-sm font-medium">Priority</label>
      <select v-model="priority" class="mt-1 w-full rounded border border-gray-300 px-2 py-1">
        <option value="low">Low</option>
        <option value="medium">Medium</option>
        <option value="high">High</option>
      </select>
      <label class="mt-3 flex items-center justify-between text-sm font-medium">
        Repository
        <button type="button" class="text-xs font-normal text-blue-600" @click="showRegisterRepository = true">+ Register a repository</button>
      </label>
      <select v-model="repositoryId" class="mt-1 w-full rounded border border-gray-300 px-2 py-1">
        <option value="">Workspace default</option>
        <option v-for="repository in repositories.repositories" :key="repository.id" :value="repository.id">
          {{ repository.name }}
        </option>
      </select>
      <div class="mt-4 flex justify-end gap-2">
        <button class="rounded border border-gray-300 px-3 py-1.5 text-sm" @click="$emit('close')">Cancel</button>
        <button
          class="rounded bg-blue-600 px-3 py-1.5 text-sm text-white disabled:opacity-50"
          :disabled="!title || submitting"
          @click="submit(() => $emit('close'))"
        >
          Create Task
        </button>
      </div>
    </div>
    <RegisterRepositoryDialog v-if="showRegisterRepository" @close="showRegisterRepository = false" @registered="onRepositoryRegistered" />
  </div>
</template>
