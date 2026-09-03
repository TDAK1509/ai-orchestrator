# Agent Office — UI / Product Specification

## Goal

Build a web interface for managing multiple Claude Code agents as if they are people working in a shared office.

The interface should make it easy to:

- See all agents and their current status.
- See which room each agent is currently in.
- Create meetings with selected agents.
- Hire/create a new agent.
- Fire/remove an agent safely.
- Maintain a repository-backed global **Skill Catalog** from the UI.
- Assign selected skills from that catalog to each agent.
- Maintain a global pool of **MCP servers** from the UI.
- Control which MCP servers each agent is allowed to use.
- Maintain private persistent memory for each agent.
- Maintain a global **Workspace Memory** automatically available to all current and future agents.
- Create and manage tasks in a Kanban board.
- Assign tasks to agents.
- Automatically move an assigned task from **Backlog** to **In Progress**.
- See what an agent is currently doing by clicking the agent.
- Respond to questions/decision requests from Claude inside the agent side sheet.
- Get a visible notification ping when an agent needs human attention.
- Toggle notification sounds on/off.

---

# 1. Main Layout

The app has three persistent areas:

1. **Top action header**
2. **Left agent sidebar**
3. **Main workspace**

The main workspace can switch between:

- **Rooms**
- **Tasks**
- **Skills**
- **MCP Servers**
- **Workspace Memory**

## Main Layout Mock-up

```text
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ AGENT OFFICE                                              🔔 2   🔊 On   [+ Task] [+ Meeting] [+ Hire Agent] │
├───────────────────────────────┬─────────────────────────────────────────────────────────────────────────┤
│                               │                                                                         │
│ AGENTS                        │  [ Rooms ] [ Tasks ] [ Skills ] [ MCP ] [ Workspace Memory ]            │
│                               │                                                                         │
│ ┌───────────────────────────┐ │                                                                         │
│ │ ● Alex                    │ │                                                                         │
│ │ Backend Engineer          │ │                    MAIN WORKSPACE                                       │
│ │ WORKING                   │ │                                                                         │
│ │ Fix token rotation        │ │                                                                         │
│ └───────────────────────────┘ │                                                                         │
│                               │                                                                         │
│ ┌───────────────────────────┐ │                                                                         │
│ │ ○ Maya                    │ │                                                                         │
│ │ Frontend Engineer         │ │                                                                         │
│ │ IDLE                      │ │                                                                         │
│ └───────────────────────────┘ │                                                                         │
│                               │                                                                         │
│ ┌───────────────────────────┐ │                                                                         │
│ │ ! Sam                     │ │                                                                         │
│ │ Reviewer                  │ │                                                                         │
│ │ BLOCKED                   │ │                                                                         │
│ │ Needs your decision       │ │                                                                         │
│ └───────────────────────────┘ │                                                                         │
│                               │                                                                         │
├───────────────────────────────┴─────────────────────────────────────────────────────────────────────────┤
│                                                                                                         │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

# 2. Header

The header contains the main global actions.

```text
┌───────────────────────────────────────────────────────────────────────────────────────────┐
│ AGENT OFFICE                                      🔔 2    🔊 On    [+ Task] [+ Meeting] [+ Agent] │
└───────────────────────────────────────────────────────────────────────────────────────────┘
```

## Actions

### `+ Task`

Opens the **Create Task** dialog.

### `+ Meeting`

Opens the **Create Meeting** dialog.

### `+ Hire Agent`

Opens the **Hire Agent** dialog.

Agent firing is intentionally not a global header action. It lives inside the selected agent's detail sheet so destructive actions stay contextual.

### Notification indicator

Example:

```text
🔔 2
```

The number represents unresolved items that need the user's attention.

Examples:

- Agent asks a question.
- Agent requires a decision.
- Agent is blocked.
- Task failed.
- Agent needs permission.
- Meeting is waiting for the user.

Clicking the notification indicator opens an attention inbox/dropdown.

### Sound toggle

```text
🔊 On
🔇 Off
```

Sound preference should persist locally for the user.

When enabled, play a short notification sound when a **new attention-required event** arrives.

Do not repeatedly play sound for the same unresolved event.

---

# 3. Agent Sidebar

The left sidebar always shows all agents.

Each agent is displayed as a card.

## Agent Card

```text
┌───────────────────────────┐
│ ● Alex                    │
│ Backend Engineer          │
│ WORKING                   │
│ Fix token rotation        │
└───────────────────────────┘
```

Idle:

```text
┌───────────────────────────┐
│ ○ Maya                    │
│ Frontend Engineer         │
│ IDLE                      │
└───────────────────────────┘
```

Blocked:

```text
┌───────────────────────────┐
│ ! Sam                     │
│ Code Reviewer             │
│ BLOCKED                   │
│ Needs your decision       │
└───────────────────────────┘
```

## Agent statuses

Use these core statuses:

```text
idle
working
blocked
```

Do **not** use "in meeting" as an agent status.

Room/location should be a separate property.

Example:

```ts
agent.status = "working"
agent.roomId = "meeting_auth_architecture"
```

## Suggested agent data shape

```ts
type AgentStatus = "idle" | "working" | "blocked"

interface Agent {
  id: string
  name: string
  role: string

  status: AgentStatus

  currentTaskId?: string
  roomId: string

  needsAttention: boolean
}
```

## Clicking an agent

Clicking any agent card opens the **Agent Detail Sheet** from the right side.

---

# 4. Agent Detail Side Sheet

The sheet slides in from the right and overlays part of the current view.

The user should not need to navigate away from Rooms or Tasks.

## Mock-up

```text
                                              ┌─────────────────────────────────────────────┐
                                              │ Alex                              [×]       │
                                              │ Backend Engineer                            │
                                              │                                             │
                                              │ ● WORKING                                   │
                                              │ Main Room                                   │
                                              │                                             │
                                              │ ──────────────────────────────────────────  │
                                              │ CURRENT TASK                                │
                                              │                                             │
                                              │ Fix refresh-token rotation                  │
                                              │ TASK-142                                    │
                                              │                                             │
                                              │ Implementing token-family revocation.        │
                                              │                                             │
                                              │ Files                                       │
                                              │ • apps/api/src/auth/token.ts                 │
                                              │ • apps/api/tests/auth.test.ts                │
                                              │                                             │
                                              │ Last activity: 18 sec ago                    │
                                              │                                             │
                                              │ ──────────────────────────────────────────  │
                                              │ ACTIVITY                                    │
                                              │                                             │
                                              │ ✓ Inspected auth middleware                  │
                                              │ ✓ Added rotation handling                    │
                                              │ ● Running tests                              │
                                              │ ○ Update integration tests                   │
                                              │                                             │
                                              │ ──────────────────────────────────────────  │
                                              │ AGENT MESSAGE                               │
                                              │                                             │
                                              │ "I'm checking whether existing sessions      │
                                              │ need migration before changing this."        │
                                              │                                             │
                                              └─────────────────────────────────────────────┘
