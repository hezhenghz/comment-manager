<template>
  <div class="chart-card">
    <h3>各门派样本分布</h3>
    <v-chart v-if="data.length" :option="option" autoresize style="height: 300px" />
    <div v-else class="empty">暂无数据</div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import VChart from 'vue-echarts';
import '../../composables/useECharts';  // 注册 ECharts 渲染器与图表模块（按需引入必需）

// data: [{ menPai, name, count }]
const props = defineProps<{ data: any[] }>();

const option = computed(() => ({
  tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
  grid: { left: 50, right: 30, top: 20, bottom: 30 },
  xAxis: {
    type: 'category',
    data: props.data.map((d) => d.name),
    axisLabel: { color: '#9ca3af', fontSize: 12 },
  },
  yAxis: { type: 'value', axisLabel: { color: '#9ca3af' } },
  series: [{
    type: 'bar',
    data: props.data.map((d) => d.count),
    barMaxWidth: 32,
    itemStyle: { color: '#3b82f6', borderRadius: [3, 3, 0, 0] },
    label: { show: true, position: 'top', color: '#9ca3af', fontSize: 11 },
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
h3 { font-size: 14px; color: var(--text-secondary); margin-bottom: 16px; }
.empty { padding: 40px; text-align: center; color: var(--text-muted); }
</style>
