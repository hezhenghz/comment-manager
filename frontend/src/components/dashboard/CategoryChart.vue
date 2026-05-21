<template>
  <div class="chart-card">
    <h3>评论分类</h3>
    <v-chart :option="option" autoresize style="height: 260px" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import VChart from 'vue-echarts';

const CATEGORY_LABEL: Record<string, string> = {
  bug: 'Bug报告', suggestion: '建议', complaint: '投诉', praise: '好评', other: '其他',
};

const props = defineProps<{ data: any[] }>();

const option = computed(() => ({
  tooltip: { trigger: 'item' },
  legend: { show: false },
  series: [{
    type: 'pie',
    radius: ['40%', '65%'],
    center: ['50%', '50%'],
    itemStyle: { borderRadius: 4 },
    label: {
      show: true,
      color: '#9ca3af',
      formatter: ({ name, percent }: any) => `${name}\n${percent}%`,
    },
    labelLine: { show: true, lineStyle: { color: '#4b5563' } },
    data: props.data.map((d: any) => ({ name: CATEGORY_LABEL[d.category] ?? d.category, value: d.count })),
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
