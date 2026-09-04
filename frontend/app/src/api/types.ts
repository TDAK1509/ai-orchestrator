export type AgentStatus = "idle" | "queued" | "working" | "blocked"

export interface Agent {
  id: string
  name: string
  role: string
  instructions: string
  status: AgentStatus
  needs_attention: boolean
  active: boolean
  room_id: string | null
  current_task_id: string | null
  created_at: string
}

export type TaskStatus = "backlog" | "in_progress" | "blocked" | "done"
export type TaskPriority = "low" | "medium" | "high"

export interface Task {
  id: string
  title: string
  description: string | null
  status: TaskStatus
  priority: TaskPriority
  assignee_id: string | null
  started_at: string | null
  completed_at: string | null
  created_at: string
}

export interface DecisionOption {
  id?: string
  label: string
  description?: string
}

export type DecisionStatus = "pending" | "answered" | "cancelled"

export interface DecisionRequest {
  id: string
  agent_id: string
  task_id: string | null
  question: string
  options: DecisionOption[] | null
  allow_custom_answer: boolean
  status: DecisionStatus
  answer: string | null
  created_at: string
  answered_at: string | null
}

export type AttentionType = "decision_required" | "permission_required" | "agent_blocked" | "task_failed" | "agent_question"

export interface AttentionEvent {
  id: string
  type: AttentionType
  agent_id: string | null
  task_id: string | null
  decision_request_id: string | null
  title: string
  message: string
  resolved: boolean
  created_at: string
  resolved_at: string | null
}

export interface Skill {
  id: string
  slug: string
  name: string
  description: string | null
  instructions: string
  created_at: string
  updated_at: string | null
}

export interface Room {
  id: string
  name: string
  type: "main" | "meeting"
  created_at: string
}

export interface RuntimeEventPayload {
  agentId: string
  taskId: string
  runId: string
  kind: string
  text: string | null
  toolName: string | null
  filePath: string | null
  exitResult: string | null
}

export interface EventEnvelope<T = unknown> {
  type: string
  data: T
}