```

The sheet should support these sections:

- Agent identity
- Status
- Current room
- Current assigned task
- Current task description
- Current activity/progress
- Recent agent messages
- Files currently being touched, when known
- Decision requests
- Blockers
- Recent completed tasks

---

# 5. Decision Requests

When Claude needs a human decision, the request appears directly in the agent side sheet.

The agent becomes:

```text
status = blocked
needsAttention = true
```

Example agent card:

```text
┌───────────────────────────┐
│ ! Alex                    │
│ Backend Engineer          │
│ BLOCKED                   │
│ Waiting for your decision │
└───────────────────────────┘
```

## Decision UI

```text
                                              ┌─────────────────────────────────────────────┐
                                              │ Alex                              [×]       │
                                              │ Backend Engineer                            │
                                              │                                             │
                                              │ ! BLOCKED                                   │
                                              │                                             │
                                              │ ──────────────────────────────────────────  │
                                              │ DECISION NEEDED                             │
                                              │                                             │
                                              │ Existing users currently have refresh       │
                                              │ tokens in localStorage. How should I handle  │
                                              │ the migration?                              │
                                              │                                             │
                                              │ ○ Force everyone to log in again             │
                                              │                                             │
                                              │ ○ Add temporary backwards compatibility      │
                                              │                                             │
                                              │ ○ Do not migrate existing sessions           │
                                              │                                             │
                                              │ [Write another answer...]                    │
                                              │                                             │
                                              │                            [Submit Decision] │
                                              │                                             │
                                              └─────────────────────────────────────────────┘
```

Claude may provide:

- Multiple-choice decisions.
- Yes/no approval.
- Free-form question.
- Permission request.

Suggested representation:

```ts
interface DecisionRequest {
  id: string
  agentId: string
  taskId?: string

  question: string

  options?: {
    id: string
    label: string
    description?: string
  }[]

  allowCustomAnswer: boolean

  status: "pending" | "answered"
  answer?: string

  createdAt: string
  answeredAt?: string
}
```

After submitting:

1. Send the response to the corresponding Claude Code session.
2. Mark the decision request as answered.
3. Remove `needsAttention` if no other request is pending.
4. Change agent status from `blocked` back to `working`.
5. Resume the agent's task.

---

# 6. Rooms View

Rooms are virtual spaces containing agents.

There is always one default room:

```text
Main Room
```

Unless an agent is in another meeting, they belong to the Main Room.

## Default Rooms View

```text
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│ ROOMS                                                                                       │
│                                                                                             │
│ ┌─────────────────────────────────────────────────────────────────────────────────────────┐ │
│ │ 🏢 MAIN ROOM                                                               5 agents    │ │
│ ├─────────────────────────────────────────────────────────────────────────────────────────┤ │
│ │                                                                                         │ │
│ │   Alex               Maya               Sam                Jordan          Emma         │ │
│ │   Backend            Frontend           Reviewer           DevOps          Product      │ │
│ │   ● Working          ○ Idle             ○ Idle             ○ Idle          ○ Idle       │ │
│ │                                                                                         │ │
│ │ ──────────────────────────────────────────────────────────────────────────────────────  │ │
│ │                                                                                         │ │
│ │ Recent activity                                                                         │ │
│ │                                                                                         │ │
│ │ Alex       Working on TASK-142 · Fix token rotation                                     │ │
│ │ Maya       Finished TASK-138 · Login error UI                                            │ │
│ │                                                                                         │ │
│ └─────────────────────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

# 7. Meetings

Clicking `+ Meeting` opens a dialog.

## Create Meeting Dialog

```text
┌───────────────────────────────────────────────┐
│ Create Meeting                           [×]  │
│                                               │
│ Topic                                         │
│ [ Authentication architecture              ] │
│                                               │
│ Participants                                  │
│                                               │
│ ☑ Alex        Backend Engineer                │
│ ☑ Maya        Frontend Engineer               │
│ ☐ Sam         Reviewer                        │
│ ☐ Jordan      DevOps                          │
│ ☑ Emma        Product Manager                 │
│                                               │
│ Goal / Instructions                           │
│ [ Decide how refresh-token rotation should  ] │
│ [ work across API and frontend.             ] │
│                                               │
│                         [Cancel] [Create]      │
└───────────────────────────────────────────────┘
```

When created:

```text
Main Room
  Sam
  Jordan

Authentication Architecture
  Alex
  Maya
  Emma
```

## Rooms View With Meeting

```text
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│ ROOMS                                                                                       │
│                                                                                             │
│ ┌─────────────────────────────────────────────────────────────────────────────────────────┐ │
│ │ 🏢 MAIN ROOM                                                               2 agents    │ │
│ ├─────────────────────────────────────────────────────────────────────────────────────────┤ │
│ │                                                                                         │ │
│ │   Sam                                      Jordan                                      │ │
│ │   Reviewer                                 DevOps                                      │ │
│ │   ○ Idle                                   ○ Idle                                      │ │
│ │                                                                                         │ │
│ └─────────────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                             │
│ ┌─────────────────────────────────────────────────────────────────────────────────────────┐ │
│ │ 💬 Authentication Architecture                                             3 agents    │ │
│ ├─────────────────────────────────────────────────────────────────────────────────────────┤ │
│ │                                                                                         │ │
│ │   Alex                    Maya                    Emma                                   │ │
│ │   Backend                 Frontend                Product                                │ │
│ │                                                                                         │ │
│ │ ──────────────────────────────────────────────────────────────────────────────────────  │ │
│ │                                                                                         │ │
│ │ Alex                                                                                    │ │
│ │ Refresh tokens should stay server-side.                                                 │ │
│ │                                                                                         │ │
│ │ Maya                                                                                    │ │
│ │ Then the frontend can rely on HttpOnly cookies.                                         │ │
│ │                                                                                         │ │
│ │ Emma                                                                                    │ │
│ │ Does this affect existing sessions?                                                     │ │
│ │                                                                                         │ │
│ │ ──────────────────────────────────────────────────────────────────────────────────────  │ │
│ │                                                           [Join] [End Meeting]          │ │
│ └─────────────────────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
```

When the meeting ends:

- Move participating agents back to Main Room.
- Store the meeting transcript.
- Generate/store:
  - summary
  - decisions
  - action items
  - unresolved questions
- Agents can then continue their assigned tasks.

---

# 8. Tasks View

The Tasks view is a Kanban board.

Initial columns:

```text
BACKLOG
IN PROGRESS
BLOCKED
DONE
```

## Kanban Mock-up

```text
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ TASKS                                                                                       [+ Task]   │
│                                                                                                        │
│ BACKLOG                   IN PROGRESS                 BLOCKED                    DONE                   │
│ ─────────────────────     ─────────────────────       ─────────────────────      ─────────────────────  │
│                                                                                                        │
│ ┌─────────────────────┐   ┌─────────────────────┐     ┌─────────────────────┐    ┌────────────────────┐ │
│ │ TASK-148            │   │ TASK-142            │     │ TASK-145            │    │ TASK-138           │ │
│ │                     │   │                     │     │                     │    │                    │ │
│ │ Improve billing UI  │   │ Fix token rotation  │     │ Deploy staging      │    │ Login error UI     │ │
│ │                     │   │                     │     │                     │    │                    │ │
│ │ Unassigned          │   │ Alex · Backend      │     │ Jordan · DevOps     │    │ Maya · Frontend    │ │
│ │                     │   │                     │     │                     │    │                    │ │
│ │ Medium              │   │ High                │     │ Blocked             │    │ ✓ Completed        │ │
│ └─────────────────────┘   └─────────────────────┘     └─────────────────────┘    └────────────────────┘ │
│                                                                                                        │
│ ┌─────────────────────┐   ┌─────────────────────┐                                                      │
│ │ TASK-149            │   │ TASK-146            │                                                      │
│ │                     │   │                     │                                                      │
│ │ Add usage analytics │   │ Review auth PR      │                                                      │
│ │                     │   │                     │                                                      │
│ │ Unassigned          │   │ Sam · Reviewer      │                                                      │
│ │                     │   │                     │                                                      │
│ │ Low                 │   │ Medium              │                                                      │
│ └─────────────────────┘   └─────────────────────┘                                                      │
│                                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

# 9. Task Lifecycle

## Creating a task

Every newly created task starts as:

```text
status = backlog
assignee = null
```

Example:

```text
TASK-148
Improve billing UI
BACKLOG
Unassigned
```

## Assigning an agent

When an agent is assigned:

```text
task.status = in_progress
task.assignee = agent.id
agent.status = working
agent.currentTaskId = task.id
```

The task moves automatically:

```text
BACKLOG
   ↓ assign Alex
