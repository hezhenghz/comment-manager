<template>
  <div class="stat-cards">
    <div class="card">
      <div class="card-value">{{ stats.total_comments?.toLocaleString() ?? 0 }}</div>
      <div class="card-label">Total Comments</div>
    </div>
    <div class="card">
      <div class="card-value accent">{{ stats.today_new?.toLocaleString() ?? 0 }}</div>
      <div class="card-label">Today New</div>
    </div>
    <div class="card">
      <div class="card-value warning">{{ stats.bug_count?.toLocaleString() ?? 0 }}</div>
      <div class="card-label">Bug Reports</div>
    </div>
    <div class="card">
      <div class="card-value" :class="stats.negative_ratio > 30 ? 'danger' : ''">{{ stats.negative_ratio ?? 0 }}%</div>
      <div class="card-label">Negative Ratio</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { DashboardStats } from '../../stores/dashboard';
defineProps<{ stats: DashboardStats }>();
</script>

<style scoped>
.stat-cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}

.card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 20px;
}

.card-value {
  font-size: 28px;
  font-weight: 700;
}

.card-value.accent { color: var(--accent); }
.card-value.warning { color: var(--warning); }
.card-value.danger { color: var(--danger); }

.card-label {
  font-size: 13px;
  color: var(--text-secondary);
  margin-top: 4px;
}
</style>
