import { defineStore } from "pinia"
import { api, pathSegment } from "../api/client"
import type { Agent, Skill } from "../api/types"

export const useSkillsStore = defineStore("skills", {
  state: () => ({
    skills: [] as Skill[],
    assignedAgentsBySkillId: {} as Record<string, Agent[]>,
  }),
  actions: {
    async fetchSkills() {
      this.skills = await api.get<Skill[]>("/skills")
    },
    async fetchSkill(id: string) {
      this.upsert(await api.get<Skill>(`/skills/${pathSegment(id)}`))
    },
    async fetchAssignedAgents(id: string) {
      this.assignedAgentsBySkillId[id] = await api.get<Agent[]>(`/skills/${pathSegment(id)}/agents`)
      return this.assignedAgentsBySkillId[id]
    },
    async createSkill(name: string, description: string | undefined, instructions: string) {
      const skill = await api.post<Skill>("/skills", { name, description, instructions })
      this.upsert(skill)
      return skill
    },
    async editSkill(id: string, patch: Partial<Pick<Skill, "name" | "description" | "instructions">>) {
      const skill = await api.patch<Skill>(`/skills/${pathSegment(id)}`, patch)
      this.upsert(skill)
      return skill
    },
    async deleteSkill(id: string) {
      await api.delete(`/skills/${pathSegment(id)}`)
      this.removeById(id)
    },
    async assignToAgent(skillId: string, agentId: string) {
      await api.post(`/skills/${pathSegment(skillId)}/assign/${pathSegment(agentId)}`)
    },
    async unassignFromAgent(skillId: string, agentId: string) {
      await api.delete(`/skills/${pathSegment(skillId)}/assign/${pathSegment(agentId)}`)
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
