<template>
  <div class="alert-form">
    <select v-model="gameId">
      <option value="">Select Game</option>
      <option v-for="g in games" :key="g.id" :value="g.id">{{ g.name }}</option>
    </select>
    <input v-model="keywordsStr" type="text" placeholder="Keywords (comma separated)" />
    <select v-model="channel">
      <option value="in_app">In App</option>
      <option value="dingtalk">DingTalk</option>
    </select>
    <button @click="create">Add Rule</button>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import api from '../../api';

const emit = defineEmits<{ created: [] }>();

const games = ref<any[]>([]);
const gameId = ref('');
const keywordsStr = ref('');
const channel = ref('in_app');

onMounted(async () => {
  const { data } = await api.get('/games');
  games.value = data;
});

async function create() {
  if (!gameId.value || !keywordsStr.value) return;
  await api.post('/alerts', {
    game_id: gameId.value,
    keywords: keywordsStr.value.split(',').map((k: string) => k.trim()).filter(Boolean),
    channel: channel.value,
  });
  emit('created');
  keywordsStr.value = '';
}
</script>

<style scoped>
.alert-form {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
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

input { flex: 1; }

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
