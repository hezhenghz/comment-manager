<template>
  <div class="chart-card">
    <h3>Word Cloud</h3>
    <v-chart :option="option" autoresize />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import VChart from 'vue-echarts';

const props = defineProps<{ data: any[] }>();

const option = computed(() => ({
  tooltip: { show: false },
  series: [{
    type: 'wordCloud',
    shape: 'circle',
    sizeRange: [14, 50],
    rotationRange: [-45, 45],
    textStyle: { color: () => ['#6366f1', '#22c55e', '#f59e0b', '#ef4444', '#3b82f6', '#8b5cf6'][Math.floor(Math.random() * 6)] },
    data: props.data.map((d: any) => ({ name: d.word, value: d.weight })),
  }],
}));
</script>

<style scoped>
.chart-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 20px;
}

h3 {
  font-size: 14px;
  color: var(--text-secondary);
  margin-bottom: 16px;
}
</style>
