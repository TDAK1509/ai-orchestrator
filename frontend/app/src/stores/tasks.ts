import { defineStore } from "pinia"
import { api } from "../api/client"
import type { Task, TaskPriority } from "../api/types"

export const useTasksStore = defineStore("tasks", {
  state: () => ({
    tasks: [] as Task[],
  }),
  getters: {
    byId: (state) => (id: string) => state.tasks.find((task) => task.id === id),
    byStatus: (state) => (status: Task["status"]) => state.tasks.filter((task) => task.status === status),
  },
  actions: {
    async fetchTasks() {
      this.tasks = await api.get<Task[]>("/tasks")
    },
    async createTask(title: string, description: string | undefined, priority: TaskPriority, repositoryId: string | undefined) {
      const task = await api.post<Task>("/tasks", { title, description, priority, repository_id: repositoryId })
      this.upsert(task)
      return task
    },
    async assignTask(taskId: string, agentId: string) {
      const task = await api.post<Task>(`/tasks/${taskId}/assign`, { agent_id: agentId })
      this.upsert(task)
      return task
    },
    async editTask(taskId: string, patch: Partial<Pick<Task, "title" | "description" | "priority" | "repository_id">>) {
      const task = await api.patch<Task>(`/tasks/${taskId}`, patch)
      this.upsert(task)
      return task
    },
    async archiveTask(taskId: string) {
      const task = await api.post<Task>(`/tasks/${taskId}/archive`)
      this.upsert(task)
      return task
    },
    async retryTask(taskId: string) {
      const task = await api.post<Task>(`/tasks/${taskId}/retry`)
      this.upsert(task)
      return task
    },
    upsert(task: Task) {
      const index = this.tasks.findIndex((existing) => existing.id === task.id)
      if (index === -1) this.tasks.push(task)
      else this.tasks[index] = task
    },
  },
})
