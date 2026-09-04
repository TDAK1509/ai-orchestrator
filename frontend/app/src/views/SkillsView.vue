<script setup lang="ts">
import { onMounted, ref } from "vue"
import SkillCard from "../components/skill/SkillCard.vue"
import { useSkillsStore } from "../stores/skills"

const skills = useSkillsStore()
const name = ref("")
const description = ref("")
const instructions = ref("")

onMounted(() => {
  skills.fetchSkills()
})

async function createSkill(): Promise<void> {
  if (!name.value || !instructions.value) return
  await skills.createSkill(name.value, description.value || undefined, instructions.value)
  name.value = ""
  description.value = ""
  instructions.value = ""
}
</script>

<template>
  <div class="p-4">
    <h2 class="text-xs font-semibold uppercase tracking-wide text-gray-400">Skill Catalog</h2>
    <div class="mt-3 rounded-lg border border-gray-200 bg-white p-3">
      <input v-model="name" placeholder="Skill name" class="w-full rounded border border-gray-300 px-2 py-1 text-sm" />
      <input v-model="description" placeholder="Description" class="mt-2 w-full rounded border border-gray-300 px-2 py-1 text-sm" />
      <textarea v-model="instructions" placeholder="Instructions" rows="3" class="mt-2 w-full rounded border border-gray-300 px-2 py-1 text-sm" />
      <button class="mt-2 rounded bg-blue-600 px-3 py-1.5 text-sm text-white" @click="createSkill">Add Skill</button>
    </div>
    <div class="mt-4 grid grid-cols-2 gap-3">
      <SkillCard v-for="skill in skills.skills" :key="skill.id" :skill="skill" />
    </div>
  </div>
</template>
