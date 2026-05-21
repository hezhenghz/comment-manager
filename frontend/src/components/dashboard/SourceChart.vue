<template>
  <div class="chart-card">
    <h3>来源分布</h3>
    <v-chart :option="option" autoresize style="height: 260px" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import VChart from 'vue-echarts';

const PLATFORM_LABEL: Record<string, string> = {
  steam_store: 'Steam评价', steam_hub: 'Steam论坛',
  discord: 'Discord', qq: 'QQ群', xiaoheihe: '小黑盒',
};

const PLATFORM_COLOR: Record<string, string> = {
  steam_store: '#4a9eff',
  steam_hub:   '#4caf74',
  discord:     '#7289da',
  qq:          '#12b7f5',
  xiaoheihe:   '#ff781e',
};

const props = defineProps<{ data: any[] }>();

const option = computed(() => ({
  tooltip: { trigger: 'item' },
  legend: { show: false },
  series: [{
    type: 'pie',
    radius: '65%',
    center: ['50%', '50%'],
    itemStyle: { borderRadius: 4 },
    label: {
      color: '#9ca3af',
      formatter: ({ name, percent }: any) => `${name}\n${percent}%`,
    },
    data: props.data.map((d: any) => ({
      name: PLATFORM_LABEL[d.platform] ?? d.platform,
      value: d.count,
      itemStyle: { color: PLATFORM_COLOR[d.platform] ?? '#6b7280' },
    })),
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
