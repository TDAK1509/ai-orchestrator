import { defineStore } from "pinia"
import { api } from "../api/client"
import type { Repository } from "../api/types"

export const useRepositoriesStore = defineStore("repositories", {
  state: () => ({
    repositories: [] as Repository[],
  }),
  getters: {
    byId: (state) => (id: string) => state.repositories.find((repository) => repository.id === id),
  },
  actions: {
    async fetchRepositories() {
      this.repositories = await api.get<Repository[]>("/repositories")
    },
    async createRepository(path: string, name: string | undefined, defaultTargetBranch: string) {
      const repository = await api.post<Repository>("/repositories", { path, name, default_target_branch: defaultTargetBranch })
      this.repositories.push(repository)
      return repository
    },
  },
})
