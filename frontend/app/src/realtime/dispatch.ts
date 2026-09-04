import { useAgentsStore } from "../stores/agents"
import { useAttentionStore } from "../stores/attention"
import { useTasksStore } from "../stores/tasks"
import type { Agent, DecisionRequest, Task } from "../api/types"
import { connectRealtime, onEvent } from "./socket"

const AGENT_EVENTS = new Set(["agent.created", "agent.fired", "agent.status_changed"])
const TASK_EVENTS = new Set(["task.created", "task.assigned", "task.blocked", "task.completed"])

export function startRealtimeDispatch(): void {
  const agents = useAgentsStore()
  const tasks = useTasksStore()
  const attention = useAttentionStore()

  onEvent((envelope) => {
    if (AGENT_EVENTS.has(envelope.type)) agents.upsert(envelope.data as Agent)
    else if (TASK_EVENTS.has(envelope.type)) tasks.upsert(envelope.data as Task)
    else if (envelope.type === "decision.created") attention.receiveDecisionCreated(envelope.data as DecisionRequest)
    else if (envelope.type === "decision.answered") attention.receiveDecisionAnswered(envelope.data as DecisionRequest)
  })

  connectRealtime()
}
