<script setup lang="ts">
import { useTasksStore } from "../../stores/tasks"
import TaskCard from "./TaskCard.vue"
import type { Task } from "../../api/types"

const tasks = useTasksStore()

const columns: { status: Task["status"]; label: string }[] = [
  { status: "backlog", label: "Backlog" },
  { status: "in_progress", label: "In Progress" },
  { status: "blocked", label: "Blocked" },
  { status: "done", label: "Done" },
]
</script>

<template>
  <div class="grid grid-cols-4 gap-4 p-4">
    <div v-for="column in columns" :key="column.status">
      <h3 class="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-400">{{ column.label }}</h3>
      <div class="flex flex-col gap-2">
        <TaskCard v-for="task in tasks.byStatus(column.status)" :key="task.id" :task="task" />
      </div>
    </div>
  </div>
</template>
