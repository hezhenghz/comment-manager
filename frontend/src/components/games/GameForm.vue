<template>
  <div class="game-form">
    <input v-model="name" type="text" placeholder="Game name" />
    <input v-model="steamAppId" type="text" placeholder="Steam App ID (e.g. 730)" />
    <input v-model="iconUrl" type="text" placeholder="Icon URL (optional)" />
    <button @click="create">Add Game</button>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import api from '../../api';

const emit = defineEmits<{ created: [] }>();

const name = ref('');
const steamAppId = ref('');
const iconUrl = ref('');

async function create() {
  if (!name.value) return;
  await api.post('/games', { name: name.value, steam_app_id: steamAppId.value || null, icon_url: iconUrl.value || null });
  emit('created');
  name.value = '';
  steamAppId.value = '';
  iconUrl.value = '';
}
</script>

<style scoped>
.game-form {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
}

input {
  padding: 8px 12px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  color: var(--text-primary);
  font-size: 13px;
  outline: none;
  flex: 1;
}

input:focus { border-color: var(--accent); }

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
