import { defineStore } from "pinia"
import { api, pathSegment } from "../api/client"
import type { Agent, Team } from "../api/types"
import { useAgentsStore } from "./agents"

export const useTeamsStore = defineStore("teams", {
  state: () => ({
    teams: [] as Team[],
  }),
  getters: {
    byId: (state) => (id: string) => state.teams.find((team) => team.id === id),
  },
  actions: {
    async fetchTeams() {
      // allow-comment: agents already carry their own team_id (fetched once, globally, by useAgentsStore) -- deriving membership from that avoids one /teams/{id}/agents request per team here.
      this.teams = await api.get<Team[]>("/teams")
    },
    async createTeam(name: string, description: string) {
      const team = await api.post<Team>("/teams", { name, description })
      this.teams.push(team)
      return team
    },
    async assignAgent(teamId: string, agentId: string) {
      const agent = await api.post<Agent>(`/teams/${pathSegment(teamId)}/agents/${pathSegment(agentId)}`)
      useAgentsStore().upsert(agent)
    },
    async unassignAgent(teamId: string, agentId: string) {
      const agent = await api.delete<Agent>(`/teams/${pathSegment(teamId)}/agents/${pathSegment(agentId)}`)
      useAgentsStore().upsert(agent)
    },
    async archiveTeam(teamId: string) {
      await api.delete(`/teams/${pathSegment(teamId)}`)
      this.teams = this.teams.filter((team) => team.id !== teamId)
    },
  },
})
