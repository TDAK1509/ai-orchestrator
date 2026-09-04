import { useAgentsStore } from "../stores/agents"
import { useAttentionStore } from "../stores/attention"
import { useActivityStore } from "../stores/activity"
import { useTasksStore } from "../stores/tasks"
import type { Agent, AttentionEvent, DecisionRequest, RuntimeEventPayload, Task } from "../api/types"
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
  const byType = { ...attentionHandlers(useAttentionStore()), ...activityHandlers(useActivityStore()) }

  return (envelope: { type: string; data: unknown }) => {
    if (AGENT_EVENTS.has(envelope.type)) agents.upsert(envelope.data as Agent)
    else if (TASK_EVENTS.has(envelope.type)) tasks.upsert(envelope.data as Task)
    else byType[envelope.type]?.(envelope.data)
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
