<script setup lang="ts">
import { ref } from "vue"
import { useTasksStore } from "../../stores/tasks"
import TaskCard from "./TaskCard.vue"
import type { Task } from "../../api/types"

const tasks = useTasksStore()
const selected = ref<Set<string>>(new Set())
const confirmingBulkArchive = ref(false)
const archiving = ref(false)
const bulkArchiveError = ref("")

const columns: { status: Task["status"]; label: string }[] = [
  { status: "backlog", label: "Backlog" },
  { status: "in_progress", label: "In Progress" },
  { status: "blocked", label: "Blocked" },
  { status: "done", label: "Done" },
]

function toggleSelection(taskId: string): void {
  if (selected.value.has(taskId)) selected.value.delete(taskId)
  else selected.value.add(taskId)
}

async function archiveSelected(): Promise<void> {
  archiving.value = true
  bulkArchiveError.value = ""
  try {
    const failedTaskIds = await tasks.bulkArchive([...selected.value])
    selected.value = new Set(failedTaskIds)
    if (failedTaskIds.length > 0) bulkArchiveError.value = `${failedTaskIds.length} task(s) could not be archived; they stay selected.`
  } finally {
    archiving.value = false
    confirmingBulkArchive.value = false
  }
}
</script>

<template>
  <div class="p-4">
    <div v-if="selected.size > 0" class="mb-3 flex flex-col gap-2 rounded border border-gray-200 bg-gray-50 px-3 py-2 text-sm">
      <div class="flex items-center gap-3">
        <span>{{ selected.size }} selected</span>
        <button class="rounded bg-red-600 px-2 py-1 text-xs text-white" @click="confirmingBulkArchive = true">Archive selected</button>
        <button class="text-xs text-gray-500" @click="selected.clear()">Clear</button>
      </div>
      <div v-if="confirmingBulkArchive" class="rounded border border-red-200 bg-red-50 p-2 text-xs">
        <p>Archive {{ selected.size }} task(s)? Any uncommitted work in their worktrees is discarded.</p>
        <div class="mt-2 flex gap-2">
          <button class="rounded bg-red-600 px-2 py-1 text-white disabled:opacity-50" :disabled="archiving" @click="archiveSelected">
            {{ archiving ? "Archiving..." : "Archive" }}
          </button>
          <button class="rounded border border-gray-300 px-2 py-1" :disabled="archiving" @click="confirmingBulkArchive = false">Cancel</button>
        </div>
      </div>
      <p v-if="bulkArchiveError" class="text-xs text-red-600">{{ bulkArchiveError }}</p>
    </div>
    <div class="grid grid-cols-4 gap-4">
      <div v-for="column in columns" :key="column.status">
        <h3 class="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-400">{{ column.label }}</h3>
        <div class="flex flex-col gap-2">
          <TaskCard
            v-for="task in tasks.byStatus(column.status)"
            :key="task.id"
            :task="task"
            :selected="selected.has(task.id)"
            @toggle="toggleSelection(task.id)"
          />
        </div>
      </div>
    </div>
  </div>
</template>
