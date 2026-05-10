<template>
  <div class="chart-card">
    <h3>Sources</h3>
    <v-chart :option="option" autoresize />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import VChart from 'vue-echarts';

const props = defineProps<{ data: any[] }>();

const option = computed(() => ({
  tooltip: { trigger: 'item' },
  series: [{
    type: 'pie',
    radius: '65%',
    itemStyle: { borderRadius: 4 },
    label: { color: '#9ca3af' },
    data: props.data.map((d: any) => ({ name: d.platform, value: d.count })),
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
