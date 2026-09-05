# Agent Office

A web interface for managing multiple Claude Code agents as if they are people working in a shared office.

This document is the product and technical specification. Section 19 defines the execution runtime, which is the part that must work first.

## Goal

The interface should make it easy to:

- See all agents and their current status.
- See which room each agent is currently in.
- Create meetings with selected agents.
- Hire/create a new agent.
- Fire/remove an agent safely.
- Maintain a global **Skill Catalog** from the UI, synced from Claude Code's own skill directory.
- Assign selected skills from that catalog to each agent.
- Control which MCP servers each agent is allowed to use. MCP servers themselves are configured in the terminal.
- Maintain private persistent memory for each agent.
- Maintain a global **Workspace Memory** automatically available to all current and future agents.
- Create and manage tasks in a Kanban board.
- Assign tasks to agents.
- Automatically move an assigned task from **Backlog** to **In Progress**.
- See what an agent is currently doing by clicking the agent.
- Respond to questions/decision requests from Claude inside the agent side sheet.
- Get a visible notification ping when an agent needs human attention.
- Toggle notification sounds on/off.

Behind the interface, the system must run real Claude Code processes in isolated git worktrees, survive a crash or a restart, and land finished work on a branch. Section 19 defines that runtime. It is the part that must work first.

## Running it

1. `make install` — once per checkout. Creates `.env` from `.env.example` if missing, creates `.venv`, installs the backend and frontend dependencies.
2. `make start` — brings up Postgres, then the backend and the frontend together.

`make start` waits for Postgres to report healthy, then migrates before the backend starts. Every start migrates; there is no flag to skip it. `make migrate` still exists as a way to migrate without starting the backend, not as a way to opt out.

`.env` is created automatically, from `.env.example`, the first time any `make` target runs on a fresh checkout — not only `install` or `db`. GNU Make remakes a missing included file before evaluating whichever target you asked for, and even a dry run (`make -n <target>`) does this for real.

The backend binds `AGENT_OFFICE_API_PORT` (default 8000); set it in `.env` when something else already owns that port. The frontend follows automatically — the Makefile derives `VITE_API_BASE_URL` from it — because the browser, not the backend, resolves that URL. Set `VITE_API_BASE_URL` yourself only when the API is reachable at a different host or port from the browser than it is from this machine.

The repository picker browses `AGENT_OFFICE_BROWSE_ROOT`, which defaults to `$HOME`. It returns directory names only — never file contents, sizes, or anything from inside a file — and a path outside the root is a 404. Widen it only deliberately: `AGENT_OFFICE_API_TOKEN` is unset by default, and reaching the app over an `ssh -L` tunnel means binding to `127.0.0.1` is not the boundary it looks like.

The first `make start` is slow: the backend downloads its embedding model (~50MB) before it serves its first request. That is expected, not a hang.

`make stop` and `make clean` only touch the database (`clean` also deletes its volume). Stop the backend and frontend with Ctrl-C on the terminal running `make start`.

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
queued
working
blocked
```

`queued` means the task is assigned but no runtime slot is free.

Do **not** use "in meeting" as an agent status.

Room/location should be a separate property.

Example:

```ts
agent.status = "working"
agent.roomId = "meeting_auth_architecture"
```

## Suggested agent data shape

```ts
type AgentStatus = "idle" | "queued" | "working" | "blocked"

interface Agent {
  id: string
  name: string
  role: string

  status: AgentStatus

