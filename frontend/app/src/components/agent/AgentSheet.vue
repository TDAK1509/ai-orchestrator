<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue"
import type { Agent, AgentEffort } from "../../api/types"
import { useActivityStore } from "../../stores/activity"
import { useAgentsStore } from "../../stores/agents"
import { useAttentionStore } from "../../stores/attention"
import { useMemoryStore } from "../../stores/memory"
import { useRepositoriesStore } from "../../stores/repositories"
import { useSkillsStore } from "../../stores/skills"
import { useTasksStore } from "../../stores/tasks"
import { useTeamsStore } from "../../stores/teams"
import AssignSkillsDialog from "./AssignSkillsDialog.vue"
import DecisionPanel from "./DecisionPanel.vue"
import NextRunNotice from "./NextRunNotice.vue"

const props = defineProps<{ agent: Agent }>()
defineEmits<{ close: [] }>()

const tasks = useTasksStore()
const agentsStore = useAgentsStore()
const attention = useAttentionStore()
const activity = useActivityStore()
const memory = useMemoryStore()
const teams = useTeamsStore()
const repositories = useRepositoriesStore()
const skills = useSkillsStore()
const confirmingFire = ref(false)

const currentTask = computed(() => (props.agent.current_task_id ? tasks.byId(props.agent.current_task_id) : undefined))
const currentTaskRepository = computed(() => (currentTask.value?.repository_id ? repositories.byId(currentTask.value.repository_id) : undefined))
const decision = computed(() => attention.decisionForAgent(props.agent.id))
const recentActivity = computed(() => activity.forAgent(props.agent.id).slice().reverse())
const agentMemories = computed(() => memory.agentMemoriesByAgentId[props.agent.id] ?? [])
const team = computed(() => (props.agent.team_id ? teams.byId(props.agent.team_id) : undefined))

onMounted(() => {
  memory.fetchAgentMemories(props.agent.id)
  skills.fetchAgentSkills(props.agent.id)
  window.addEventListener("keydown", handleKeydown)
})

onUnmounted(() => {
  window.removeEventListener("keydown", handleKeydown)
})

function handleKeydown(event: KeyboardEvent): void {
  if (event.key !== "Escape" || props.agent.status !== "working" || isEditableTarget(event.target)) return
  stopAgent()
}

function isEditableTarget(target: EventTarget | null): boolean {
  return target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement
}

async function confirmFire(): Promise<void> {
  await agentsStore.fireAgent(props.agent.id)
  confirmingFire.value = false
}

async function stopAgent(): Promise<void> {
  await agentsStore.stopAgent(props.agent.id)
}

// B4: README 18 specifies [Overview] [Memory] [Skills & MCP] for a future config tab this sheet doesn't
// build yet -- Activity takes that third slot until Skills & MCP has content of its own to show.
const TABS = ["Overview", "Activity", "Memory"] as const
const activeTab = ref<(typeof TABS)[number]>("Overview")

const MODEL_OPTIONS = ["claude-opus-5", "claude-sonnet-5", "claude-haiku-4-5", "claude-fable-5-1"]
const EFFORT_OPTIONS = ["low", "medium", "high", "xhigh", "max"]
const editingRuntime = ref(false)
const modelDraft = ref("")
const effortDraft = ref<AgentEffort | "">("")
const savingRuntime = ref(false)

function startEditingRuntime(): void {
  modelDraft.value = props.agent.model ?? ""
  effortDraft.value = props.agent.effort ?? ""
  editingRuntime.value = true
}

async function saveRuntime(): Promise<void> {
  savingRuntime.value = true
  try {
    await agentsStore.editAgent(props.agent.id, { model: modelDraft.value || null, effort: effortDraft.value || null })
    editingRuntime.value = false
  } finally {
    savingRuntime.value = false
  }
}

const editingIdentity = ref(false)
const nameDraft = ref("")
const roleDraft = ref("")
const instructionsDraft = ref("")
const savingIdentity = ref(false)
const identityError = ref("")

function startEditingIdentity(): void {
  nameDraft.value = props.agent.name
  roleDraft.value = props.agent.role
  instructionsDraft.value = props.agent.instructions
  identityError.value = ""
  editingIdentity.value = true
}

async function saveIdentity(): Promise<void> {
  savingIdentity.value = true
  identityError.value = ""
  try {
    await agentsStore.editAgent(props.agent.id, { name: nameDraft.value, role: roleDraft.value, instructions: instructionsDraft.value })
    editingIdentity.value = false
  } catch (err) {
    identityError.value = err instanceof Error ? err.message : "Could not save, try again"
  } finally {
    savingIdentity.value = false
  }
}

const agentSkills = computed(() => skills.skillsByAgentId[props.agent.id] ?? [])
const showAssignSkills = ref(false)

async function removeSkill(skillId: string): Promise<void> {
  await skills.unassignFromAgent(skillId, props.agent.id)
  await skills.fetchAgentSkills(props.agent.id)
}

