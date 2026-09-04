"""Event type names, matching README 24. Shared between publishers and the /ws router."""

AGENT_CREATED = "agent.created"
AGENT_FIRED = "agent.fired"
AGENT_STATUS_CHANGED = "agent.status_changed"

TASK_CREATED = "task.created"
TASK_ASSIGNED = "task.assigned"
TASK_BLOCKED = "task.blocked"
TASK_COMPLETED = "task.completed"
TASK_UPDATED = "task.updated"

RUNTIME_EVENT = "runtime.event"

DECISION_CREATED = "decision.created"
DECISION_ANSWERED = "decision.answered"

ATTENTION_CREATED = "attention.created"
ATTENTION_RESOLVED = "attention.resolved"

MEETING_CREATED = "meeting.created"
MEETING_MESSAGE = "meeting.message"
MEETING_ENDED = "meeting.ended"
MEETING_UPDATED = "meeting.updated"

SKILL_CREATED = "skill.created"
SKILL_UPDATED = "skill.updated"
SKILL_DELETED = "skill.deleted"

MEMORY_CREATED = "memory.created"

MCP_GRANTED = "agent.mcp_granted"
MCP_REVOKED = "agent.mcp_revoked"
