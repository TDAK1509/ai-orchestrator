<script setup lang="ts">
import { ref } from "vue"
import type { DecisionRequest } from "../../api/types"
import { useAttentionStore } from "../../stores/attention"

const props = defineProps<{ decision: DecisionRequest }>()

const attention = useAttentionStore()
const selectedOption = ref<string | null>(null)
const customAnswer = ref("")
const submitting = ref(false)

function answerText(): string {
  return customAnswer.value || selectedOption.value || ""
}

function chooseOption(label: string): void {
  selectedOption.value = label
  customAnswer.value = ""
}

function typeCustomAnswer(value: string): void {
  customAnswer.value = value
  if (value) selectedOption.value = null
}

async function submit(): Promise<void> {
  if (!answerText()) return
  submitting.value = true
  try {
    await attention.answerDecision(props.decision.id, answerText())
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="rounded-lg border border-red-200 bg-red-50 p-3">
    <h3 class="text-xs font-semibold uppercase tracking-wide text-red-500">Decision needed</h3>
    <p class="mt-2 text-sm text-gray-800">{{ decision.question }}</p>
    <div v-if="decision.options" class="mt-3 flex flex-col gap-2">
      <label v-for="option in decision.options" :key="option.label" class="flex items-center gap-2 text-sm">
        <input
          type="radio"
          :value="option.label"
          :checked="selectedOption === option.label"
          @change="chooseOption(option.label)"
        />
        {{ option.label }}
      </label>
    </div>
    <input
      v-if="decision.allow_custom_answer"
      :value="customAnswer"
      type="text"
      placeholder="Write another answer..."
      class="mt-3 w-full rounded border border-gray-300 px-2 py-1 text-sm"
      @input="typeCustomAnswer(($event.target as HTMLInputElement).value)"
    />
    <button
      class="mt-3 rounded bg-red-600 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
      :disabled="!answerText() || submitting"
      @click="submit"
    >
      Submit Decision
    </button>
  </div>
</template>
