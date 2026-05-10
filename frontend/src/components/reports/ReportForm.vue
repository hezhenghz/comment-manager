<template>
  <div class="report-form">
    <select v-model="gameId" required>
      <option value="">Select Game</option>
      <option v-for="g in games" :key="g.id" :value="g.id">{{ g.name }}</option>
    </select>
    <select v-model="type">
      <option value="excel">Excel</option>
      <option value="pdf">PDF</option>
    </select>
    <input v-model="dateFrom" type="date" />
    <input v-model="dateTo" type="date" />
    <select v-model="schedule">
      <option value="">Manual</option>
      <option value="0 8 * * *">Daily</option>
      <option value="0 9 * * 1">Weekly</option>
    </select>
    <button @click="create">Create</button>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import api from '../../api';

const emit = defineEmits<{ created: [] }>();

const games = ref<any[]>([]);
const gameId = ref('');
const type = ref('excel');
const dateFrom = ref('');
const dateTo = ref('');
const schedule = ref('');

onMounted(async () => {
  const { data } = await api.get('/games');
  games.value = data;
});

async function create() {
  if (!gameId.value) return;
  await api.post('/reports', {
    game_id: gameId.value,
    type: type.value,
    date_from: dateFrom.value || null,
    date_to: dateTo.value || null,
    schedule: schedule.value || null,
  });
  emit('created');
  dateFrom.value = '';
  dateTo.value = '';
}
</script>

<style scoped>
.report-form {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}

select, input {
  padding: 8px 12px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  color: var(--text-primary);
  font-size: 13px;
  outline: none;
}

button {
  padding: 8px 20px;
  background: var(--accent);
  color: #fff;
  border: none;
  border-radius: var(--radius);
  cursor: pointer;
  font-size: 13px;
}

button:hover { background: var(--accent-hover); }
</style>
