<template>
  <div class="stat-cards">
    <div class="card">
      <div class="dual-row">
        <div class="main-val">{{ stats.total_comments?.toLocaleString() ?? 0 }}</div>
        <div class="today-val">{{ stats.today_new?.toLocaleString() ?? 0 }}</div>
      </div>
      <div class="dual-label">
        <span>总评论数</span>
        <span>今日</span>
      </div>
    </div>

    <div class="card clickable" @click="router.push('/bugs')">
      <div class="dual-row">
        <div class="main-val warning">{{ stats.bug_count?.toLocaleString() ?? 0 }}</div>
        <div class="today-val">{{ stats.today_bug_count?.toLocaleString() ?? 0 }}</div>
      </div>
      <div class="dual-label">
        <span>Bug反馈</span>
        <span>今日</span>
      </div>
    </div>

    <div class="card clickable" @click="router.push('/suggestions')">
      <div class="dual-row">
        <div class="main-val accent">{{ stats.suggestion_count?.toLocaleString() ?? 0 }}</div>
        <div class="today-val">{{ stats.today_suggestion_count?.toLocaleString() ?? 0 }}</div>
      </div>
      <div class="dual-label">
        <span>建议</span>
        <span>今日</span>
      </div>
    </div>

    <div class="card">
      <div class="main-val" :class="stats.negative_review_rate != null && stats.negative_review_rate > 30 ? 'danger' : ''">
        {{ stats.negative_review_rate != null ? stats.negative_review_rate + '%' : '—' }}
      </div>
      <div class="single-label">差评率</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router';
import type { DashboardStats } from '../../stores/dashboard';

defineProps<{ stats: DashboardStats }>();
const router = useRouter();
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

.card.clickable {
  cursor: pointer;
  transition: border-color 0.15s;
}

.card.clickable:hover {
  border-color: var(--accent);
}

.dual-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
}

.dual-label {
  display: flex;
  justify-content: space-between;
  margin-top: 4px;
}

.dual-label span {
  font-size: 13px;
  color: var(--text-secondary);
}

.main-val {
  font-size: 28px;
  font-weight: 700;
}

.today-val {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-secondary);
}

.single-label {
  font-size: 13px;
  color: var(--text-secondary);
  margin-top: 4px;
}

.main-val.accent  { color: var(--accent); }
.main-val.warning { color: var(--warning); }
.main-val.danger  { color: var(--danger); }
</style>