const messageDraft = ref("")
const sendingMessage = ref(false)

async function sendMessage(): Promise<void> {
  const content = messageDraft.value.trim()
  if (!content) return
  sendingMessage.value = true
  try {
    await agentsStore.sendMessage(props.agent.id, content)
    messageDraft.value = ""
  } finally {
    sendingMessage.value = false
  }
}
</script>

<template>
  <div class="fixed inset-y-0 right-0 z-20 w-96 overflow-y-auto border-l border-gray-200 bg-white p-4 shadow-xl">
    <div class="flex items-start justify-between">
      <div>
        <h2 class="text-lg font-semibold">{{ agent.name }}</h2>
        <p class="text-sm text-gray-500">{{ agent.role }}</p>
      </div>
      <button class="text-gray-400 hover:text-gray-600" @click="$emit('close')">✕</button>
    </div>

    <div class="mt-2 flex items-center justify-between">
      <p class="text-sm font-medium uppercase tracking-wide text-gray-500">{{ agent.status }}</p>
      <button v-if="agent.status === 'working'" class="text-sm text-red-600" title="Kills the current run; the task will need resuming" @click="stopAgent">
        Stop
      </button>
    </div>
    <p v-if="team" class="mt-1 text-sm text-gray-500">Team: {{ team.name }}</p>

    <DecisionPanel v-if="decision" :decision="decision" class="mt-4" />

    <div class="mt-4 flex gap-4 border-b border-gray-200 text-sm">
      <button
        v-for="tab in TABS"
        :key="tab"
        class="border-b-2 px-1 pb-2 -mb-px"
        :class="activeTab === tab ? 'border-blue-600 font-medium text-blue-600' : 'border-transparent text-gray-500'"
        @click="activeTab = tab"
      >
        {{ tab }}
      </button>
    </div>

    <div v-if="activeTab === 'Overview'" class="pt-4">
      <div class="border-b border-gray-100 pb-4">
        <div class="flex items-center justify-between">
          <h3 class="text-xs font-semibold uppercase tracking-wide text-gray-400">Job Description</h3>
          <button v-if="!editingIdentity" class="text-sm text-blue-600" @click="startEditingIdentity">Edit</button>
        </div>

        <div v-if="!editingIdentity" class="mt-2">
          <p v-if="agent.instructions" class="whitespace-pre-wrap text-sm text-gray-700">{{ agent.instructions }}</p>
          <p v-else class="text-sm text-gray-400">No instructions set. Add some to give this agent working rules.</p>
        </div>
        <div v-else class="mt-2 space-y-2">
          <div>
            <label class="block text-xs font-medium text-gray-500">Name</label>
            <input v-model="nameDraft" class="mt-1 w-full rounded border border-gray-300 px-2 py-1 text-sm" />
          </div>
          <div>
            <label class="block text-xs font-medium text-gray-500">Role</label>
            <input v-model="roleDraft" class="mt-1 w-full rounded border border-gray-300 px-2 py-1 text-sm" />
          </div>
          <div>
            <label class="block text-xs font-medium text-gray-500">Instructions</label>
            <textarea
              v-model="instructionsDraft"
              rows="8"
              class="mt-1 w-full rounded border border-gray-300 px-2 py-1 font-mono text-sm"
              placeholder="This agent's job description and working rules..."
            />
          </div>
          <NextRunNotice />
          <p class="text-xs text-gray-400">A rule for several agents belongs in a skill, not copied into each agent's instructions.</p>
          <p v-if="identityError" class="text-xs text-red-600">{{ identityError }}</p>
          <div class="flex gap-2">
            <button
              class="rounded bg-blue-600 px-2 py-1 text-sm text-white disabled:opacity-50"
              :disabled="savingIdentity || !nameDraft.trim() || !roleDraft.trim()"
              @click="saveIdentity"
            >
              Save
            </button>
            <button class="rounded border border-gray-300 px-2 py-1 text-sm" @click="editingIdentity = false">Cancel</button>
          </div>
        </div>
      </div>

      <div class="border-b border-gray-100 py-4">
        <div class="flex items-center justify-between">
          <h3 class="text-xs font-semibold uppercase tracking-wide text-gray-400">Skills</h3>
          <button class="text-sm text-blue-600" @click="showAssignSkills = true">Add</button>
        </div>
        <div v-if="agentSkills.length" class="mt-2 flex flex-wrap gap-1.5">
          <span
            v-for="skill in agentSkills"
            :key="skill.id"
            class="flex items-center gap-1 rounded-full bg-gray-100 py-0.5 pl-2 pr-1 text-xs text-gray-700"
          >
            {{ skill.name }}
            <button class="text-gray-400 hover:text-gray-600" title="Unassign" @click="removeSkill(skill.id)">✕</button>
          </span>
        </div>
        <p v-else class="mt-2 text-sm text-gray-400">No skills assigned.</p>
        <NextRunNotice class="mt-2" />
        <AssignSkillsDialog v-if="showAssignSkills" :agent="agent" @close="showAssignSkills = false" />
      </div>

      <div v-if="currentTask" class="mt-4">
        <h3 class="text-xs font-semibold uppercase tracking-wide text-gray-400">Current Task</h3>
        <p class="mt-1 font-medium">{{ currentTask.title }}</p>
        <p class="mt-1 text-sm text-gray-600">{{ currentTask.description }}</p>
        <p class="mt-1 text-xs text-gray-400">Repository: {{ currentTaskRepository?.name ?? "Workspace default" }}</p>
      </div>

      <div class="mt-6 border-t border-gray-100 pt-4">
        <h3 class="text-xs font-semibold uppercase tracking-wide text-gray-400">Agent Settings</h3>

        <div v-if="!editingRuntime" class="mt-2 flex items-center justify-between text-sm text-gray-600">
          <span>Model: {{ agent.model ?? "Workspace default" }} · Effort: {{ agent.effort ?? "Workspace default" }}</span>
          <button class="text-blue-600" @click="startEditingRuntime">Edit</button>
        </div>
        <div v-else class="mt-2 rounded border border-gray-200 p-2">
          <label class="block text-xs font-medium text-gray-500">Model</label>
          <select v-model="modelDraft" class="mt-1 w-full rounded border border-gray-300 px-2 py-1 text-sm">
            <option value="">Workspace default</option>
            <option v-for="option in MODEL_OPTIONS" :key="option" :value="option">{{ option }}</option>
          </select>
          <label class="mt-2 block text-xs font-medium text-gray-500">Effort</label>
          <select v-model="effortDraft" class="mt-1 w-full rounded border border-gray-300 px-2 py-1 text-sm">
            <option value="">Workspace default</option>
            <option v-for="option in EFFORT_OPTIONS" :key="option" :value="option">{{ option }}</option>
          </select>
          <p class="mt-2 text-xs text-gray-400">Applies to this agent's next run, not one already in progress.</p>
          <div class="mt-2 flex gap-2">
            <button class="rounded bg-blue-600 px-2 py-1 text-sm text-white disabled:opacity-50" :disabled="savingRuntime" @click="saveRuntime">Save</button>
            <button class="rounded border border-gray-300 px-2 py-1 text-sm" @click="editingRuntime = false">Cancel</button>
          </div>
        </div>

        <button v-if="!confirmingFire" class="mt-2 text-sm text-red-600" @click="confirmingFire = true">Fire Agent</button>
        <div v-else class="mt-2 rounded border border-red-200 bg-red-50 p-2 text-sm">
          <p>Fire {{ agent.name }}? Unfinished work returns to Backlog.</p>
          <div class="mt-2 flex gap-2">
            <button class="rounded bg-red-600 px-2 py-1 text-white" @click="confirmFire">Fire Agent</button>
            <button class="rounded border border-gray-300 px-2 py-1" @click="confirmingFire = false">Cancel</button>
          </div>
        </div>
      </div>
    </div>

    <div v-else-if="activeTab === 'Activity'" class="pt-4">
      <ul v-if="recentActivity.length" class="flex flex-col gap-1 text-sm text-gray-600">
        <li v-for="(item, index) in recentActivity" :key="index">
          {{ item.toolName ? `Using ${item.toolName}` : item.text || item.kind }}
        </li>
      </ul>
      <p v-else class="text-sm text-gray-400">No activity yet.</p>

      <div class="mt-4 border-t border-gray-100 pt-3">
        <textarea
          v-model="messageDraft"
          :disabled="agent.status === 'working'"
          class="w-full rounded border border-gray-300 px-2 py-1 text-sm disabled:bg-gray-50 disabled:text-gray-400"
          rows="2"
          placeholder="Message this agent..."
        />
        <p v-if="agent.status === 'working'" class="mt-1 text-xs text-gray-400">Agent is working; wait for it to finish before messaging it.</p>
        <button
          class="mt-2 rounded bg-blue-600 px-2 py-1 text-sm text-white disabled:opacity-50"
          :disabled="!messageDraft.trim() || agent.status === 'working' || sendingMessage"
          @click="sendMessage"
        >
          Send
        </button>
      </div>
    </div>

    <div v-else class="pt-4">
      <div v-if="agentMemories.length" class="flex flex-col gap-2">
        <div v-for="record in agentMemories" :key="record.id" class="flex items-start justify-between gap-2 rounded border border-gray-200 p-2 text-sm">
          <p>{{ record.content }}</p>
          <button class="shrink-0 text-xs text-blue-600" @click="memory.promote(record.id, agent.id)">Share to workspace</button>
        </div>
      </div>
      <p v-else class="text-sm text-gray-400">No private memory yet.</p>
    </div>
  </div>
</template>
