<template>
  <div class="page">
    <h2>Games</h2>
    <GameForm @created="load" />
    <table v-if="games.length">
      <thead>
        <tr>
          <th>Name</th>
          <th>Steam App ID</th>
          <th>Comments</th>
          <th>Created</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="g in games" :key="g.id">
          <td>{{ g.name }}</td>
          <td>{{ g.steam_app_id || '—' }}</td>
          <td>{{ g.comment_count }}</td>
          <td>{{ new Date(g.created_at).toLocaleDateString() }}</td>
          <td><button class="del" @click="remove(g.id)">Delete</button></td>
        </tr>
      </tbody>
    </table>
    <div v-else class="empty">No games added yet.</div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import api from '../../api';
import GameForm from './GameForm.vue';

const games = ref<any[]>([]);

async function load() {
  const { data } = await api.get('/games');
  games.value = data;
}

async function remove(id: string) {
  await api.delete(`/games/${id}`);
  load();
}

onMounted(load);
</script>

<style scoped>
.page { max-width: 900px; }
h2 { font-size: 22px; margin-bottom: 20px; }

table {
  width: 100%;
  border-collapse: collapse;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
}

th, td {
  padding: 10px 14px;
  text-align: left;
  font-size: 13px;
  border-bottom: 1px solid var(--border);
}

th { background: var(--bg-hover); color: var(--text-secondary); font-weight: 600; }
td { color: var(--text-primary); }

.del { color: var(--danger); background: none; border: none; cursor: pointer; font-size: 13px; }

.empty {
  text-align: center;
  padding: 48px;
  color: var(--text-muted);
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
}
</style>
