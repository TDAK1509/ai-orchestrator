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

export type MeetingStatus = "active" | "ended"

export interface Meeting {
  id: string
  room_id: string
  topic: string
  goal: string | null
  status: MeetingStatus
  ended_at: string | null
  summary: string | null
  decisions: string[]
  action_items: string[]
  unresolved_questions: string[]
  created_at: string
}

export interface MeetingMessage {
  id: string
  meeting_id: string
  agent_id: string
  content: string
  created_at: string
}

export type MemoryScope = "workspace" | "agent" | "task"
export type MemoryType = "fact" | "decision" | "preference" | "lesson" | "task_summary" | "project_context" | "convention" | "architecture"

export interface MemoryRecord {
  id: string
  scope: MemoryScope
  agent_id: string | null
  task_id: string | null
  type: MemoryType
  content: string
  importance: number
  pinned: boolean
  status: "active" | "superseded" | "archived"
  created_at: string
}

export interface McpServerRef {
  name: string
  transport: string
}

export interface AgentMcpPermission {
  id: string
  agent_id: string
  mcp_server_name: string
  allowed: boolean
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
