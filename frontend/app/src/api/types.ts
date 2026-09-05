export type AgentStatus = "idle" | "queued" | "working" | "blocked"
export type AgentEffort = "low" | "medium" | "high" | "xhigh" | "max"

export interface Agent {
  id: string
  name: string
  role: string
  instructions: string
  model: string | null
  effort: AgentEffort | null
  status: AgentStatus
  needs_attention: boolean
  active: boolean
  room_id: string | null
  team_id: string | null
  current_task_id: string | null
  created_at: string
}

export type TaskStatus = "backlog" | "in_progress" | "blocked" | "done" | "archived"
export type TaskPriority = "low" | "medium" | "high"

export interface Task {
  id: string
  title: string
  description: string | null
  status: TaskStatus
  priority: TaskPriority
  assignee_id: string | null
  repository_id: string | null
  created_by_agent_id: string | null
  started_at: string | null
  completed_at: string | null
  created_at: string
}

export interface DirectoryEntry {
  name: string
  path: string
  is_directory: boolean
  is_git_repo: boolean
}

export interface Repository {
  id: string
  name: string
  path: string
  default_target_branch: string
  default_working_dir: string | null
  setup_script: string | null
  active: boolean
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

export type SkillSource = "imported" | "custom"

export interface SkillImportSummary {
  created: string[]
  updated: string[]
  removed: string[]
  unassigned: { slug: string; agents: string[] }[]
  skipped: string[]
  errors: string[]
}

export interface SkillAvailableEntry {
  slug: string
  name: string
  in_catalog: boolean
  on_disk: boolean
}

export interface Skill {
  id: string
  slug: string
  name: string
  description: string | null
  instructions: string
  source: SkillSource
  repository_path: string | null
  created_at: string
  updated_at: string | null
}

export interface Room {
  id: string
  name: string
  type: "main" | "meeting"
  created_at: string
}

export interface Team {
  id: string
  name: string
  description: string
  active: boolean
  created_at: string
}

export type MeetingStatus = "active" | "ended"
export type MeetingLoopState = "idle" | "running" | "paused"

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
  facilitator_instructions: string | null
  max_rounds: number
  chair_agent_id: string | null
  current_round: number
  next_speaker_id: string | null
  loop_state: MeetingLoopState
  created_at: string
}

export type MeetingAuthor = "human" | "agent" | "legacy_human_as_agent"

export interface MeetingMessage {
  id: string
  meeting_id: string
  agent_id: string | null
  content: string
  author: MeetingAuthor
  created_at: string
}

export type MemoryScope = "workspace" | "agent" | "team" | "task"
export type MemoryType = "fact" | "decision" | "preference" | "lesson" | "task_summary" | "project_context" | "convention" | "architecture"

export interface MemoryRecord {
  id: string
  scope: MemoryScope
  agent_id: string | null
  team_id: string | null
  task_id: string | null
  type: MemoryType
  content: string
  importance: number
  pinned: boolean
  status: "active" | "superseded" | "archived"
  created_at: string
}

export interface MemoryProposal {
  id: string
  old_memory_id: string
  new_memory_id: string
  similarity: number
  status: "pending" | "applied" | "dismissed"
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
