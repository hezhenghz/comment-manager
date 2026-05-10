<template>
  <div class="page">
    <h2>Settings</h2>
    <section class="section">
      <h3>AI Configuration</h3>
      <p class="hint">Set up your environment variables (.env) and restart the backend to apply AI changes.</p>
    </section>
    <section class="section">
      <h3>Crawler Settings</h3>
      <div class="field">
        <label>Crawler Interval (minutes)</label>
        <input v-model="crawlerInterval" type="number" />
      </div>
      <button @click="save">Save</button>
    </section>
    <section class="section">
      <h3>Reserved Platforms</h3>
      <div class="platform-list">
        <div class="platform-item">
          <span class="badge active">Steam Store</span> Active
        </div>
        <div class="platform-item">
          <span class="badge active">Steam Hub</span> Active
        </div>
        <div class="platform-item">
          <span class="badge reserved">Discord</span> Reserved
        </div>
        <div class="platform-item">
          <span class="badge reserved">QQ Group</span> Reserved
        </div>
        <div class="platform-item">
          <span class="badge reserved">Xiaoheihe</span> Reserved
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';

const crawlerInterval = ref(120);

function save() {
  alert('Settings saved. Note: full config is managed via .env file.');
}
</script>

<style scoped>
.page { max-width: 800px; }
h2 { font-size: 22px; margin-bottom: 24px; }

.section {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 20px;
  margin-bottom: 20px;
}

h3 { font-size: 16px; margin-bottom: 12px; }

.hint { color: var(--text-secondary); font-size: 13px; }

.field { margin-bottom: 12px; }

label { display: block; font-size: 13px; color: var(--text-secondary); margin-bottom: 6px; }

input {
  padding: 8px 12px;
  background: var(--bg-primary);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  color: var(--text-primary);
  font-size: 13px;
  width: 120px;
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

.platform-list { display: flex; flex-direction: column; gap: 10px; }

.platform-item {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 14px;
  color: var(--text-secondary);
}

.badge {
  padding: 2px 10px;
  border-radius: 4px;
  font-size: 12px;
  width: 110px;
  text-align: center;
}

.badge.active { background: rgba(34, 197, 94, 0.15); color: var(--success); }
.badge.reserved { background: rgba(107, 114, 128, 0.15); color: var(--neutral); }
</style>
