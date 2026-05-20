<template>
  <div class="dashboard">
    <header class="db-header">
      <h2>仪表盘</h2>
    </header>
    <StatCards :stats="dashStore.stats" />
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
</style>
