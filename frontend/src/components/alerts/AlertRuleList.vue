<template>
  <div class="page">
    <h2>Alert Rules</h2>
    <AlertRuleForm @created="load" />
    <table v-if="rules.length">
      <thead>
        <tr>
          <th>Game</th>
          <th>Keywords</th>
          <th>Channel</th>
          <th>Enabled</th>
          <th>Created</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="r in rules" :key="r.id">
          <td>{{ r.game_id }}</td>
          <td>{{ r.keywords.join(', ') }}</td>
          <td>{{ r.channel }}</td>
          <td><span :class="r.enabled ? 'on' : 'off'">{{ r.enabled ? 'Yes' : 'No' }}</span></td>
          <td>{{ new Date(r.created_at).toLocaleString() }}</td>
          <td><button class="del" @click="remove(r.id)">Delete</button></td>
        </tr>
      </tbody>
    </table>
    <div v-else class="empty">No alert rules yet.</div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import api from '../../api';
import AlertRuleForm from './AlertRuleForm.vue';

const rules = ref<any[]>([]);

async function load() {
  const { data } = await api.get('/alerts');
  rules.value = data;
}

async function remove(id: string) {
  await api.delete(`/alerts/${id}`);
  load();
}

onMounted(load);
</script>

<style scoped>
.page { max-width: 1000px; }
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

.on { color: var(--success); }
.off { color: var(--neutral); }
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
