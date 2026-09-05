<script setup lang="ts">
import { ref } from "vue"
import { useTasksStore } from "../../stores/tasks"
import TaskCard from "./TaskCard.vue"
import type { Task } from "../../api/types"

const tasks = useTasksStore()
const selected = ref<Set<string>>(new Set())

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
  await tasks.bulkArchive([...selected.value])
  selected.value.clear()
}
</script>

<template>
  <div class="p-4">
    <div v-if="selected.size > 0" class="mb-3 flex items-center gap-3 rounded border border-gray-200 bg-gray-50 px-3 py-2 text-sm">
      <span>{{ selected.size }} selected</span>
      <button class="rounded bg-red-600 px-2 py-1 text-xs text-white" @click="archiveSelected">Archive selected</button>
      <button class="text-xs text-gray-500" @click="selected.clear()">Clear</button>
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
