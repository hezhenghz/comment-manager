<template>
  <div class="menpai-grid-section">
    <h3 class="section-title">各门派职业物品占比</h3>
    <div class="grid">
      <CareerPie
        v-for="m in menpais"
        :key="m.value"
        :data="dataMap[m.value] ?? []"
        :title="m.name"
        :showTopLabels="true"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue';
import api from '../../api';
import CareerPie from './CareerPie.vue';

// menpais: [{value, name}]；rankLevel 跟随顶部段位筛选（门派固定为每格自身）
const props = defineProps<{
  menpais: { value: number; name: string }[];
  rankLevel: number | null;
  sinceDays: number | null;
}>();

// 门派 value → 职业物品列表
const dataMap = ref<Record<number, any[]>>({});

async function loadOne(menPai: number) {
  const params: any = { top: 15, careerOnly: true, menPai };
  if (props.rankLevel != null) params.rankLevel = props.rankLevel;
  if (props.sinceDays != null) params.sinceDays = props.sinceDays;
  try {
    const { data } = await api.get('/lineup/usage', { params });
    dataMap.value = { ...dataMap.value, [menPai]: data.items ?? [] };
  } catch {
    dataMap.value = { ...dataMap.value, [menPai]: [] };
  }
}

function loadAll() {
  for (const m of props.menpais) loadOne(m.value);
}

onMounted(loadAll);
// 门派列表就绪 / 段位 / 时间范围变化时重新拉取
watch(() => [props.menpais, props.rankLevel, props.sinceDays], loadAll, { deep: true });
</script>

<style scoped>
.menpai-grid-section { margin-top: 16px; }
.section-title {
  font-size: 14px;
  color: var(--text-secondary);
  margin-bottom: 12px;
}
/* 5 行 2 列 */
.grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}
</style>
