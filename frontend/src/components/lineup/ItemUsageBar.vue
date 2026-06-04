<template>
  <div class="chart-card">
    <h3>{{ title ?? `物品使用率 Top ${data.length}` }}</h3>
    <v-chart :option="option" autoresize :style="{ height: chartHeight + 'px' }" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import VChart from 'vue-echarts';
import '../../composables/useECharts';  // 注册 ECharts 渲染器与图表模块（按需引入必需）
import { qualityColor } from './qualityColor';

// data: [{ itemId, name, count, pct, isCareer }]，已按 count 降序
// title: 可选标题，不传则用默认"物品使用率 Top N"
const props = defineProps<{ data: any[]; title?: string }>();

// 横向柱状图，条数多时自动增高
const chartHeight = computed(() => Math.max(300, props.data.length * 22));

const option = computed(() => {
  // ECharts y 轴从下往上，故倒序让最大值显示在顶部
  const rows = [...props.data].reverse();
  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (ps: any) => {
        const p = ps[0];
        return `${p.name}<br/>出现次数：${p.data.value}<br/>使用率：${p.data.pct}%`;
      },
    },
    grid: { left: 110, right: 70, top: 10, bottom: 20 },
    xAxis: { type: 'value', axisLabel: { color: '#9ca3af' } },
    yAxis: {
      type: 'category',
      // 物品名按品质着色；职业物品名字左侧加 ★ 标识
      data: rows.map((d) => ({
        value: d.isCareer ? `★${d.name}` : d.name,
        textStyle: { color: qualityColor(d.rank), fontSize: 12 },
      })),
    },
    series: [{
      type: 'bar',
      data: rows.map((d) => ({
        value: d.count,
        pct: d.pct,
        // 所有物品统一蓝色（职业物品改用名字左侧的五角星标识）
        itemStyle: { color: '#3b82f6', borderRadius: [0, 3, 3, 0] },
      })),
      barMaxWidth: 16,
      label: {
        show: true, position: 'right', color: '#9ca3af', fontSize: 11,
        formatter: (p: any) => `${p.data.value}（${p.data.pct}%）`,
      },
    }],
  };
});
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
