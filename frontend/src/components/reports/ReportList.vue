<template>
  <div class="page">
    <h2>Reports</h2>
    <ReportForm @created="load" />
    <table v-if="tasks.length">
      <thead>
        <tr>
          <th>Type</th>
          <th>Date Range</th>
          <th>Schedule</th>
          <th>Status</th>
          <th>Created</th>
          <th>Action</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="t in tasks" :key="t.id">
          <td>{{ t.type.toUpperCase() }}</td>
          <td>{{ t.date_range || '—' }}</td>
          <td>{{ t.schedule || 'Manual' }}</td>
          <td><span class="status" :class="t.status">{{ t.status }}</span></td>
          <td>{{ new Date(t.created_at).toLocaleString() }}</td>
          <td>
            <a v-if="t.status === 'done' && t.file_path" :href="`/api/reports/${t.id}/download`">Download</a>
            <button v-if="t.status === 'pending'" @click="generate(t.id)">Generate</button>
          </td>
        </tr>
      </tbody>
    </table>
    <div v-else class="empty">No reports yet.</div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import api from '../../api';
import ReportForm from './ReportForm.vue';

const tasks = ref<any[]>([]);

async function load() {
  const { data } = await api.get('/reports');
  tasks.value = data;
}

async function generate(id: string) {
  await api.post(`/export/generate/${id}`);
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

.status { font-size: 12px; }
.status.done { color: var(--success); }
.status.failed { color: var(--danger); }
.status.running { color: var(--info); }

a, button { color: var(--accent); font-size: 13px; cursor: pointer; background: none; border: none; }

.empty {
  text-align: center;
  padding: 48px;
  color: var(--text-muted);
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
}
</style>