IN PROGRESS
```

Claude Code should then receive the task.

Conceptually:

```text
User assigns Alex
        │
        ▼
Task → IN PROGRESS
        │
        ▼
Alex → WORKING
        │
        ▼
Send task context to Alex's Claude Code runtime
```

## Agent blocked

If Claude requires something that prevents progress:

```text
task.status = blocked
agent.status = blocked
agent.needsAttention = true
```

The task moves to the Blocked column.

## Decision answered

If the blocker was a human decision:

```text
task.status = in_progress
agent.status = working
```

The task moves back into In Progress.

## Task completed

When Claude signals task completion:

```text
task.status = done
agent.status = idle
agent.currentTaskId = null
```

The task moves to Done.

---

# 10. Create Task Dialog

```text
┌─────────────────────────────────────────────────────────┐
│ Create Task                                        [×]  │
│                                                         │
│ Title                                                   │
│ [ Fix refresh-token rotation                         ] │
│                                                         │
│ Description                                             │
│ [ Refresh tokens currently fail when a reused token  ] │
│ [ is detected. Implement token-family revocation.    ] │
│                                                         │
│ Priority                                                │
│ [ High ▼ ]                                              │
│                                                         │
│ Assign agent                                            │
│ [ Unassigned ▼ ]                                        │
│                                                         │
│ ──────────────────────────────────────────────────────  │
│                                                         │
│ If no agent is assigned, the task will be added to      │
│ Backlog.                                                │
│                                                         │
│ If an agent is assigned, it will immediately move to    │
│ In Progress and the agent will start working on it.     │
│                                                         │
│                                  [Cancel] [Create Task]  │
└─────────────────────────────────────────────────────────┘
```

---

# 11. Task Details

Clicking a Kanban task opens either:

- A side sheet, or
- A task details dialog.

Recommended: use the same right-side sheet pattern as agents.

```text
                                              ┌─────────────────────────────────────────────┐
                                              │ TASK-142                          [×]       │
                                              │ Fix refresh-token rotation                  │
                                              │                                             │
                                              │ IN PROGRESS                                 │
                                              │ High                                        │
                                              │                                             │
                                              │ Assigned to                                 │
                                              │ Alex · Backend Engineer                     │
                                              │                                             │
                                              │ ──────────────────────────────────────────  │
                                              │ DESCRIPTION                                 │
                                              │                                             │
                                              │ Refresh tokens fail when a reused token...   │
                                              │                                             │
                                              │ ──────────────────────────────────────────  │
                                              │ PROGRESS                                    │
                                              │                                             │
                                              │ ✓ Inspect current implementation             │
                                              │ ✓ Implement token-family tracking            │
                                              │ ● Run integration tests                      │
                                              │ ○ Update documentation                       │
                                              │                                             │
                                              │ ──────────────────────────────────────────  │
                                              │ ACTIVITY                                    │
                                              │                                             │
                                              │ 13:41 Alex started task                      │
                                              │ 13:44 Modified token.ts                      │
                                              │ 13:48 Tests running                          │
                                              │                                             │
                                              └─────────────────────────────────────────────┘
```

---

# 12. Attention / Notification System

An **attention event** represents something that requires the user's involvement.

Suggested types:

```ts
type AttentionType =
  | "decision_required"
  | "permission_required"
  | "agent_blocked"
  | "task_failed"
  | "meeting_attention"
  | "agent_question"
```

Suggested shape:

```ts
interface AttentionEvent {
  id: string

  type: AttentionType

  agentId?: string
  taskId?: string
  meetingId?: string
  decisionRequestId?: string

  title: string
  message: string

  resolved: boolean

  createdAt: string
  resolvedAt?: string
}
```

## Global notification ping

When a new unresolved attention event arrives:

```text
🔔 0
   ↓
🔔 1
```

If sound is enabled:

```text
new attention event
       ↓
play notification sound once
```

Also visually highlight the corresponding agent:

```text
┌───────────────────────────┐
│ ! Alex                    │
│ Backend Engineer          │
│ BLOCKED                   │
│ Needs your attention      │
└───────────────────────────┘
```

Optional browser notification support can be added later.

---

# 13. Notification Inbox

Clicking the bell shows unresolved requests.

```text
                                            ┌──────────────────────────────────────┐
                                            │ NEEDS YOUR ATTENTION                 │
                                            │                                      │
                                            │ ! Alex                               │
                                            │ Decision required                    │
                                            │ Refresh-token migration              │
                                            │                             [Open]   │
                                            │                                      │
                                            │ ! Jordan                             │
                                            │ Deployment failed                    │
                                            │ Staging health check failed          │
                                            │                             [Open]   │
                                            │                                      │
                                            │ ───────────────────────────────────  │
                                            │ 2 unresolved                         │
                                            └──────────────────────────────────────┘
```

Clicking `Open` should open the relevant agent/task/meeting side sheet.

---

# 14. Hire / Fire Agent

## Hire Agent

Hiring creates a persistent agent identity, not merely a Claude session.

The hire form must allow selecting:

- Name
- Role
- Instructions / role prompt
- Repository / workspace
- Skills from the global Skill Catalog
- MCP servers from the global MCP Pool

Every new hire automatically receives **Workspace Memory** in addition to their own initially empty private agent memory.

```text
┌──────────────────────────────────────────────────────────────┐
│ Hire Agent                                             [×]  │
│                                                              │
│ Name                                                         │
│ [ Alex                                                    ] │
│                                                              │
│ Role                                                         │
│ [ Backend Engineer                                        ] │
│                                                              │
│ Instructions / role definition                               │
│ [ Senior backend engineer. Focus on API architecture,      ] │
│ [ database design, performance and reliability.            ] │
│                                                              │
│ Repository / workspace                                       │
│ [ patricia ▼ ]                                               │
│                                                              │
│ Skills                                                       │
│ [ Search skills...                                      ]   │
│                                                              │
│ ☑ Backend Development                                        │
│ ☑ PostgreSQL                                                 │
│ ☐ UI Design                                                  │
│ ☑ Testing                                                    │
│                                                              │
│                         [Manage Skill Catalog]                │
│                                                              │
│ Allowed MCP Servers                                          │
│                                                              │
│ ☑ GitHub                                                     │
│ ☑ Neon                                                       │
│ ☐ Slack                                                      │
│ ☐ Figma                                                      │
│                                                              │
│                         [Manage MCP Servers]                  │
│                                                              │
│ Memory                                                       │
│ ✓ Workspace Memory will be inherited automatically           │
│ ✓ A private memory store will be created for this agent      │
│                                                              │
│                                             [Hire Agent]     │
└──────────────────────────────────────────────────────────────┘
```

After creation:

```text
agent.status = idle
agent.roomId = main_room

agent.skills = selectedSkillIds
agent.allowedMcpServers = selectedMcpServerIds

