<template>
  <div class="imbalance-section">
    <h3 class="section-title">
      选用失衡度
      <span class="desc">基尼系数衡量该类物品选用集中度（≥0.6 严重失衡）；偏冷 = 份额低于公平份额(1/N) 的 25%</span>
    </h3>
    <div v-if="excluded.length" class="excluded-note">
      已排除稀缺物品（BOSS掉落，不计入失衡）：{{ excluded.map((e) => e.name).join('、') }}
    </div>

    <div v-if="!types.length" class="empty">暂无数据</div>

    <div v-else class="rows">
      <div v-for="t in types" :key="t.type" class="imb-row">
        <div class="row-head" @click="toggle(t.type)">
          <span class="type-name">{{ t.typeName }}</span>
          <span class="item-count">{{ t.itemCount }} 种</span>
          <span class="gini" :style="{ color: levelColor(t.level) }">
            基尼 {{ t.gini.toFixed(2) }}
            <span class="level-tag" :style="{ background: levelBg(t.level), color: levelColor(t.level) }">
              {{ levelText(t.level) }}
            </span>
          </span>
          <span class="cold-stat">
            <span v-if="t.severeCount" class="severe">严重偏冷 {{ t.severeCount }}（{{ severeNames(t) }}）</span>
            <span v-if="t.coldCount" class="cold">偏冷 {{ t.coldCount }}</span>
            <span v-if="!t.coldCount" class="muted">无明显偏冷</span>
          </span>
          <span class="arrow">{{ expanded.has(t.type) ? '▾' : '▸' }}</span>
        </div>

        <div v-if="expanded.has(t.type) && t.cold.length" class="cold-list">
          <div v-for="c in t.cold" :key="c.itemId" class="cold-item">
            <span class="cold-name" :style="{ color: qualityColor(c.rank) }">
              <span v-if="c.severe" class="dot severe-dot">●</span>{{ c.name }}
            </span>
            <span class="cold-share">份额 {{ c.share }}%</span>
            <span class="cold-ratio" :class="{ severe: c.severe }">
              仅公平份额的 {{ Math.round(c.ratio * 100) }}%
            </span>
          </div>
        </div>
        <div v-else-if="expanded.has(t.type)" class="cold-list empty-cold">该类型无偏冷物品</div>
      </div>
    </div>

    <!-- 子区：职业物品前3失衡 -->
    <h3 class="section-title sub">
      职业物品前3失衡
      <span class="desc">每门派只统计选用最高的前3个职业物品（其余为跨门派抓取的杂质，不参与）；段位跟随筛选，固定对比10门派</span>
    </h3>
    <div v-if="!careerTop.length" class="empty">暂无数据</div>
    <div v-else class="rows">
      <div v-for="m in careerTop" :key="m.menPai" class="imb-row">
        <div class="row-head" @click="toggleMp(m.menPai)">
          <span class="type-name">{{ m.menPaiName }}</span>
          <span class="gini" :style="{ color: levelColor(m.level) }">
            前3基尼 {{ m.gini.toFixed(2) }}
            <span class="level-tag" :style="{ background: levelBg(m.level), color: levelColor(m.level) }">
              {{ levelText(m.level) }}
            </span>
          </span>
          <span class="top3-preview">
            <span v-for="(it, i) in m.items" :key="it.itemId">
              <span :style="{ color: qualityColor(it.rank) }">{{ it.name }}</span>
              <span class="share-inline">{{ it.share }}%</span><span v-if="i < m.items.length - 1"> · </span>
            </span>
          </span>
          <span class="arrow">{{ expandedMp.has(m.menPai) ? '▾' : '▸' }}</span>
        </div>
        <div v-if="expandedMp.has(m.menPai)" class="cold-list">
          <div v-for="it in m.items" :key="it.itemId" class="cold-item">
            <span class="cold-name" :style="{ color: qualityColor(it.rank) }">{{ it.name }}</span>
            <span class="cold-share">占前3的 {{ it.share }}%</span>
            <span class="cold-ratio">选用 {{ it.count }} 次</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue';
import api from '../../api';
import { qualityColor } from './qualityColor';

const props = defineProps<{
  menPai: number | null;
  rankLevel: number | null;
}>();

const types = ref<any[]>([]);
const expanded = ref<Set<number>>(new Set());
const careerTop = ref<any[]>([]);
const expandedMp = ref<Set<number>>(new Set());
const excluded = ref<any[]>([]);   // 已排除的稀缺物品

