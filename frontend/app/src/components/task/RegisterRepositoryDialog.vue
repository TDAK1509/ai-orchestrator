<script setup lang="ts">
import { onMounted, ref } from "vue"
import type { DirectoryEntry } from "../../api/types"
import { useRepositoriesStore } from "../../stores/repositories"

const emit = defineEmits<{ close: []; registered: [repositoryId: string] }>()

const repositories = useRepositoriesStore()
const currentPath = ref("")
const entries = ref<DirectoryEntry[]>([])
const loading = ref(false)
const error = ref("")
const registering = ref(false)
const branchDraft = ref("")
const hasRemote = ref<boolean | null>(null)

onMounted(() => browseTo(undefined))

async function browseTo(path: string | undefined): Promise<void> {
  loading.value = true
  error.value = ""
  try {
    entries.value = await repositories.browseDirectory(path)
    if (path) currentPath.value = path
  } catch {
    error.value = "Could not list that directory."
  } finally {
    loading.value = false
  }
  await inspectCurrentDirectory()
}

async function inspectCurrentDirectory(): Promise<void> {
  if (!currentPath.value) {
    resetInspection()
    return
  }
  try {
    const info = await repositories.inspectRepository(currentPath.value)
    branchDraft.value = info.default_target_branch
    hasRemote.value = info.has_remote
  } catch {
    resetInspection()
  }
}

function resetInspection(): void {
  branchDraft.value = ""
  hasRemote.value = null
}

function goUp(): void {
  const parent = currentPath.value.split("/").slice(0, -1).join("/")
  browseTo(parent || "/")
}

async function registerCurrentDirectory(): Promise<void> {
  registering.value = true
  error.value = ""
  try {
    const repository = await repositories.createRepository(currentPath.value, undefined, branchDraft.value || "main")
    emit("registered", repository.id)
  } catch {
    error.value = `Could not register this directory -- check it is a git repository with a '${branchDraft.value || "main"}' branch.`
  } finally {
    registering.value = false
  }
}
</script>

<template>
  <div class="fixed inset-0 z-40 flex items-center justify-center bg-black/30">
    <div class="w-[28rem] rounded-lg bg-white p-4 shadow-xl">
      <div class="flex items-center justify-between">
        <h2 class="text-lg font-semibold">Register a Repository</h2>
        <button class="text-gray-400 hover:text-gray-600" @click="$emit('close')">✕</button>
      </div>
      <p class="mt-2 truncate text-xs text-gray-500">{{ currentPath || "/" }}</p>
      <div class="mt-2 h-64 overflow-y-auto rounded border border-gray-200">
        <button class="block w-full px-2 py-1 text-left text-sm hover:bg-gray-50" :disabled="!currentPath" @click="goUp">.. (up)</button>
        <button
          v-for="entry in entries"
          :key="entry.path"
          class="flex w-full items-center justify-between px-2 py-1 text-left text-sm hover:bg-gray-50"
          @click="browseTo(entry.path)"
        >
          <span>{{ entry.name }}</span>
          <span v-if="entry.is_git_repo" class="text-xs text-green-600">git repo</span>
        </button>
        <p v-if="!loading && !entries.length" class="px-2 py-1 text-sm text-gray-400">No subdirectories.</p>
      </div>

      <template v-if="currentPath">
        <label class="mt-2 block text-xs font-medium text-gray-500">Base branch</label>
        <input v-model="branchDraft" placeholder="origin/main" class="mt-1 w-full rounded border border-gray-300 px-2 py-1 text-sm" />
        <p v-if="hasRemote === true" class="mt-1 text-xs text-gray-400">Has a remote -- tasks will land as pull requests.</p>
        <p v-else-if="hasRemote === false" class="mt-1 text-xs text-gray-400">No remote -- tasks will land by merging directly into this checkout.</p>
      </template>

      <p v-if="error" class="mt-2 text-sm text-red-600">{{ error }}</p>
      <div class="mt-4 flex justify-end gap-2">
        <button class="rounded border border-gray-300 px-3 py-1.5 text-sm" @click="$emit('close')">Cancel</button>
        <button
          class="rounded bg-blue-600 px-3 py-1.5 text-sm text-white disabled:opacity-50"
          :disabled="!currentPath || !branchDraft || registering"
          @click="registerCurrentDirectory"
        >
          Use this directory
        </button>
      </div>
    </div>
  </div>
</template>
