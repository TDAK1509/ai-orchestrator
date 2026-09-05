<script setup lang="ts">
defineProps<{ agentNames: string[] }>()
</script>

<template>
  <p v-if="agentNames.length">Assigned to {{ agentNames.join(", ") }}. They will lose this skill.</p>
  <p v-else>No agents are assigned to this skill.</p>
</template>
