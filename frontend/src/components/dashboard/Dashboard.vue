<template>
  <div class="dashboard">
    <header class="db-header">
      <h2>仪表盘</h2>
    </header>
    <StatCards :stats="dashStore.stats" />

    <!-- AI 队列积压（仅在有 pending 或 failed 时显示）-->
    <div
      v-if="dashStore.aiQueue.pending > 0 || dashStore.aiQueue.failed > 0"
      class="ai-queue-bar"
    >
      <span class="ai-queue-label">AI 分析队列：</span>
      <span v-if="dashStore.aiQueue.pending > 0" class="ai-queue-item pending">
        ⏳ 待分析 <strong>{{ dashStore.aiQueue.pending.toLocaleString() }}</strong>
      </span>
      <span v-if="dashStore.aiQueue.failed > 0" class="ai-queue-item failed">
        ⚠ 分析失败 <strong>{{ dashStore.aiQueue.failed.toLocaleString() }}</strong>
      </span>
      <span v-if="dashStore.aiQueue.skipped > 0" class="ai-queue-item skipped">
        — 已跳过 <strong>{{ dashStore.aiQueue.skipped.toLocaleString() }}</strong>
      </span>
    </div>

    <div class="charts-row">
      <SourceChart :data="dashStore.sources" />
      <CategoryChart :data="dashStore.categories" />
    </div>
    <CommentFeed :game-id="gameStore.selectedGameId" />
  </div>
</template>

<script setup lang="ts">
import { watch } from 'vue';
import { useDashboardStore } from '../../stores/dashboard';
import { useGameStore } from '../../stores/game';
import { usePolling } from '../../composables/usePolling';
import '../../composables/useECharts';
import StatCards from './StatCards.vue';
import CategoryChart from './CategoryChart.vue';
import SourceChart from './SourceChart.vue';
import CommentFeed from './CommentFeed.vue';

const dashStore = useDashboardStore();
const gameStore = useGameStore();

watch(
  () => gameStore.selectedGameId,
  (id) => { dashStore.loadAll(id); },
  { immediate: true },
);

usePolling(() => dashStore.loadAll(gameStore.selectedGameId), 30000);
</script>

<style scoped>
.dashboard {
  max-width: 1400px;
}

.db-header {
  display: flex;
  align-items: center;
  margin-bottom: 24px;
}

.db-header h2 {
  font-size: 22px;
}

.charts-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  margin-bottom: 20px;
}

/* ── AI 队列积压条 ── */
.ai-queue-bar {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 10px 16px;
  margin-bottom: 20px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  font-size: 13px;
}
.ai-queue-label {
  color: var(--text-secondary);
  font-weight: 500;
}
.ai-queue-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.ai-queue-item strong { font-weight: 700; }
.ai-queue-item.pending { color: var(--text-secondary); }
.ai-queue-item.failed  { color: #f87171; }
.ai-queue-item.skipped { color: var(--text-muted); }
</style>
