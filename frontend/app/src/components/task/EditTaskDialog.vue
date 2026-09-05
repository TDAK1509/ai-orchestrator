<script setup lang="ts">
import { ref } from "vue"
import type { Task, TaskPriority } from "../../api/types"
import { useRepositoriesStore } from "../../stores/repositories"
import { useTasksStore } from "../../stores/tasks"

const props = defineProps<{ task: Task }>()
const emit = defineEmits<{ close: [] }>()

const tasks = useTasksStore()
const repositories = useRepositoriesStore()
const title = ref(props.task.title)
const description = ref(props.task.description ?? "")
const priority = ref<TaskPriority>(props.task.priority)
const repositoryId = ref(props.task.repository_id ?? "")
const submitting = ref(false)
const error = ref("")

async function submit(): Promise<void> {
  if (!title.value || !repositoryId.value) return
  submitting.value = true
  error.value = ""
  try {
    await tasks.editTask(props.task.id, {
      title: title.value,
      description: description.value || null,
      priority: priority.value,
      repository_id: repositoryId.value,
    })
    emit("close")
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Failed to save task"
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="fixed inset-0 z-30 flex items-center justify-center bg-black/30">
    <div class="w-96 rounded-lg bg-white p-4 shadow-xl">
      <div class="flex items-center justify-between">
        <h2 class="text-lg font-semibold">Edit Task</h2>
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
      <label class="mt-3 block text-sm font-medium">Repository</label>
      <select v-model="repositoryId" class="mt-1 w-full rounded border border-gray-300 px-2 py-1">
        <option value="" disabled>Select a repository...</option>
        <option v-for="repository in repositories.repositories" :key="repository.id" :value="repository.id">
          {{ repository.name }}
        </option>
      </select>
      <p v-if="error" class="mt-2 text-sm text-red-600">{{ error }}</p>
      <div class="mt-4 flex justify-end gap-2">
        <button class="rounded border border-gray-300 px-3 py-1.5 text-sm" @click="$emit('close')">Cancel</button>
        <button
          class="rounded bg-blue-600 px-3 py-1.5 text-sm text-white disabled:opacity-50"
          :disabled="!title || !repositoryId || submitting"
          @click="submit"
        >
          Save
        </button>
      </div>
    </div>
  </div>
</template>