agent.privateMemory = new empty persistent memory namespace
agent.workspaceMemoryAccess = enabled
```

The new agent appears immediately in the left sidebar and Main Room.

## Fire Agent

The Agent Detail Sheet must contain a contextual destructive action:

```text
[Fire Agent]
```

Place it near the bottom of the sheet or inside an overflow/settings menu, not next to frequent actions.

Example:

```text
                                              ┌─────────────────────────────────────────────┐
                                              │ Alex                              [×]       │
                                              │ Backend Engineer                            │
                                              │                                             │
                                              │ Skills                                      │
                                              │ Backend · PostgreSQL · Testing               │
                                              │                                             │
                                              │ MCP access                                  │
                                              │ GitHub · Neon                               │
                                              │                                             │
                                              │ Memory                                      │
                                              │ 184 private memories                        │
                                              │ Workspace memory: enabled                   │
                                              │                                             │
                                              │ ──────────────────────────────────────────  │
                                              │ AGENT SETTINGS                              │
                                              │ [Edit Agent]                                │
                                              │ [Fire Agent]                                │
                                              └─────────────────────────────────────────────┘
```

Firing requires confirmation:

```text
┌──────────────────────────────────────────────────────────────┐
│ Fire Alex?                                             [×]  │
│                                                              │
│ Alex will stop receiving work and will be removed from       │
│ active rooms and the agent list.                             │
│                                                              │
│ Current task: TASK-142 · Fix token rotation                  │
│                                                              │
│ What should happen to assigned unfinished tasks?             │
│                                                              │
│ ● Move back to Backlog                                       │
│ ○ Reassign now                                               │
│                                                              │
│ Memory handling                                              │
│ ● Archive private memory and history                          │
│ ○ Permanently delete private memory                           │
│                                                              │
│ Workspace Memory is not affected.                            │
│                                                              │
│                           [Cancel] [Fire Agent]               │
└──────────────────────────────────────────────────────────────┘
```

Default behavior should be **archive, not delete**:

```text
agent.lifecycle = fired
agent.active = false
agent.privateMemoryStatus = archived
```

Unfinished assigned tasks return to Backlog unless the user explicitly reassigns them.

Do not delete:

- task history
- meeting history
- decisions
- audit events
- artifacts/commits
- archived private memory

unless the user explicitly chooses permanent deletion.

---

# 15. Global Skill Catalog

Skills are repository-backed reusable instruction/capability packages.

There is one global catalog for the workspace/app repository. Agents receive references to selected skills from this catalog.

## Suggested repository structure

The exact format can evolve, but use a simple repository-owned layout such as:

```text
.agent-office/
  skills/
    backend-development/
      SKILL.md
      metadata.json

    ui-design/
      SKILL.md
      metadata.json

    testing/
      SKILL.md
      metadata.json
```

The repository is the source of truth.

The UI should read/write these skill definitions rather than maintaining a separate disconnected copy.

## Skills View

```text
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│ SKILL CATALOG                                                     [+ Add Skill]          │
│                                                                                          │
│ Search skills... [________________________________________]                               │
│                                                                                          │
│ ┌──────────────────────────────────────────────────────────────────────────────────────┐ │
│ │ Backend Development                                                     3 agents    │ │
│ │ API design, backend architecture, reliability                                       │ │
│ │                                                                            [Edit]    │ │
│ └──────────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                          │
│ ┌──────────────────────────────────────────────────────────────────────────────────────┐ │
│ │ PostgreSQL                                                               2 agents    │ │
│ │ Schema design, migrations, query optimization                                      │ │
│ │                                                                            [Edit]    │ │
│ └──────────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                          │
│ ┌──────────────────────────────────────────────────────────────────────────────────────┐ │
│ │ UI Design                                                                1 agent     │ │
│ │ UI hierarchy, interaction patterns, accessibility                                  │ │
│ │                                                                            [Edit]    │ │
│ └──────────────────────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

## Add / Edit Skill

```text
┌──────────────────────────────────────────────────────────────┐
│ Edit Skill                                             [×]  │
│                                                              │
│ Name                                                         │
│ [ Backend Development                                     ] │
│                                                              │
│ Description                                                  │
│ [ Backend architecture and implementation guidance.       ] │
│                                                              │
│ Instructions / SKILL.md                                      │
│ ┌──────────────────────────────────────────────────────────┐ │
│ │ You are responsible for...                               │ │
│ │                                                          │ │
│ └──────────────────────────────────────────────────────────┘ │
│                                                              │
│ Repository path                                              │
│ .agent-office/skills/backend-development/                     │
│                                                              │
│                                [Delete Skill] [Save Changes] │
└──────────────────────────────────────────────────────────────┘
```

Users can:

- create skill
- edit skill
- delete skill
- assign/unassign skill to agents
- inspect which agents currently use a skill

Deleting a skill that is assigned to agents must show the affected agents before confirmation.

Suggested shape:

```ts
interface Skill {
  id: string
  slug: string
  name: string
  description?: string

  repositoryPath: string
  instructions: string

  createdAt: string
  updatedAt: string
}
```

Agent assignment:

```ts
interface AgentSkillAssignment {
  agentId: string
  skillId: string
}
```

At runtime, the Context Builder loads only skills assigned to that agent.

---

# 16. Global MCP Server Pool

MCP servers are also managed globally, while permission to use them is configured per agent.

The UI must support:

- Create MCP server
- Edit MCP server
- Remove MCP server
- Enable/disable server globally
- Test connection
- Assign/unassign server access to agents
- View which agents are allowed to use a server

## MCP Servers View

