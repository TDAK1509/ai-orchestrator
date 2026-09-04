import { useAgentsStore } from "../stores/agents"
import { useAttentionStore } from "../stores/attention"
import { useActivityStore } from "../stores/activity"
import { useMcpStore } from "../stores/mcp"
import { useMeetingsStore } from "../stores/meetings"
import { useMemoryStore } from "../stores/memory"
import { useRoomsStore } from "../stores/rooms"
import { useSkillsStore } from "../stores/skills"
import { useTasksStore } from "../stores/tasks"
import type { Agent, AttentionEvent, DecisionRequest, Meeting, MeetingMessage, MemoryRecord, RuntimeEventPayload, Skill, Task } from "../api/types"
import { connectRealtime, onEvent, onOpen } from "./socket"

const AGENT_EVENTS = new Set(["agent.created", "agent.fired", "agent.status_changed"])
const TASK_EVENTS = new Set(["task.created", "task.assigned", "task.blocked", "task.completed", "task.updated"])

export function startRealtimeDispatch(loadSnapshots: () => Promise<void>): void {
  const route = buildRouter()
  const buffer = createEventBuffer(route)

  onEvent(buffer.handle)
  onOpen(() => resync(loadSnapshots, buffer))
  connectRealtime()
}

async function resync(loadSnapshots: () => Promise<void>, buffer: ReturnType<typeof createEventBuffer>): Promise<void> {
  buffer.pause()
  await loadSnapshots()
  buffer.resume()
}

function createEventBuffer(route: (envelope: { type: string; data: unknown }) => void) {
  let paused = false
  let pending: { type: string; data: unknown }[] = []
  return {
    pause: () => {
      paused = true
      pending = []
    },
    resume: () => {
      paused = false
      const queued = pending
      pending = []
      for (const envelope of queued) route(envelope)
    },
    handle: (envelope: { type: string; data: unknown }) => {
      if (paused) pending.push(envelope)
      else route(envelope)
    },
  }
}

type EnvelopeHandler = (data: unknown) => void

function buildRouter() {
  const agents = useAgentsStore()
  const tasks = useTasksStore()
  const byType = buildByTypeHandlers()

  return (envelope: { type: string; data: unknown }) => {
    if (AGENT_EVENTS.has(envelope.type)) agents.upsert(envelope.data as Agent)
    else if (TASK_EVENTS.has(envelope.type)) tasks.upsert(envelope.data as Task)
    else byType[envelope.type]?.(envelope.data)
  }
}

function buildByTypeHandlers(): Record<string, EnvelopeHandler> {
  return {
    ...attentionHandlers(useAttentionStore()),
    ...activityHandlers(useActivityStore()),
    ...meetingHandlers(useMeetingsStore()),
    ...skillHandlers(useSkillsStore()),
    ...mcpHandlers(useMcpStore()),
    "memory.created": (data) => useMemoryStore().receiveMemoryCreated(data as MemoryRecord),
  }
}

function attentionHandlers(attention: ReturnType<typeof useAttentionStore>): Record<string, EnvelopeHandler> {
  return {
    "decision.created": (data) => attention.receiveDecisionCreated(data as DecisionRequest),
    "decision.answered": (data) => attention.receiveDecisionAnswered(data as DecisionRequest),
    "attention.created": (data) => attention.receiveAttentionCreated(data as AttentionEvent),
    "attention.resolved": (data) => attention.receiveAttentionResolved(data as AttentionEvent),
  }
}

function activityHandlers(activity: ReturnType<typeof useActivityStore>): Record<string, EnvelopeHandler> {
  return {
    "runtime.event": (data) => activity.receiveRuntimeEvent(data as RuntimeEventPayload),
  }
}

function meetingHandlers(meetings: ReturnType<typeof useMeetingsStore>): Record<string, EnvelopeHandler> {
  return {
    "meeting.created": (data) => receiveMeetingChange(meetings, data as Meeting),
    "meeting.ended": (data) => receiveMeetingChange(meetings, data as Meeting),
    "meeting.updated": (data) => meetings.upsertMeeting(data as Meeting),
    "meeting.message": (data) => meetings.receiveMessage(data as MeetingMessage),
  }
}

function receiveMeetingChange(meetings: ReturnType<typeof useMeetingsStore>, meeting: Meeting): void {
  meetings.upsertMeeting(meeting)
  useRoomsStore().fetchRooms()
}

function skillHandlers(skills: ReturnType<typeof useSkillsStore>): Record<string, EnvelopeHandler> {
  return {
    "skill.created": (data) => skills.fetchSkill((data as Skill).id),
    "skill.updated": (data) => skills.fetchSkill((data as Skill).id),
    "skill.deleted": (data) => skills.removeById((data as Skill).id),
  }
}

function mcpHandlers(mcp: ReturnType<typeof useMcpStore>): Record<string, EnvelopeHandler> {
  return {
    "agent.mcp_granted": (data) => mcp.receivePermissionChange((data as { agent_id: string }).agent_id),
    "agent.mcp_revoked": (data) => mcp.receivePermissionChange((data as { agent_id: string }).agent_id),
  }
}
