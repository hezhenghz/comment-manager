<template>
  <div class="chart-card">
    <h3>Sentiment Trend (7 days)</h3>
    <v-chart :option="option" autoresize />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import VChart from 'vue-echarts';

const props = defineProps<{ data: any[] }>();

const option = computed(() => ({
  tooltip: { trigger: 'axis' },
  legend: { textStyle: { color: '#9ca3af' }, bottom: 0 },
  grid: { left: '3%', right: '4%', bottom: '12%', top: '8%', containLabel: true },
  xAxis: { type: 'category', data: props.data.map((d: any) => d.date.slice(5)), axisLabel: { color: '#6b7280' } },
  yAxis: { type: 'value', axisLabel: { color: '#6b7280' } },
  series: [
    { name: 'Positive', type: 'line', data: props.data.map((d: any) => d.positive), smooth: true, lineStyle: { color: '#22c55e' }, itemStyle: { color: '#22c55e' } },
    { name: 'Neutral', type: 'line', data: props.data.map((d: any) => d.neutral), smooth: true, lineStyle: { color: '#6b7280' }, itemStyle: { color: '#6b7280' } },
    { name: 'Negative', type: 'line', data: props.data.map((d: any) => d.negative), smooth: true, lineStyle: { color: '#ef4444' }, itemStyle: { color: '#ef4444' } },
  ],
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
