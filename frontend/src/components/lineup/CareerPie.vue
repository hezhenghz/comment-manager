<template>
  <div class="chart-card">
    <h3>{{ title ?? '职业物品占比' }}</h3>
    <v-chart v-if="data.length" :option="option" autoresize style="height: 320px" />
    <div v-else class="empty">当前筛选无职业物品数据</div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import VChart from 'vue-echarts';
import '../../composables/useECharts';  // 注册 ECharts 渲染器与图表模块（按需引入必需）
import { qualityColor } from './qualityColor';

// data: 只含职业物品的 [{ name, count, rank }]
// title: 可选标题，不传则用默认"职业物品占比"
// showTopLabels: 是否在扇区旁标注排名前 3 的物品名（门派网格用）
const props = defineProps<{ data: any[]; title?: string; showTopLabels?: boolean }>();

const option = computed(() => ({
  tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
  legend: { type: 'scroll', orient: 'vertical', right: 0, top: 'middle',
            // 图例文字按品质着色
            data: props.data.map((d) => ({ name: d.name, textStyle: { color: qualityColor(d.rank) } })),
            textStyle: { fontSize: 11 } },
  series: [{
    type: 'pie',
    radius: ['38%', '62%'],
    center: ['38%', '50%'],
    itemStyle: { borderRadius: 4, borderWidth: 0 },
    label: { show: false },
    // data 已按 count 降序，前 3 项（index<3）在扇区旁标名字（仅 showTopLabels 时）
    data: props.data.map((d, i) => ({
      name: d.name,
      value: d.count,
      label: props.showTopLabels && i < 3
        ? { show: true, formatter: '{b}', color: qualityColor(d.rank), fontSize: 11 }
        : { show: false },
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
h3 { font-size: 14px; color: var(--text-secondary); margin-bottom: 16px; }
.empty { padding: 40px; text-align: center; color: var(--text-muted); }
</style>
