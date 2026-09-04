import { defineStore } from "pinia"
import { api, pathSegment } from "../api/client"
import type { Agent, Team } from "../api/types"

export const useTeamsStore = defineStore("teams", {
  state: () => ({
    teams: [] as Team[],
    agentsByTeamId: {} as Record<string, Agent[]>,
  }),
  getters: {
    byId: (state) => (id: string) => state.teams.find((team) => team.id === id),
  },
  actions: {
    async fetchTeams() {
      this.teams = await api.get<Team[]>("/teams")
      await Promise.all(this.teams.map((team) => this.fetchTeamAgents(team.id)))
    },
    async fetchTeamAgents(teamId: string) {
      this.agentsByTeamId[teamId] = await api.get<Agent[]>(`/teams/${pathSegment(teamId)}/agents`)
    },
    async createTeam(name: string, description: string) {
      const team = await api.post<Team>("/teams", { name, description })
      this.teams.push(team)
      return team
    },
    async assignAgent(teamId: string, agentId: string) {
      await api.post(`/teams/${pathSegment(teamId)}/agents/${pathSegment(agentId)}`)
      await this.fetchTeamAgents(teamId)
    },
    async unassignAgent(teamId: string, agentId: string) {
      await api.delete(`/teams/${pathSegment(teamId)}/agents/${pathSegment(agentId)}`)
      await this.fetchTeamAgents(teamId)
    },
    async archiveTeam(teamId: string) {
      await api.delete(`/teams/${pathSegment(teamId)}`)
      this.teams = this.teams.filter((team) => team.id !== teamId)
      delete this.agentsByTeamId[teamId]
    },
  },
})
