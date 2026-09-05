<script setup lang="ts">
import type { Skill } from "../../api/types"

defineProps<{ skill: Skill }>()
defineEmits<{ click: [] }>()
</script>

<template>
  <button
    class="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-left text-sm font-medium shadow-sm hover:bg-gray-50"
    @click="$emit('click')"
  >
    {{ skill.name }}
  </button>
</template>