  currentTaskId?: string
  currentSessionId?: string
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

**V2.** Rooms and meetings come after the human-agent execution loop works. See section 25.

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

**V2.** See section 25 for the reasons.

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
│  MCP servers are configured in the terminal.                 │
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
agent.allowedMcpServers = selectedMcpServerNames

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

Skills are reusable instruction/capability packages. There is one global catalog for the workspace/app. Agents receive references to selected skills from this catalog. Every skill is a row in the `skills` table — there is no repository directory backing any of them.

There are two sources of authorship, one table, one read path:

- **Imported skills** are pulled from Claude Code's own skill directory (`~/.claude/skills`, or `AGENT_OFFICE_CLAUDE_SKILLS_DIR` to override) by the "Sync from Claude Code" button. The import reads that directory; it never writes back to it.
- **Custom skills** are created in the web UI and stored entirely in the database.

Both sources are fully editable and deletable from the web UI. Editing an imported skill is not permanent: the next sync overwrites it with whatever `~/.claude/skills` holds for that slug.

## Importing from Claude Code

`GET /skills/available` lists every skill under the Claude Code skills directory by slug and name only — no instructions, no file contents — alongside every already-imported skill, so a directory that has since vanished still appears (`on_disk: false`) instead of becoming unremovable through this screen. `CUSTOM` skills never appear here; they were never in this directory to begin with.

"Sync from Claude Code" opens this list as a checkbox picker, pre-ticked for whatever is already in the catalog. `POST /skills/import` then takes an optional `{"slugs": [...]}`:

| Slug is | In catalog | Result |
|---|---|---|
| ticked | no | a new row is created, `source = "imported"` |
| ticked | yes, `source = "imported"` | name, description and instructions are overwritten |
| ticked | yes, `source = "custom"` | left untouched; reported as skipped |
| unticked | yes, `source = "imported"` | **the row is deleted, along with every agent's assignment to it** |
| unticked | yes, `source = "custom"` | left untouched — a custom skill is never removed by sync |
| ticked | not found on disk | reported as an error; no row is created or changed |

An absent `slugs` key means "every skill currently on disk" — the original, no-removal behaviour — so any direct `POST /skills/import` call keeps working unchanged. Symlinks in the directory are followed: it is almost entirely symlinks into a separate checkout the user already trusts, not a repository directory a stray link could escape, though a symlink that leads back *outside* the skill's own directory is rejected.

Unticking something removes it, so the picker names the cost before it runs: for each skill about to be deleted, it shows which agents are assigned to it and asks for confirmation, the same warning a single skill's own delete button shows. No confirmation is shown when nothing is being removed.

The route returns `{created, updated, removed, unassigned, skipped, errors}` (slugs, plus `unassigned: [{slug, agents}]` naming who lost each removed skill), and the UI shows it after the sync runs.

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

Every skill's dialog is fully editable, whatever its source:

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
│ Instructions                                                 │
│ ┌──────────────────────────────────────────────────────────┐ │
│ │ You are responsible for...                               │ │
│ │                                                          │ │
│ └──────────────────────────────────────────────────────────┘ │
│                                                              │
│                                [Delete Skill] [Save Changes] │
└──────────────────────────────────────────────────────────────┘
```

An imported skill's edits stick until the next "Sync from Claude Code" —
that button overwrites it with whatever the file on disk holds for the slug.

Users can:

- create a custom skill
- edit or delete any skill (imported or custom)
- assign/unassign any skill to agents
- inspect which agents currently use a skill
- sync the catalog from Claude Code's own skill directory

Deleting a skill that is assigned to agents must show the affected agents before confirmation.

Suggested shape:

```ts
interface Skill {
  id: string
  slug: string
  name: string
  description?: string

