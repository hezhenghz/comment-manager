<template>
  <div class="dashboard">
    <header class="db-header">
      <h2>Dashboard</h2>
      <select v-model="selectedGameId" @change="onGameChange">
        <option :value="null">All Games</option>
        <option v-for="g in dashStore.games" :key="g.id" :value="g.id">{{ g.name }}</option>
      </select>
    </header>
    <StatCards :stats="dashStore.stats" />
    <div class="charts-row">
      <TrendChart :data="dashStore.trends" />
      <CategoryChart :data="dashStore.categories" />
    </div>
    <div class="charts-row">
      <SourceChart :data="dashStore.sources" />
      <WordCloud :data="dashStore.wordcloud" />
    </div>
    <CommentFeed :game-id="selectedGameId" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useDashboardStore } from '../../stores/dashboard';
import { usePolling } from '../../composables/usePolling';
import '../../composables/useECharts';
import StatCards from './StatCards.vue';
import TrendChart from './TrendChart.vue';
import CategoryChart from './CategoryChart.vue';
import SourceChart from './SourceChart.vue';
import WordCloud from './WordCloud.vue';
import CommentFeed from './CommentFeed.vue';

const dashStore = useDashboardStore();
const selectedGameId = ref<string | null>(null);

onMounted(async () => {
  await dashStore.loadGames();
  dashStore.selectedGameId = null;
  await dashStore.loadAll(null);
});

usePolling(() => dashStore.loadAll(selectedGameId.value), 30000);

function onGameChange() {
  dashStore.selectedGameId = selectedGameId.value;
  dashStore.loadAll(selectedGameId.value);
}
</script>

<style scoped>
.dashboard {
  max-width: 1400px;
}

.db-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
}

.db-header h2 {
  font-size: 22px;
}

.db-header select {
  padding: 8px 12px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  color: var(--text-primary);
  font-size: 13px;
  cursor: pointer;
  outline: none;
}

.charts-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  margin-bottom: 20px;
}
</style>
