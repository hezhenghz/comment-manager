<template>
  <div class="by-type">
    <div
      v-for="t in types"
      :key="t.type"
      class="type-row"
    >
      <ItemUsageBar :data="t.top" :title="`${t.typeName} · Top ${t.top.length}`" />
      <ItemUsageBar :data="t.last" :title="`${t.typeName} · Last ${t.last.length}`" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue';
import api from '../../api';
import ItemUsageBar from './ItemUsageBar.vue';

// 跟随父组件的门派/段位筛选
const props = defineProps<{
  menPai: number | null;
  rankLevel: number | null;
}>();

const types = ref<any[]>([]);

async function load() {
  const params: any = { topN: 20 };
  if (props.menPai != null) params.menPai = props.menPai;
  if (props.rankLevel != null) params.rankLevel = props.rankLevel;
  try {
    const { data } = await api.get('/lineup/usage-by-type', { params });
    types.value = data.types ?? [];
  } catch {
    types.value = [];
  }
}

onMounted(load);
watch(() => [props.menPai, props.rankLevel], load);
</script>

<style scoped>
.by-type {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-top: 16px;
}
/* 每个类型一行：左 Top / 右 Last 两栏并排 */
.type-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}
</style>