  source: "imported" | "custom"
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

# 16. MCP Servers (Read-Only in the Web UI)

MCP servers are **not** managed from the web UI.

They are configured once, in the terminal, using the normal Claude Code commands:

```bash
claude mcp add github ...
claude mcp add neon ...
claude mcp list
```

Agent Office reads that configuration and treats it as the global pool.

The web UI can only:

- List the available MCP servers.
- Grant or revoke a server for one agent.
- Show which agents are allowed to use a server.

The web UI must **not**:

- Create an MCP server.
- Edit an MCP server.
- Delete an MCP server.
- Store MCP credentials.
- Test a connection.

Reason: credentials stay in the user's own machine configuration. The application never holds an MCP secret, so there is nothing extra to encrypt, back up, or leak.

## Reading the pool

Read the servers the terminal already configured. Cache the parsed result and refresh it on demand.

```text
~/.claude.json  and  project .mcp.json
        ↓
   parse server list
        ↓
   global MCP pool (read-only)
        ↓
   per-agent allow list (stored in Postgres)
```

Show a `[Refresh]` action, not an `[Add]` action.

## MCP Servers View

```text
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│ MCP SERVERS                          Managed in the terminal · read only     [Refresh]   │
│                                                                                          │
│ ┌──────────────────────────────────────────────────────────────────────────────────────┐ │
│ │ github                                                     http · 4 agents           │ │
│ └──────────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                          │
│ ┌──────────────────────────────────────────────────────────────────────────────────────┐ │
│ │ neon                                                       http · 2 agents           │ │
│ └──────────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                          │
│ ┌──────────────────────────────────────────────────────────────────────────────────────┐ │
│ │ slack                                                      stdio · 0 agents          │ │
│ └──────────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                          │
│ To add or remove a server, run `claude mcp add` in the terminal, then press Refresh.     │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

## Per-agent access

Only the allow list is application state.

```ts
interface McpServerRef {
  name: string          // key from the terminal configuration
  transport: "stdio" | "http" | "sse"
}

interface AgentMcpPermission {
  agentId: string
  mcpServerName: string
  allowed: boolean
}
```

An agent never gains access to a newly configured server automatically. Access is explicit per agent.

## Enforcement at spawn time

Write a per-agent MCP configuration file into the agent's runtime directory. Pass it to the process and forbid every other source.

```bash
claude --mcp-config .agent-office/runtime/<agent>/mcp.json \
       --strict-mcp-config \
       ...
```

`--strict-mcp-config` makes the passed file the only source. Without it the process inherits every server the user configured, and the per-agent allow list means nothing.

If a stored allow list names a server that no longer exists in the terminal configuration, mark it `missing` in the UI. Do not fail the spawn.

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
                                              │ MCP list is read-only. Configure in terminal.│
                                              │                                             │
                                              │                              [Save Changes] │
                                              └─────────────────────────────────────────────┘
```

Changes apply to future agent turns/runtime launches.

If an MCP is removed from an agent while a task is running, revoke it for subsequent tool calls as soon as the runtime supports safe dynamic refresh; otherwise restart/refresh the agent runtime at the next safe boundary.

---

# 19. Execution Runtime

This is the core of the system. Everything else is a view over it.

An agent is a persistent database record. A Claude Code session is disposable. One agent uses many sessions over its life.

```text
Agent  (persistent)
├── identity, role, instructions
├── private memory
├── assigned skills
├── allowed MCP servers
│
└── Runtime  (disposable)
    ├── git worktree
    ├── task branch
    ├── working directory
    ├── OS process
    ├── Claude session id
    └── process status
```

## 19.1 Three layers

```text
PRODUCT UI          agents, tasks, decisions, notifications
      ↓
ORCHESTRATION CORE  scheduler, lifecycle, decision routing, context builder
      ↓
EXECUTION RUNTIME   worktree, branch, process, session, streaming
```

Keep the UI layer free of process handling. Keep the runtime layer free of product concepts.

## 19.2 How Claude is started

Start the Claude Code CLI as a child process in headless streaming mode.

```bash
claude \
  --print \
  --output-format stream-json \
  --input-format stream-json \
  --include-partial-messages \
  --verbose \
  --model <model> \
  --permission-mode <mode> \
  --mcp-config <runtime>/mcp.json \
  --strict-mcp-config
```

Resume an existing session with:

```bash
claude --resume <claude_session_id> ...
```

Prompts go to stdin as JSON. Events come from stdout as one JSON object per line.

This is the same approach Vibe Kanban uses, verified in its shipped binary and its SQLite schema. Prefer it over the Claude Agent SDK for the first version: the CLI is the surface the user already runs, and its session files on disk are inspectable when something goes wrong.

## 19.3 Git isolation

Two agents must never share a working tree.

```text
repository
│
├── developer working tree
│
├── .agent-office/worktrees/
│   ├── TASK-142/        branch agent-office/TASK-142
│   ├── TASK-143/        branch agent-office/TASK-143
│   └── TASK-146/        branch agent-office/TASK-146
│
└── .agent-office/config/   branch agent-office/config
    └── .agent-office/skills/
```

One worktree per **task**, not per agent. A task is the unit of work, it holds the branch, and it outlives the agent that started it. If the agent is fired, the worktree and branch stay, and another agent attaches to them.

The configuration worktree is separate again. Skill files are written and committed there. Never touch the developer's index. Never touch an agent's index.

```bash
git add .agent-office/skills/    # only these paths
```

Never `git add -A`.

## 19.4 What survives

```text
Claude session dies, rotates, or the machine reboots
        ↓
worktree survives
branch survives
uncommitted files survive
task survives
memory survives
        ↓
a new Claude session attaches to the same worktree
```

## 19.5 Session persistence

Persist the Claude session id. Without it a crash loses the conversation and the work restarts from nothing.

Read the id from the first `stream-json` event of a run and write it immediately, not at the end.

```ts
interface AgentSession {
  id: string
  agentId: string
  workspaceId: string        // the task worktree
  claudeSessionId?: string   // from the runtime, may be null before the first event
  cwd: string
  boundVia: "spawn" | "resume" | "manual"
  status: "running" | "completed" | "failed" | "killed"
  exitCode?: number
  startedAt: string
  completedAt?: string
}
```

Record one row per **run**, not one row per agent. A task that is answered, resumed, and answered again produces several runs against one Claude session id.

Also store, per run:

```text
before_head_commit
after_head_commit
```

This gives an exact diff for the run, and it survives the process.

On startup, reconcile: any session row marked `running` whose process is gone becomes `failed`. Then offer resume.

## 19.6 The execution loop

```text
User assigns task
        ↓
Scheduler checks concurrency slots
        ↓
Create or reuse the task worktree and branch
        ↓
Build context
        ↓
Spawn or resume Claude Code
        ↓
Persist the Claude session id on the first event
        ↓
Stream events → activity, files, status
        ↓
        ├── finished → commit → task Done
        │
        └── needs a human
                ↓
          decision_required in Postgres
                ↓
          WebSocket → bell → UI
                ↓
          human answers
                ↓
          write the answer to the same process stdin,
          or resume the session with the answer
                ↓
          Claude continues
```

## 19.7 Asking the human

`decision_required` is not a native Claude Code concept. Build it.

Give every agent one internal MCP tool:

```text
ask_human(question, options?, urgency)
```

The tool call writes a `DecisionRequest` row, sets the agent to `blocked`, raises an attention event, and does not return until the human answers. The agent is then genuinely waiting, and the whole loop stays inside one session.

The permission prompt is the second source. When the runtime asks to use a tool the agent is not allowed to use, surface it in the same inbox.

## 19.8 Concurrency

```text
interface WorkspaceRuntimePolicy {
  maxConcurrentAgents: number
  idleRuntimeTimeoutMinutes: number
}

interface AgentRuntimePolicy {
  model: string
  maxTurnsPerTask?: number
  permissionMode: string
}
```

An idle agent runs no process and costs nothing. Start a process only when there is work.

If more tasks are assigned than there are slots, agents queue.

```text
WORKING   Alex, Maya, Sam
QUEUED    Emma, Jordan
```

Add `queued` to the agent statuses:

```ts
type AgentStatus = "idle" | "queued" | "working" | "blocked"
```

Room stays a separate property.

Do not implement dollar budgets. Concurrency and turn limits are enough, and they are the only limits that can be enforced before the money is spent.

## 19.9 Landing the work

A task is not Done because Claude stopped talking.

```text
Claude finishes
        ↓
commit on the task branch
        ↓
push
        ↓
open a pull request   (or merge directly, per project setting)
        ↓
record the merge
        ↓
task Done
```

Store the result:

```ts
interface TaskMerge {
  taskId: string
  type: "direct" | "pr"
  targetBranch: string
  mergeCommit?: string
  prNumber?: number
  prUrl?: string
  prStatus?: "open" | "merged" | "closed"
}
```

A Done task with an orphan branch is an unfinished task. Show the branch and the pull request in the task detail view.

---

# 20. Recommended Overall Interaction

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

# 21. Core Entity Relationships

```text
Workspace
│
├── Agents
│     │
│     ├── currentTask
│     ├── room
│     └── current Session (disposable)
│
├── Tasks
│     │
│     ├── assigned Agent
│     ├── worktree + branch
│     ├── Sessions
│     │     └── Runs (process, exit code, before/after commit)
│     └── Merge (direct or pull request)
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
├── MCP pool (read-only)
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

# 22. Suggested Frontend State Model

```ts
interface WorkspaceState {
  view: "rooms" | "tasks"

