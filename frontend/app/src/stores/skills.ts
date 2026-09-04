import { defineStore } from "pinia"
import { api } from "../api/client"
import type { Skill } from "../api/types"

export const useSkillsStore = defineStore("skills", {
  state: () => ({
    skills: [] as Skill[],
  }),
  actions: {
    async fetchSkills() {
      this.skills = await api.get<Skill[]>("/skills")
    },
    async createSkill(name: string, description: string | undefined, instructions: string) {
      const skill = await api.post<Skill>("/skills", { name, description, instructions })
      this.upsert(skill)
      return skill
    },
    async editSkill(id: string, patch: Partial<Pick<Skill, "name" | "description" | "instructions">>) {
      const skill = await api.patch<Skill>(`/skills/${id}`, patch)
      this.upsert(skill)
      return skill
    },
    async deleteSkill(id: string) {
      await api.delete(`/skills/${id}`)
      this.removeById(id)
    },
    async assignToAgent(skillId: string, agentId: string) {
      await api.post(`/skills/${skillId}/assign/${agentId}`)
    },
    async unassignFromAgent(skillId: string, agentId: string) {
      await api.delete(`/skills/${skillId}/assign/${agentId}`)
    },
    upsert(skill: Skill) {
      const index = this.skills.findIndex((existing) => existing.id === skill.id)
      if (index === -1) this.skills.push(skill)
      else this.skills[index] = skill
    },
    removeById(id: string) {
      this.skills = this.skills.filter((skill) => skill.id !== id)
    },
  },
})