function toggle(t: number) {
  const next = new Set(expanded.value);
  next.has(t) ? next.delete(t) : next.add(t);
  expanded.value = next;
}

function toggleMp(mp: number) {
  const next = new Set(expandedMp.value);
  next.has(mp) ? next.delete(mp) : next.add(mp);
  expandedMp.value = next;
}

const LEVEL = {
  severe:   { text: '严重失衡', color: '#E53935', bg: 'rgba(229,57,53,0.12)' },
  moderate: { text: '中度失衡', color: '#FF9800', bg: 'rgba(255,152,0,0.12)' },
  balanced: { text: '均衡',     color: '#8BC34A', bg: 'rgba(139,195,74,0.12)' },
} as Record<string, { text: string; color: string; bg: string }>;

// 严重偏冷物品名（逗号分隔，供概览行括号内显示）
function severeNames(t: any): string {
  return (t.cold ?? []).filter((c: any) => c.severe).map((c: any) => c.name).join('、');
}

function levelText(l: string)  { return LEVEL[l]?.text ?? l; }
function levelColor(l: string) { return LEVEL[l]?.color ?? '#9ca3af'; }
function levelBg(l: string)    { return LEVEL[l]?.bg ?? 'transparent'; }

async function load() {
  const params: any = {};
  if (props.menPai != null) params.menPai = props.menPai;
  if (props.rankLevel != null) params.rankLevel = props.rankLevel;
  try {
    const { data } = await api.get('/lineup/usage-imbalance', { params });
    types.value = data.types ?? [];
    excluded.value = data.excluded ?? [];
  } catch {
    types.value = [];
  }
}

// 职业前3失衡：固定10门派，只跟随段位（不受 menPai 影响）
async function loadCareerTop() {
  const params: any = {};
  if (props.rankLevel != null) params.rankLevel = props.rankLevel;
  try {
    const { data } = await api.get('/lineup/career-top-imbalance', { params });
    careerTop.value = data.menpais ?? [];
  } catch {
    careerTop.value = [];
  }
}

onMounted(() => { load(); loadCareerTop(); });
watch(() => [props.menPai, props.rankLevel], load);
watch(() => props.rankLevel, loadCareerTop);
</script>

<style scoped>
.imbalance-section { margin-top: 16px; }
.section-title {
  font-size: 14px;
  color: var(--text-secondary);
  margin-bottom: 12px;
  display: flex;
  align-items: baseline;
  gap: 10px;
  flex-wrap: wrap;
}
.desc { font-size: 12px; color: var(--text-muted); font-weight: 400; }
.excluded-note {
  font-size: 12px;
  color: var(--text-muted);
  margin: -4px 0 12px;
  padding: 6px 10px;
  background: var(--bg-hover);
  border-radius: var(--radius);
}
.empty { padding: 24px; text-align: center; color: var(--text-muted); }

.rows { display: flex; flex-direction: column; gap: 8px; }
.imb-row {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
}
.row-head {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 16px;
  cursor: pointer;
}
.row-head:hover { background: var(--bg-hover); }
.type-name { font-size: 14px; font-weight: 600; color: var(--text-primary); min-width: 48px; }
.item-count { font-size: 12px; color: var(--text-muted); min-width: 44px; }
.gini { font-size: 13px; display: flex; align-items: center; gap: 8px; min-width: 150px; }
.level-tag { font-size: 11px; padding: 1px 7px; border-radius: 4px; }
.cold-stat { flex: 1; display: flex; gap: 12px; font-size: 12px; }
.cold-stat .severe { color: #E53935; }
.cold-stat .cold { color: #FF9800; }
.cold-stat .muted { color: var(--text-muted); }
.arrow { color: var(--text-muted); font-size: 12px; }

.cold-list {
  border-top: 1px solid var(--border);
  padding: 8px 16px 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.cold-list.empty-cold { color: var(--text-muted); font-size: 12px; }
.cold-item {
  display: flex;
  align-items: center;
  gap: 16px;
  font-size: 13px;
  padding: 2px 0;
}
.cold-name { min-width: 160px; }
.dot { font-size: 9px; margin-right: 4px; }
.severe-dot { color: #E53935; }
.cold-share { color: var(--text-secondary); min-width: 90px; }
.cold-ratio { color: var(--text-muted); }
.cold-ratio.severe { color: #E53935; font-weight: 500; }

.section-title.sub { margin-top: 24px; }
.top3-preview { flex: 1; font-size: 12px; color: var(--text-secondary); }
.share-inline { color: var(--text-muted); margin-left: 3px; }
</style>