```text
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│ MCP SERVERS                                                     [+ Add MCP Server]       │
│                                                                                          │
│ ┌──────────────────────────────────────────────────────────────────────────────────────┐ │
│ │ ● GitHub                                                   Enabled · 4 agents        │ │
│ │ HTTP · OAuth                                                                     │ │
│ │                                                       [Test] [Edit]                  │ │
│ └──────────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                          │
│ ┌──────────────────────────────────────────────────────────────────────────────────────┐ │
│ │ ● Neon                                                     Enabled · 2 agents        │ │
│ │ HTTP · OAuth                                                                     │ │
│ │                                                       [Test] [Edit]                  │ │
│ └──────────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                          │
│ ┌──────────────────────────────────────────────────────────────────────────────────────┐ │
│ │ ○ Local Browser MCP                                         Disabled · 0 agents       │ │
│ │ stdio                                                                            │ │
│ │                                                       [Test] [Edit]                  │ │
│ └──────────────────────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

## Create / Edit MCP Server

Support the connection/configuration types required by the runtime.

Conceptual UI:

```text
┌──────────────────────────────────────────────────────────────┐
│ Add MCP Server                                         [×]  │
│                                                              │
│ Name                                                         │
│ [ GitHub                                                  ] │
│                                                              │
│ Transport                                                    │
│ [ HTTP ▼ ]                                                   │
│                                                              │
│ URL / Command                                                │
│ [ https://...                                             ] │
│                                                              │
│ Authentication                                               │
│ [ OAuth ▼ ]                                                  │
│                                                              │
│ Credentials / environment                                    │
│ [ Configure securely...                                   ] │
│                                                              │
│ Enabled                                                      │
│ [✓]                                                          │
│                                                              │
│ Agent access                                                 │
│ ☑ Alex                                                       │
│ ☑ Maya                                                       │
│ ☐ Sam                                                        │
│                                                              │
│                          [Test Connection] [Save MCP Server] │
└──────────────────────────────────────────────────────────────┘
```

Sensitive MCP credentials must **not** be exposed to Claude as raw prompt text.

Store secrets using the app's server-side secret mechanism and provide only the runtime connection capability.

Suggested shape:

```ts
type McpTransport = "stdio" | "http" | "sse"

interface McpServer {
  id: string
  name: string

  transport: McpTransport

  command?: string
  args?: string[]
  url?: string

  authType?: "none" | "bearer" | "oauth" | "custom"

  enabled: boolean

  // Reference to encrypted/server-side secret storage.
  credentialRef?: string

  createdAt: string
  updatedAt: string
}

interface AgentMcpPermission {
  agentId: string
  mcpServerId: string
  allowed: boolean
}
```

At runtime:

```text
Global MCP Pool
       │
       ├── GitHub
       ├── Neon
       ├── Slack
       └── Figma
              │
       permission filter
              │
              ▼
         Agent runtime
```

An agent must never automatically gain access to a newly created MCP server.

Access is explicit per agent.

---

# 17. Memory Architecture

Memory must be treated as persistent application state, separate from the Claude Code session/context window.

There are two primary memory layers:

```text
Workspace Memory
      │
      ├──────────────► Alex
      ├──────────────► Maya
      ├──────────────► Sam
      └──────────────► every future hire

Private Agent Memory
      │
      └──────────────► only that agent
```

## 17.1 Workspace Memory

Workspace Memory contains knowledge that should apply to the whole company/workspace.

Examples:

```text
Architecture:
"We use Neon Postgres for the primary database."

Engineering convention:
"All new UI must support dark mode."

Product rule:
"Never change billing behavior without explicit human approval."

Repository context:
"The API lives in apps/api and frontend lives in apps/web."
```

Workspace Memory is automatically included as an available memory source for:

- all existing agents
- every newly hired agent

New hires do **not** need manual assignment.

The UI needs a dedicated Workspace Memory view.

```text
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│ WORKSPACE MEMORY                                                   [+ Add Memory]        │
│                                                                                          │
│ Search memory... [________________________________________]                               │
│                                                                                          │
│ Pinned                                                                                   │
│ ┌──────────────────────────────────────────────────────────────────────────────────────┐ │
│ │ Architecture                                                                         │ │
│ │ Primary database is Neon Postgres.                                      [Edit]       │ │
│ └──────────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                          │
│ ┌──────────────────────────────────────────────────────────────────────────────────────┐ │
│ │ Product rule                                                                         │ │
│ │ Billing changes require explicit human approval.                        [Edit]       │ │
│ └──────────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                          │
│ Other memory                                                                             │
│ ...                                                                                      │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

Users can:

- create memory
- edit memory
- delete/archive memory
- pin important memory
- search memory
- inspect provenance/history

Suggested shape:

```ts
interface WorkspaceMemory {
  id: string

  type:
    | "fact"
    | "decision"
    | "convention"
    | "lesson"
    | "architecture"
    | "product_context"

  title?: string
  content: string

  importance: number
  pinned: boolean

  status: "active" | "superseded" | "archived"

  createdAt: string
  updatedAt: string
}
```

## 17.2 Per-Agent Private Memory

Each agent has a persistent private memory namespace.

Examples for a backend agent:

```text
"I previously investigated the refresh-token race in token.ts."

"Alex prefers to validate migrations against a disposable Neon branch."

"TASK-142 introduced token-family revocation."

"The failing auth integration test is caused by fixture X."
```

Do not share these automatically with other agents.

Suggested memory scope:

```ts
type MemoryScope =
  | "workspace"
  | "agent"
  | "meeting"
  | "task"
```

Private agent memories should support:

- automatic extraction from work
- manual add/edit/delete
- semantic retrieval
- importance
- recency
- pinning
- superseding stale memories
- provenance: where the memory came from

Suggested shape:

```ts
interface MemoryRecord {
  id: string

  scope: MemoryScope
  agentId?: string
  taskId?: string
  meetingId?: string

  type:
    | "fact"
    | "decision"
    | "preference"
    | "lesson"
    | "task_summary"
    | "project_context"

  content: string

  importance: number
  pinned: boolean

  status: "active" | "superseded" | "archived"

  sourceType?: "human" | "agent" | "meeting" | "task" | "system"
  sourceId?: string

  createdAt: string
  lastAccessedAt?: string
}
```

## 17.3 Agent Memory UI

Expose memory from the Agent Detail Sheet:

```text
                                              ┌─────────────────────────────────────────────┐
                                              │ Alex                              [×]       │
                                              │ Backend Engineer                            │
                                              │                                             │
                                              │ [Overview] [Memory] [Skills & MCP]          │
                                              │                                             │
                                              │ MEMORY                                      │
                                              │                                             │
                                              │ Workspace Memory                            │
                                              │ ✓ Enabled automatically                     │
                                              │ 46 active shared memories                   │
                                              │                                             │
                                              │ Private Memory                              │
                                              │ 184 active memories                         │
                                              │                                             │
                                              │ Search [____________________________]        │
                                              │                                             │
                                              │ 📌 Token rotation uses token families       │
                                              │    learned from TASK-142                    │
                                              │                                             │
                                              │    Auth middleware lives in ...             │
                                              │                                             │
                                              │                         [+ Add Memory]       │
                                              └─────────────────────────────────────────────┘
```

## 17.4 Context Window Management

Do not make a long-running Claude conversation the source of memory.

Treat:

```text
Claude context window = temporary working context
Persistent memory     = durable storage
```

Build each execution context from:

```text
Agent role / identity
        +
Assigned skills
        +
Allowed MCP capabilities
        +
Relevant Workspace Memory
        +
Relevant Private Agent Memory
        +
Current task
        +
Relevant task/meeting context
        +
Recent conversation/activity
```

Do **not** inject all stored memory into every prompt.

Retrieve only relevant memories plus pinned critical items.

Conceptual Context Builder:

```text
                  Workspace Memory
                         │
Private Agent Memory ────┼────► Context Builder
                         │
Assigned Skills ─────────┤
                         │
Current Task ────────────┤
                         │
Recent Messages ─────────┤
                         │
                         ▼
                    Claude Code
```

## 17.5 Session Rotation / Checkpointing

An agent is persistent; an individual Claude Code session is replaceable.

```text
Agent Alex
│
├── identity
├── skills
├── MCP permissions
├── private memory
├── task/workspace state
│
└── Claude sessions
     ├── old session
     ├── old session
     └── current session
```

When a context becomes too large or noisy:

1. Ask the runtime to produce a structured checkpoint.
2. Extract important durable memories.
3. Persist task state and technical state.
4. Archive the old session.
5. Start a clean Claude session.
6. Rebuild context from persistent state.

Suggested checkpoint:

```ts
interface AgentCheckpoint {
  summary: string
  decisions: string[]
  discoveries: string[]
  importantFiles: string[]
  unfinishedWork: string[]
  blockers: string[]
  risks: string[]

  branch?: string
  headSha?: string
  testStatus?: string
}
```

This rotation should eventually be automatic based on context usage and task boundaries.

## 17.6 Memory Consolidation

Prevent contradictory/stale memory from accumulating forever.

Example:

```text
Old:
"We use Redis queues."

Later:
"We are migrating away from Redis."

Current:
"Job queues use Postgres; Redis is no longer used for queues."
```

Mark old records as:

```text
superseded
```

rather than blindly returning every historical statement during retrieval.

---

# 18. Agent Skills & MCP in Side Sheet

The Agent Detail Sheet should have a dedicated configuration tab:

```text
                                              ┌─────────────────────────────────────────────┐
                                              │ Alex                              [×]       │
                                              │ Backend Engineer                            │
                                              │                                             │
                                              │ [Overview] [Memory] [Skills & MCP]          │
                                              │                                             │
                                              │ SKILLS                                      │
                                              │ ☑ Backend Development                       │
                                              │ ☑ PostgreSQL                                │
                                              │ ☑ Testing                                   │
                                              │ ☐ UI Design                                 │
                                              │                                             │
                                              │ [Manage global skills]                      │
                                              │                                             │
                                              │ ──────────────────────────────────────────  │
                                              │ MCP ACCESS                                  │
                                              │ ☑ GitHub                                    │
                                              │ ☑ Neon                                      │
                                              │ ☐ Slack                                     │
                                              │ ☐ Figma                                     │
                                              │                                             │
                                              │ [Manage global MCP servers]                 │
                                              │                                             │
                                              │                              [Save Changes] │
                                              └─────────────────────────────────────────────┘
```

Changes apply to future agent turns/runtime launches.

If an MCP is removed from an agent while a task is running, revoke it for subsequent tool calls as soon as the runtime supports safe dynamic refresh; otherwise restart/refresh the agent runtime at the next safe boundary.

---

# 19. Recommended Overall Interaction

Example user workflow:

```text
1. User clicks + Task

2. Creates:
   "Fix refresh-token rotation"

3. Task appears:
   BACKLOG

4. User assigns Alex

5. Automatically:
   Task → IN PROGRESS
   Alex → WORKING

6. Claude Code starts working

7. Claude encounters architectural choice

8. Automatically:
   Alex → BLOCKED
   Task → BLOCKED
   needsAttention → true
   🔔 counter increases
   🔊 notification sound

9. User clicks Alex

10. Agent side sheet opens

11. User chooses one of Claude's proposed decisions

12. Response goes back to Claude

13. Automatically:
    Alex → WORKING
    Task → IN PROGRESS

14. Claude finishes

15. Automatically:
    Task → DONE
    Alex → IDLE
```

---

# 20. Core Entity Relationships

```text
Workspace
│
├── Agents
│     │
│     ├── currentTask
│     ├── room
│     └── Claude session/runtime
│
├── Tasks
│     │
│     └── assigned Agent
│
├── Rooms
│     │
│     └── Agents
│
├── Meetings
│     │
│     ├── participants
│     ├── messages
│     ├── decisions
│     └── action items
│
├── Decision Requests
│     │
│     ├── Agent
│     └── optional Task
│
├── Skill Catalog
│     │
│     └── assigned to Agents
│
├── MCP Server Pool
│     │
│     └── permissioned to Agents
│
├── Workspace Memory
│     │
│     └── automatically available to every Agent
│
├── Private Agent Memory
│     │
│     └── belongs to one Agent
│
└── Attention Events
      │
      └── links back to agent/task/meeting/decision
```

---

# 21. Suggested Frontend State Model

```ts
interface WorkspaceState {
  view: "rooms" | "tasks"

  agents: Agent[]
  tasks: Task[]
  rooms: Room[]
  meetings: Meeting[]

  skills: Skill[]
  mcpServers: McpServer[]

  workspaceMemory: WorkspaceMemory[]
  agentMemory: MemoryRecord[]

  attentionEvents: AttentionEvent[]

  selectedAgentId?: string
  selectedTaskId?: string

  soundEnabled: boolean
}
```

Task:

```ts
type TaskStatus =
  | "backlog"
  | "in_progress"
  | "blocked"
  | "done"

interface Task {
  id: string
  title: string
  description?: string

  status: TaskStatus
  priority: "low" | "medium" | "high"

  assigneeId?: string

  progressSummary?: string

  createdAt: string
  startedAt?: string
  completedAt?: string
}
```

Room:

```ts
interface Room {
  id: string
  name: string

  type: "main" | "meeting"

  agentIds: string[]
}
```

---

# 22. Important Behavior Rules

### Rule 1 — There is always a Main Room

All agents who are not participating in another meeting belong to Main Room.

### Rule 2 — Status and room are separate

Valid:

```text
Alex
status: working
room: Authentication Meeting
```

Do not model:

```text
status: in_meeting
```

### Rule 3 — Unassigned tasks belong in Backlog

```text
assignee = null
status = backlog
```

### Rule 4 — Assigning an agent starts work

```text
assign agent
    ↓
task = in_progress
agent = working
Claude receives task
```

### Rule 5 — One primary task per agent for MVP

An agent can have many historical tasks, but only one active primary task.

This avoids confusing state such as:

```text
Alex working on TASK-1
Alex working on TASK-2
Alex working on TASK-3
```

Multi-task scheduling can be introduced later.

### Rule 6 — Human decisions block execution

When Claude explicitly requires a decision before safely continuing:

```text
agent.status = blocked
task.status = blocked
```

### Rule 7 — Attention state is independent

An agent can need attention even when a task isn't fully blocked.

Example:

```text
agent.status = working
needsAttention = true
```

for a non-blocking question.

### Rule 8 — Notifications are event driven

Do not derive all notifications just from `agent.status`.

Create explicit attention events so they can be:

- counted
- resolved
- linked
- deduplicated
- audited

### Rule 9 — Skills are global; assignments are per agent

A skill exists once in the repository-backed catalog.

```text
Skill Catalog
    ↓ assign
Agent
```

Do not duplicate the skill contents into each agent record.

### Rule 10 — MCP servers are global; access is per agent

Creating an MCP server does not grant it to all agents.

```text
MCP Pool
    ↓ explicit permission
Agent
```

### Rule 11 — Every agent gets Workspace Memory

Workspace Memory is automatically available to all agents, including future hires.

No per-agent opt-in is required for the base shared workspace memory layer.

### Rule 12 — Private memory survives session rotation

Starting a fresh Claude Code session must not erase the agent's persistent private memory.

### Rule 13 — Firing archives by default

Firing removes an agent from active work but preserves historical records unless permanent deletion is explicitly requested.


---

# 23. Suggested Realtime Events

Use WebSocket/SSE events between backend and browser.

Examples:

```text
agent.created
agent.status_changed
agent.activity_changed

task.created
task.assigned
task.started
task.blocked
task.completed

meeting.created
meeting.message
meeting.ended

decision.created
decision.answered

attention.created
attention.resolved

skill.created
skill.updated
skill.deleted
agent.skill_assigned
agent.skill_removed

mcp.created
mcp.updated
mcp.deleted
mcp.connection_tested
agent.mcp_granted
agent.mcp_revoked

memory.created
memory.updated
memory.archived
memory.superseded

agent.fired
```

Example payload:

```json
{
  "type": "decision.created",
  "data": {
    "decisionId": "decision_123",
    "agentId": "agent_alex",
    "taskId": "task_142"
  }
}
```

The frontend receives it and immediately:

```text
Alex card → BLOCKED
TASK-142 → BLOCKED
bell → +1
sound → ping
```

---

# 24. MVP Scope

Implement these first:

- Agent sidebar
- Rooms view
- Main Room
- Create meeting
- Meeting room
- Hire agent
- Fire agent with safe archival flow
- Global Skill Catalog UI
- Create/edit/delete skills
- Assign/unassign skills per agent
- Global MCP Server Pool UI
- Create/edit/delete/test MCP servers
- Grant/revoke MCP access per agent
- Workspace Memory UI
- Automatic Workspace Memory inheritance for new hires
- Per-agent private persistent memory
- Memory retrieval/context builder
- Session checkpoint + rotation design
- Agent side sheet with Overview / Memory / Skills & MCP
- Tasks/Kanban view
- Create task
- Assign task
- Backlog → In Progress automation
- In Progress → Blocked automation
- Blocked → In Progress after decision
- In Progress → Done
- Claude decision request UI
- Bell notification count
- Sound on/off
- Realtime UI updates

Do **not** make the first version overly complicated with:

- multiple concurrent tasks per agent
- complex workforce scheduling
- agent performance scoring
- payroll/budget simulation
- sophisticated room permissions
- arbitrary workflow builders

Those can come later.

---

# 25. Final Desktop Mock-up

```text
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ AGENT OFFICE                                                  🔔 1   🔊 On   [+ Task] [+ Meeting] [+ Hire Agent] │
├──────────────────────────────┬──────────────────────────────────────────────────────────────────────────────┤
│                              │                                                                              │
│ AGENTS                       │  [ Rooms ] [ Tasks ] [ Skills ] [ MCP ] [ Workspace Memory ]                │
│                              │                                                                              │
│ ┌──────────────────────────┐ │  BACKLOG               IN PROGRESS             BLOCKED             DONE     │
│ │ ● Alex                   │ │  ───────────────────   ───────────────────     ─────────────────   ──────── │
│ │ Backend Engineer         │ │                                                                              │
│ │ WORKING                  │ │  ┌─────────────────┐   ┌─────────────────┐     ┌─────────────────┐           │
│ │ Fix token rotation       │ │  │ TASK-148        │   │ TASK-142        │     │ TASK-145        │           │
│ └──────────────────────────┘ │  │ Billing UI      │   │ Token rotation  │     │ Deploy staging  │           │
│                              │  │                 │   │                 │     │                 │           │
│ ┌──────────────────────────┐ │  │ Unassigned      │   │ Alex            │     │ Jordan          │           │
│ │ ○ Maya                   │ │  └─────────────────┘   └─────────────────┘     └─────────────────┘           │
│ │ Frontend Engineer        │ │                                                                              │
│ │ IDLE                     │ │  ┌─────────────────┐   ┌─────────────────┐                                      │
│ └──────────────────────────┘ │  │ TASK-149        │   │ TASK-146        │                                      │
│                              │  │ Analytics       │   │ Review auth PR  │                                      │
│ ┌──────────────────────────┐ │  │                 │   │                 │                                      │
│ │ ! Sam                    │ │  │ Unassigned      │   │ Sam             │                                      │
│ │ Reviewer                 │ │  └─────────────────┘   └─────────────────┘                                      │
│ │ BLOCKED                  │ │                                                                              │
│ │ Needs your decision      │ │                                                                              │
│ └──────────────────────────┘ │                                                                              │
│                              │                                                     ┌────────────────────────┐ │
│ ┌──────────────────────────┐ │                                                     │ Sam              [×]  │ │
│ │ ● Jordan                 │ │                                                     │ Reviewer              │ │
│ │ DevOps Engineer          │ │                                                     │ ! BLOCKED             │ │
│ │ WORKING                  │ │                                                     │                      │ │
│ │ Deploy staging           │ │                                                     │ DECISION NEEDED      │ │
│ └──────────────────────────┘ │                                                     │                      │ │
│                              │                                                     │ The tests disagree   │ │
│ ┌──────────────────────────┐ │                                                     │ with the API spec.    │ │
│ │ ○ Emma                   │ │                                                     │                      │ │
│ │ Product Manager          │ │                                                     │ ○ Update tests        │ │
│ │ IDLE                     │ │                                                     │ ○ Update API          │ │
│ └──────────────────────────┘ │                                                     │                      │ │
│                              │                                                     │ [Custom answer...]   │ │
│                              │                                                     │                      │ │
│                              │                                                     │      [Submit]        │ │
│                              │                                                     └────────────────────────┘ │
└──────────────────────────────┴──────────────────────────────────────────────────────────────────────────────┘
```

---


# 26. Implementation Plan

Implement in layers so Claude runtime orchestration is not tightly coupled to UI components.

## Phase 1 — Core domain and persistence

Implement persistent entities for:

```text
Workspace
Agent
Task
Room
Meeting
DecisionRequest
AttentionEvent

Skill
AgentSkillAssignment

McpServer
AgentMcpPermission

WorkspaceMemory
MemoryRecord
AgentCheckpoint
```

Create clear service boundaries for:

```text
AgentService
TaskService
MeetingService
SkillService
McpService
MemoryService
AttentionService
RuntimeService
```

## Phase 2 — Agent lifecycle

Implement:

```text
Hire
Edit
Fire / archive
Restore later if desired
```

Hiring must:

1. Create agent identity.
2. Assign chosen skills.
3. Assign chosen MCP permissions.
4. Create private memory namespace.
5. Automatically enable Workspace Memory.
6. Put agent in Main Room.
7. Initialize runtime only when needed.

Firing must:

1. Stop active runtime safely.
2. Remove agent from active rooms/meetings.
3. Handle unfinished tasks.
4. Revoke runtime MCP access.
5. Archive private memory by default.
6. Preserve historical audit/task/meeting records.

## Phase 3 — Global capabilities

Implement repository-backed Skill Catalog management.

Implement global MCP Pool management with secret-safe credential storage and per-agent permissioning.

These are global workspace resources; agent records store assignments/references, not copies.

## Phase 4 — Memory system

This is a first-class part of the product, not a later chat-history feature.

Implement **per-person memory management** for every agent:

```text
private persistent memory
memory search/retrieval
manual inspection/editing
pinning
importance
provenance
superseding stale memories
checkpoint extraction
```

Implement **Workspace Memory**:

```text
shared persistent knowledge
automatically available to every agent
automatically inherited by new hires
manual UI management
retrieval into runtime context
```

Implement a Context Builder that combines:

```text
agent identity
+ assigned skills
+ allowed MCP capabilities
+ relevant workspace memory
+ relevant private agent memory
+ current task
+ relevant task/meeting state
+ recent messages
```

Do not equate Claude session history with memory.

## Phase 5 — Tasks and runtime

Implement task lifecycle and runtime dispatch:

```text
Backlog
  ↓ assign
In Progress
  ↓ needs human decision
Blocked
  ↓ answer
In Progress
  ↓ finished
Done
```

Connect each active task to an agent runtime.

## Phase 6 — Rooms and meetings

Implement Main Room, temporary meeting rooms, participant movement, transcript storage, decisions/action-item extraction, and return participants to Main Room.

## Phase 7 — Human attention loop

Implement:

```text
Decision requests
Agent blockers
Bell count
Attention inbox
Sound toggle
One-time sound ping per new event
Deep-link/open correct side sheet
```

## Phase 8 — Context/session lifecycle

Track approximate context usage.

Before a session becomes too large/noisy:

```text
checkpoint
→ extract durable memories
→ persist task/runtime state
→ archive session
→ create fresh session
→ reconstruct context
```

The persistent **agent** must survive replacement of the underlying Claude session.

---


# 27. Backup, Persistence & Disaster Recovery

The system must be recoverable if the local machine/VPS is lost, corrupted, or rebuilt.

There are two different persistence categories and they should be backed up differently:

```text
Repository state
├── application code
├── Skill Catalog
└── non-secret static configuration

Runtime state
├── agents
├── tasks
├── rooms / meetings
├── decisions
├── private agent memories
├── Workspace Memory
├── skill assignments
├── MCP definitions / permissions
└── audit/activity state
```

## 27.1 Skill persistence

Skills live inside the Git repository and Git is their source of truth.

Example:

```text
.agent-office/
└── skills/
    ├── backend-development/
    │   ├── SKILL.md
    │   └── metadata.json
    │
    └── testing/
        ├── SKILL.md
        └── metadata.json
```

When skills are created, edited, or removed through the UI, the application modifies these repository files.

### Recommended behavior

Prefer committing skill changes soon after the UI operation rather than relying solely on a daily cron.

```text
Create/Edit/Delete skill
        ↓
write repository files
        ↓
mark repository dirty
        ↓
commit + push
```

A daily backup job should still run as a safety net in case automatic commits failed.

Example automatic commit messages:

```text
agent-office: add skill "PostgreSQL"
agent-office: update skill "UI Design"
agent-office: remove skill "Legacy Deployment"
```

For multiple pending changes:

```text
agent-office: sync skill catalog 2026-09-03
```

Do not automatically commit unrelated user source-code changes.

The backup process should only stage paths owned by Agent Office, for example:

```bash
git add .agent-office/skills/
```

Never:

```bash
git add -A
```

because agents or the human developer may have unrelated working-tree changes.

## 27.2 Daily repository sync job

Run at least once per day.

Conceptual job:

```text
Daily backup job
      │
      ├── check .agent-office/skills for changes
      │
      ├── commit changes if present
      │
      └── push backup branch/repository
```

The job must be idempotent.

If there are no changes:

```text
exit successfully
```

Do not create empty commits.

Record:

```text
last successful Git backup
last attempted Git backup
last backup commit SHA
last error
```

Expose backup status in Settings/System Status.

---

## 27.3 PostgreSQL backups

Postgres contains the operational state required to reconstruct the office.

The backup must include enough state to restore:

- agents and lifecycle state
- tasks and assignments
- meetings and transcripts
- decision requests
- attention events where useful
- per-agent private memory
- Workspace Memory
- skill assignments
- MCP server definitions
- MCP permissions
- checkpoints
- application settings

### Important: do not commit raw database dumps into the normal application Git history

A PostgreSQL dump may:

- grow quickly
- make the repository permanently large
- contain private agent memory
- contain internal project information
- accidentally contain secrets
- be difficult to rotate/delete because Git keeps historical blobs

Therefore the preferred design is:

```text
GitHub repository
└── code + skills + non-secret configuration

Backup storage
└── encrypted PostgreSQL snapshots
```

Recommended backup targets include an encrypted/private object store or dedicated backup repository/storage.

If GitHub must be used as the backup destination, use a **separate private backup repository or release/artifact storage**, not the main application's Git commit history.

Never store:

- raw OAuth tokens
- API keys
- MCP bearer tokens
- unencrypted credentials

inside a Git repository.

---

## 27.4 PostgreSQL dump job

Run a database backup daily.

Conceptually:

```bash
pg_dump \
  --format=custom \
  --no-owner \
  --no-acl \
  "$DATABASE_URL" \
  > agent-office-YYYY-MM-DD.dump
```

Prefer PostgreSQL's custom dump format because it supports `pg_restore` and selective restore.

The job then:

```text
pg_dump
   ↓
compress/encrypt if required
   ↓
upload backup
   ↓
verify upload exists
   ↓
record checksum
   ↓
update backup status
```

Do not consider the backup successful until the uploaded artifact has been verified.

Suggested metadata:

```ts
interface BackupRecord {
  id: string

  type: "postgres" | "repository"

  startedAt: string
  completedAt?: string

  status:
    | "running"
    | "success"
    | "failed"

  location?: string
  checksum?: string

  gitCommitSha?: string

  error?: string
}
```

---

## 27.5 Backup retention

Do not keep unlimited daily database dumps.

Suggested initial retention policy:

```text
Daily backups       14 days
Weekly backups       8 weeks
Monthly backups     12 months
```

This is an initial policy and should be configurable.

A simple MVP can begin with:

```text
last 14 daily backups
```

and add tiered retention later.

---

## 27.6 Recovery target

The backup design should allow rebuilding the complete Agent Office from:

```text
1. Git repository
      +
2. latest PostgreSQL backup
      +
3. separately stored MCP/application secrets
```

Recovery flow:

```text
Fresh machine / VPS
        │
        ▼
Clone Git repository
        │
        ▼
Restore dependencies
        │
        ▼
Start fresh PostgreSQL
        │
        ▼
pg_restore latest backup
        │
        ▼
Restore/configure secrets
        │
        ▼
Start Agent Office
        │
        ▼
Agents, tasks, memory, skills,
permissions and workspace state return
```

Claude Code sessions themselves do not need to be recoverable byte-for-byte.

After recovery:

```text
persistent Agent state
        +
agent/private memory
        +
Workspace Memory
        +
task checkpoint
        +
Git workspace
        ↓
new Claude Code session
```

The agent should continue from persistent state.

---

## 27.7 Secrets backup

MCP credentials and application secrets are separate from normal Postgres/Git backup.

Preferred model:

```text
MCP record in Postgres
{
  name: "GitHub",
  url: "...",
  authType: "oauth",
  credentialRef: "secret/github/alex"
}
```

while the actual credential lives in encrypted secret storage.

Back up the secret store using whatever encrypted mechanism the deployment environment supports.

A restore is not complete until both:

```text
database
+
secret store
```

have been recovered.

---

## 27.8 Backup UI

Add a small system/settings view:

```text
┌────────────────────────────────────────────────────────────────────┐
│ BACKUPS                                                            │
│                                                                    │
│ Repository                                                         │
│ ✓ Last push: Today 02:00                                           │
│ Commit: a81f29c                                                    │
│                                                [Back Up Now]       │
│                                                                    │
│ PostgreSQL                                                         │
│ ✓ Last backup: Today 02:03                                         │
│ Size: 184 MB                                                       │
│ Verified: Yes                                                      │
│                                                [Back Up Now]       │
│                                                                    │
│ Recovery                                                           │
│ Latest usable restore point: Sep 3, 2026 02:03                    │
│                                                                    │
│                                         [View Backup History]      │
└────────────────────────────────────────────────────────────────────┘
```

A failed backup must create an attention event:

```text
type = backup_failed
```

and trigger the normal notification system.

---

## 27.9 Scheduled maintenance job

The daily maintenance job can coordinate several persistence tasks:

```text
Daily Maintenance
│
├── Sync Skill Catalog to Git
│
├── Create PostgreSQL backup
│
├── Verify backup
│
├── Apply retention policy
│
├── Consolidate/supersede stale memories
│
└── Record health/status
```

These should be separate internal steps so one failure does not hide the status of the others.

Example result:

```text
Skill sync       ✓
Postgres dump    ✓
Upload           ✓
Verification     ✓
Retention        ✓
Memory cleanup   !
```

The UI should show partial failure clearly.

---

## 27.10 Backup principle

The system must assume:

```text
Claude sessions are disposable.
Local runtime state is disposable.
The machine/VPS is disposable.

Git + database backups + secrets are durable.
```

A successful disaster-recovery test should prove that a completely fresh deployment can reconstruct the office without relying on the original server.

---

# 28. Product Principle

The interface should feel like managing a small team, not managing AI prompts.

Prefer concepts such as:

```text
Agent
Task
Room
Meeting
Working
Blocked
Needs your decision
```

over implementation-oriented concepts such as:

```text
Claude process
Prompt
Context window
Tool call
Session ID
LLM request
```

The technical details can exist in advanced/debug views, but the default UI should represent the agents as team members doing work.