  agents: Agent[]
  tasks: Task[]
  rooms: Room[]
  meetings: Meeting[]

  skills: Skill[]
  mcpServers: McpServerRef[]

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

  worktreePath?: string
  branch?: string
  merge?: TaskMerge

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

# 23. Important Behavior Rules

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

A skill exists once in the database-backed catalog.

```text
Skill Catalog
    ↓ assign
Agent
```

Do not duplicate the skill contents into each agent record.

### Rule 10 — MCP servers are terminal-managed; access is per agent

A server configured in the terminal does not grant it to all agents.

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

### Rule 14 — One worktree per task

Two agents never share a working tree. The worktree and the branch belong to the task, not to the agent, and survive the agent being fired.

### Rule 15 — The Claude session id is persisted immediately

Write it on the first event of a run, not at the end. Without it a crash loses the conversation.

### Rule 16 — An idle agent runs no process

A process starts only when there is work. Concurrency is limited by slots, and extra agents queue.

### Rule 17 — Done means landed

A task is Done only when its branch is merged, or a pull request is open and recorded. A Done task with an orphan branch is unfinished.

### Rule 18 — MCP servers are configured in the terminal

The web UI lists them and grants them per agent. It never creates, edits or deletes one, and it never stores a credential.


---

# 24. Suggested Realtime Events

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

session.started
session.resumed
session.ended
runtime.event
worktree.created
task.committed
task.pr_opened

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

mcp.pool_refreshed
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

# 25. Release Scope

The first version must prove one complete loop, end to end, reliably. Nothing else matters until it works.

## V1 — the human-agent execution loop

```text
 1. Hire an agent
 2. Fire an agent
 3. Create a task
 4. Assign the task
 5. Create the task worktree and branch
 6. Spawn Claude Code
 7. Persist the Claude session id
 8. Stream status and activity into the UI
 9. Claude asks the human a question
10. Agent and task become blocked
11. Bell, inbox, sound
12. Human answers in the side sheet
13. Claude resumes in the same session
14. Claude finishes
15. Commit, push, pull request
16. Task becomes Done
```

Plus the minimum surface that loop needs:

- Agent sidebar with idle / queued / working / blocked
- Agent side sheet, Overview tab only
- Tasks Kanban with Backlog, In Progress, Blocked, Done
- Concurrency limit and a queue
- Realtime UI updates
- Crash recovery: reconcile orphan sessions on startup, then resume

## V1.1

```text
Skill Catalog
Per-agent skill assignment
Read-only MCP list and per-agent access
Basic private agent memory
```

## V1.2

```text
Workspace Memory
Memory retrieval
Context builder
Session checkpointing
Session rotation
```

## V2

```text
Rooms
Meetings
Agent-to-agent communication
Meeting summaries
```

Meetings look simple in the UI and are expensive in the runtime. They raise questions the first version cannot answer: who speaks first, how many rounds, who decides the meeting is over, can agents use tools while talking, does a meeting interrupt a running task, how does the meeting result reach the task context, how are conversation loops stopped.

Make `human ↔ agent ↔ task` reliable first. Build `agent ↔ agent` on top of it.

## Later

```text
Task dependencies
Automatic code review
Multiple repositories
Advanced scheduling
Cost analytics
```

## Not in any near version

- multiple concurrent tasks per agent
- agent performance scoring
- dollar budgets
- room permissions
- workflow builders

---

# 26. Final Desktop Mock-up

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


# 27. Implementation Plan

Build from the runtime outwards. The runtime, the worktree isolation and the human decision round trip are the foundation. Everything else sits on top.

## Phase 1 — Core domain and persistence

Implement persistent entities for:

```text
Agent
Task
TaskWorktree
AgentSession
ExecutionRun
DecisionRequest
AttentionEvent
TaskMerge

Skill
AgentSkillAssignment

AgentMcpPermission

WorkspaceMemory
MemoryRecord
AgentCheckpoint

Room
Meeting
```

`Room` and `Meeting` are V2. Define them last, or leave them out of the first migration.

Create clear service boundaries for:

```text
RuntimeService      spawn, resume, stream, kill
WorktreeService     create, reuse, remove, commit, push
SchedulerService    slots, queue
AgentService
TaskService
DecisionService
AttentionService
SkillService
McpService
MemoryService
MeetingService      (V2)
```

Write `RuntimeService` first and prove it from a script, before any UI exists.

## Phase 2 — Execution runtime

Build this before any UI. Prove it from a script.

1. Create a git worktree and branch for a task.
2. Spawn the Claude Code CLI in that worktree, headless, streaming.
3. Read the Claude session id from the first event and persist it.
4. Parse the event stream into activity, files touched, and status.
5. Record `before_head_commit` and `after_head_commit` for the run.
6. Kill the process safely.
7. Resume the same session with `--resume`.
8. On startup, mark orphan `running` rows as `failed`.

Write the per-agent `mcp.json` here, and always pass `--strict-mcp-config`.

## Phase 3 — Agent lifecycle

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
6. Leave the agent idle with no process running.

Firing must:

1. Stop the active runtime safely.
2. Handle unfinished tasks.
3. Archive private memory by default.
4. Preserve task history, decisions, audit events, branches and commits.

Firing must not delete a task worktree or branch. The work belongs to the task, not the agent.

## Phase 4 — Task loop and landing

```text
Backlog
  ↓ assign
In Progress        worktree + branch + process
  ↓ needs a human
Blocked
  ↓ answer
In Progress
  ↓ finished
commit → push → pull request
  ↓
Done
```

Add the scheduler here: a concurrency limit, a queue, and the `queued` status.

A task is Done only when its branch has landed or a pull request is open and recorded.

## Phase 5 — Human attention loop

Implement:

```text
The ask_human MCP tool
Decision requests
Agent blockers
Bell count
Attention inbox
Sound toggle
One sound per new event
Deep link to the correct side sheet
Answer routed back into the same session
```

## Phase 6 — Skills and MCP access

Implement the repository-backed Skill Catalog in its own configuration worktree.

Implement the read-only MCP pool: parse the terminal configuration, store only the per-agent allow list, and write a per-agent `mcp.json` at spawn time.

These are global resources. Agent records store references, never copies.

## Phase 7 — Memory system

This is a first-class part of the product, not a later chat-history feature.

Implement **per-agent private memory**:

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
+ relevant task state
+ recent messages
```

Do not equate Claude session history with memory.

## Phase 8 — Context and session rotation

Track approximate context usage.

Before a session becomes too large or noisy:

```text
checkpoint
→ extract durable memories
→ persist task and runtime state
→ archive the session
→ start a fresh session in the same worktree
→ rebuild context
```

The persistent agent, the worktree and the branch all survive the replacement of the Claude session.

## Phase 9 — Rooms and meetings (V2)

Implement Main Room, temporary meeting rooms, participant movement, transcript storage, decision and action-item extraction, and the return of participants to the Main Room.

Do not start this before Phases 2 to 5 are reliable.

---

# 28. Backup, Persistence & Disaster Recovery

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
├── MCP permissions
└── audit/activity state
```

## 28.1 Skill persistence

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

## 28.2 Daily repository sync job

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

## 28.3 PostgreSQL backups

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

## 28.4 PostgreSQL dump job

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

## 28.5 Backup retention

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

## 28.6 Recovery target

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

## 28.7 Secrets backup

Agent Office stores no MCP credential.

MCP servers are configured in the terminal, so their credentials live in the user's own Claude configuration and in the operating system, outside this application.

Back up:

```text
~/.claude.json
project .mcp.json
```

with the machine's normal file backup, or re-create them with `claude mcp add` after a rebuild.

The database holds only names and per-agent allow lists. A restore therefore needs:

```text
database
+
terminal MCP configuration
```

If the terminal configuration is missing after a restore, the affected agents show their MCP servers as `missing` and keep working without them.

---

## 28.8 Backup UI

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

## 28.9 Scheduled maintenance job

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

## 28.10 Backup principle

The system must assume:

```text
Claude sessions are disposable.
Local runtime state is disposable.
The machine/VPS is disposable.

Git + database backups + secrets are durable.
```

A successful disaster-recovery test should prove that a completely fresh deployment can reconstruct the office without relying on the original server.

---

# 30. Repository Structure

The stack matches the other projects in this workspace: FastAPI, SQLAlchemy, Alembic, asyncpg and Redis on the backend; Vue 3, Vite, Pinia and Tailwind on the frontend.

```text
ai-orchestrator/
│
├── backend/
│   └── api/
│       ├── app.py                     FastAPI application, routers, WebSocket mount
│       ├── pyproject.toml
│       ├── alembic.ini
│       ├── migrations/                Alembic revisions
│       │
│       ├── models/                    SQLAlchemy tables, one file per aggregate
│       │   ├── agent.py
│       │   ├── task.py
│       │   ├── worktree.py
│       │   ├── session.py             AgentSession + ExecutionRun
│       │   ├── decision.py
│       │   ├── attention.py
│       │   ├── skill.py
│       │   ├── mcp.py                 per-agent allow list only
│       │   ├── memory.py              MemoryRecord + WorkspaceMemory
│       │   └── merge.py
│       │
│       ├── routers/                   HTTP surface, thin, no logic
│       │   ├── agents.py
│       │   ├── tasks.py
│       │   ├── decisions.py
│       │   ├── skills.py
│       │   ├── mcp.py
│       │   ├── memory.py
│       │   └── events.py              WebSocket /ws
│       │
│       ├── services/                  business logic, no HTTP, no process handling
│       │   ├── agent_service.py
│       │   ├── task_service.py
│       │   ├── scheduler_service.py   slots, queue, promotion
│       │   ├── decision_service.py
│       │   ├── attention_service.py
│       │   ├── skill_service.py
│       │   ├── mcp_service.py
│       │   └── memory/
│       │       ├── store.py           write, supersede, archive
│       │       ├── retrieval.py       hybrid search
│       │       ├── extraction.py      turn a run into candidate memories
│       │       ├── consolidation.py   dedupe and supersede
│       │       └── context_builder.py assemble the prompt context
│       │
│       ├── runtime/                   the only place that touches processes and git
│       │   ├── runtime_service.py     spawn, resume, kill, reconcile
│       │   ├── process.py             asyncio subprocess, stdin and stdout
│       │   ├── stream_parser.py       stream-json line to domain event
│       │   ├── worktree.py            create, reuse, commit, push, remove
│       │   ├── mcp_config.py          write per-agent mcp.json
│       │   ├── prompt.py              render the system prompt
│       │   └── ask_human_mcp.py       the internal MCP server, one tool
│       │
│       ├── events/
│       │   ├── bus.py                 Redis pub/sub fan-out
│       │   └── schema.py              event payloads, shared with the frontend
│       │
│       ├── workers/                   taskiq
│       │   ├── run_agent.py           owns one Claude process for its lifetime
│       │   ├── memory_jobs.py         extraction and consolidation
│       │   └── backup_jobs.py         skill sync, pg_dump, retention
│       │
│       └── tests/
│
├── frontend/
│   └── app/
│       ├── src/
│       │   ├── views/                 RoomsView, TasksView, SkillsView, McpView, MemoryView
│       │   ├── components/
│       │   │   ├── agent/             AgentCard, AgentSheet, DecisionPanel
│       │   │   ├── task/              KanbanBoard, TaskCard, TaskDetail
│       │   │   └── shell/             Header, Sidebar, NotificationInbox
│       │   ├── stores/                Pinia: agents, tasks, memory, attention
│       │   ├── realtime/socket.ts     one WebSocket, dispatches into the stores
│       │   └── api/                   generated client
│       └── package.json
│
├── .agent-office/                     runtime and configuration, inside the repo
│   ├── skills/                        the Skill Catalog, git is the source of truth
│   ├── worktrees/
│   │   ├── TASK-142/                  branch agent-office/TASK-142
│   │   └── TASK-143/
│   ├── runtime/
│   │   └── <agent-id>/
│   │       ├── mcp.json               written at spawn, allow list only
│   │       └── logs/
│   └── config/                        the configuration worktree, branch agent-office/config
│
└── devops/
    ├── docker-compose.yml             postgres with pgvector, redis
    └── render.yaml
```

Three directories carry the rules:

- `routers/` has no logic. It validates input and calls a service.
- `services/` has no processes and no git. It is pure business logic over the database.
- `runtime/` is the only code that spawns a process, parses a stream, or touches git.

---

# 31. How the Business Logic Works

## 31.1 Assigning a task

```text
POST /tasks/{id}/assign {agentId}
        │
routers/tasks.py
        │
task_service.assign()
        ├── task.assigneeId = agent
        ├── task.status = in_progress
        └── scheduler_service.request_slot(agent)
                │
                ├── no free slot  → agent.status = queued, stop here
                │
                └── free slot     → enqueue workers/run_agent
                                        │
                          ┌─────────────┴──────────────┐
                          │  worker: run_agent          │
                          │                             │
                          │ 1 worktree.ensure(task)     │
                          │ 2 mcp_config.write(agent)   │
                          │ 3 context_builder.build()   │
                          │ 4 process.spawn()           │
                          │ 5 read stdout line by line  │
                          └─────────────┬───────────────┘
                                        │
                                  events/bus.py
                                        │
                                   WebSocket
                                        │
                                    Pinia store
                                        │
                                    agent card
```

One worker owns one process for its whole life. The worker is the only writer of that session's rows. Nothing else may write to that process's stdin.

## 31.2 The event stream

`claude --print --output-format stream-json` writes one JSON object per line. `stream_parser.py` turns each line into a domain event and nothing else.

```text
stdout line
     │
     ├── init            → persist claudeSessionId immediately, then everything else
     ├── assistant text  → activity entry, agent message
     ├── tool_use        → activity entry; Edit and Write also record the file
     ├── tool_result     → activity entry
     ├── result          → run finished, exit code, token usage
     └── unknown         → log and ignore, never crash the run
```

Every event is written to Postgres first, then published to Redis. The WebSocket layer only reads Redis. A browser that reconnects replays from the database, so a dropped socket loses nothing.

## 31.3 The decision round trip

```text
Claude calls  ask_human(question, options)
        │
runtime/ask_human_mcp.py                     the tool does not return yet
        │
decision_service.create()
        ├── DecisionRequest row              status = open
        ├── agent.status = blocked
        ├── task.status = blocked
        └── attention_service.raise()        bell + one sound
        │
        ▼
   the human answers in the side sheet
        │
POST /decisions/{id}/answer
        │
decision_service.answer()
        ├── DecisionRequest.status = answered
        └── release the waiting tool call
        │
        ▼
the tool returns the answer to Claude
agent.status = working, task.status = in_progress
Claude continues in the same session
```

The tool call is what blocks. The process stays alive, so no context is rebuilt and no tokens are re-paid.

If the process died while waiting, the answer is delivered by resuming instead:

```bash
claude --resume <claudeSessionId> --print ...
```

with the answer as the next prompt. The stored session id is what makes this possible.

## 31.4 Finishing

```text
result event, exit code 0
        │
worktree.commit(task)
worktree.push()
        │
        ├── project setting = pr      → open a pull request, store number and url
        └── project setting = direct  → merge into the target branch, store the commit
        │
task.status = done
agent.status = idle
scheduler_service.release_slot()   → the first queued agent starts
```

A non-zero exit code sets the run to `failed` and raises an attention event. The worktree and the branch are kept. The human decides whether to retry or discard.

## 31.5 Crash recovery

On startup:

```text
for every run row with status = running:
    is the pid alive?
        yes → re-attach the log reader
        no  → status = failed, raise an attention event, offer resume
```

The worktree, the branch, the uncommitted files, the task and the memories are all still there. Resume starts a new run against the stored `claudeSessionId`.

---

# 32. How Memory Is Managed

Memory is database state. The Claude context window is temporary working space. The two are never the same thing.

```text
                    ┌──────────────────────────┐
   write path       │      memory_records      │      read path
                    │  (Postgres + pgvector)   │
                    └────────────┬─────────────┘
                                 │
  run transcript                 │                 context_builder
        │                        │                        │
   extraction.py ────────────────┤                        │
        │                        │                 retrieval.py
   consolidation.py ─────────────┤                        │
        │                        │                        │
   human edits in the UI ────────┘                        ▼
                                                    system prompt
```

## 32.1 One table

```sql
CREATE TABLE memory_records (
  id             uuid PRIMARY KEY,
  scope          text NOT NULL,           -- 'workspace' | 'agent' | 'task'
  agent_id       uuid NULL,               -- null when scope = workspace
  task_id        uuid NULL,
  type           text NOT NULL,           -- fact, decision, preference, lesson, ...
  content        text NOT NULL,
  embedding      vector(1536),
  importance     real NOT NULL DEFAULT 0.5,
  pinned         boolean NOT NULL DEFAULT false,
  status         text NOT NULL DEFAULT 'active',   -- active | superseded | archived
  superseded_by  uuid NULL REFERENCES memory_records(id),
  source_type    text,                    -- human | agent | task | system
  source_id      text,
  created_at     timestamptz NOT NULL DEFAULT now(),
  last_accessed_at timestamptz
);
```

Workspace memory and private memory are the same table with a different `scope`. That keeps one retrieval query, one editor, one backup.

## 32.2 The write path

Memory is written at three moments, never continuously.

```text
1. End of a run
   The transcript goes to a cheap model with a strict schema:
   "Return only durable facts. No task narration."
        ↓
   candidate memories
        ↓
   consolidation.py
        ├── embed each candidate
        ├── nearest active memory for this agent
        │     similarity > 0.92  → update the existing record, do not insert
        │     contradiction      → new record, old one status = superseded
        │     otherwise          → insert
        └── cap: at most N new memories per run

2. Session rotation
   The checkpoint fields (decisions, discoveries, blockers, files) become
   memories directly. No model pass, they are already structured.

3. Human edit
   Anything typed in the UI is source_type = human and importance = 1.0.
   A human memory is never superseded automatically.
```

Nothing writes memory during a run. A run that fails halfway leaves no half-truths behind.

## 32.3 The read path

```text
context_builder.build(agent, task)
        │
        ├── agent identity and role instructions
        ├── assigned skills                       (file contents, not summaries)
        ├── allowed MCP capabilities              (names only)
        │
        ├── pinned workspace memory               ALWAYS, all of it
        ├── pinned private memory                 ALWAYS, all of it
        │
        ├── retrieval.py(query = task title + description + recent activity)
        │        │
        │        ├── vector search over active records for this agent + workspace
        │        ├── score = 0.6·similarity + 0.25·importance + 0.15·recency
        │        ├── drop status != active
        │        └── take until the memory token budget is spent
        │
        ├── current task and its state
        └── the last N activity entries
```

Two hard rules:

- Never inject the whole store. Pinned plus top-k only.
- Pinned memory has its own budget, separate from retrieved memory, so a large retrieval can never push out a critical rule.

Every returned record gets `last_accessed_at` updated. That feeds the recency term and shows the human which memories are actually used.

## 32.4 Consolidation

A stale memory is worse than a missing one.

```text
"We use Redis queues."                      → superseded
"We are migrating away from Redis."         → superseded
"Job queues use Postgres. Redis is not used for queues."   → active
```

Retrieval reads `status = 'active'` only. Superseded records stay in the table for provenance and are visible in the UI history, never in a prompt.

A nightly job re-embeds recent records, finds contradiction clusters, and proposes supersessions. It proposes. It does not apply them without a human, because a wrong supersession silently deletes knowledge.

## 32.5 Where memory lives per agent

```text
Agent Alex
├── private memory      scope = agent, agent_id = alex        184 records
├── workspace memory    scope = workspace                     shared, read only for the agent
└── task memory         scope = task, task_id = TASK-142       dropped when the task is archived
```

A new hire gets workspace memory on the first run, with no assignment step, because the retrieval query already includes `scope = 'workspace'`.

Firing an agent sets its private records to `archived`. They stop being retrieved and stay recoverable.

---

# 33. Product Principle

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
