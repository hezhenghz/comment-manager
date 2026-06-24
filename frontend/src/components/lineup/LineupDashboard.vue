<template>
  <div class="lineup-page">
    <!-- 顶部工具栏：标题 + 控制 + 状态，合并为一个紧凑卡片 -->
    <div class="toolbar">
      <div class="toolbar-row">
        <h2>阵容物品使用率分析</h2>
        <div class="controls">
          <label class="switch">
            <input type="checkbox" v-model="autoEnabled" /> 自动
          </label>
          <label class="interval">
            每
            <input type="number" v-model.number="autoInterval" min="1" max="168"
                   :disabled="!autoEnabled" style="width:52px" />
            时
          </label>
          <button class="btn-small" :disabled="savingSchedule" @click="saveSchedule">
            {{ savingSchedule ? '保存中…' : '保存' }}
          </button>
          <button class="btn" :disabled="fetching" @click="triggerFetch">
            {{ fetching ? '拉取中…' : '立即拉取' }}
          </button>
        </div>
      </div>

      <!-- 状态行：下次执行 · 上次自动结果 · 当前拉取进度 -->
      <div class="toolbar-status">
        <template v-if="schedule">
          <span v-if="schedule.enabled && schedule.next_run_time">
            下次执行：{{ fmt(schedule.next_run_time) }}
          </span>
          <span v-else class="muted">自动拉取已关闭</span>
          <template v-if="schedule.last_auto_job">
            <span class="sep">·</span>
            <span>
              上次自动：<span class="status" :class="schedule.last_auto_job.status">{{ autoStatusText(schedule.last_auto_job.status) }}</span>
              新增 {{ schedule.last_auto_job.new_count }} 条<span
                v-if="schedule.last_auto_job.finished_at" class="muted">（{{ fmt(schedule.last_auto_job.finished_at) }}）</span>
              <span v-if="schedule.last_auto_job.error_msg" class="err">{{ schedule.last_auto_job.error_msg }}</span>
            </span>
          </template>
        </template>
        <template v-if="job">
          <span class="sep">·</span>
          <span class="status" :class="job.status">{{ statusText }}</span>
          <span v-if="job.req_total">{{ job.req_done }}/{{ job.req_total }}</span>
          <span>新增 {{ job.new_count }} 条</span>
          <span v-if="job.finished_at" class="muted">完成于 {{ fmt(job.finished_at) }}</span>
          <span v-if="job.error_msg" class="err">{{ job.error_msg }}</span>
        </template>
      </div>
    </div>

    <!-- 概览统计 -->
    <div class="stat-cards" v-if="stats">
      <div class="stat-card">
        <div class="num">{{ stats.total_snapshots }}</div>
        <div class="label">总局数</div>
      </div>
      <div class="stat-card">
        <div class="num">{{ stats.total_rounds ?? 0 }}</div>
        <div class="label">总回合数</div>
      </div>
      <div class="stat-card">
        <div class="num">{{ stats.menpai_count }}</div>
        <div class="label">覆盖门派</div>
      </div>
      <div class="stat-card">
        <div class="num">{{ usage?.sample_players ?? 0 }}</div>
        <div class="label">当前筛选样本</div>
      </div>
    </div>

    <!-- 筛选栏 -->
    <div class="filters">
      <label>时间范围
        <select v-model.number="sinceDays" @change="onFilterChange">
          <option v-for="o in sinceOptions" :key="o.value ?? 'all'" :value="o.value">{{ o.label }}</option>
        </select>
      </label>
      <label>门派
        <select v-model="menPai" @change="onFilterChange">
          <option :value="null">全部</option>
          <option v-for="m in menpais" :key="m.value" :value="m.value">{{ m.name }}</option>
        </select>
      </label>
      <label>段位
        <select v-model.number="rankLevel" @change="onFilterChange">
          <option :value="null">全部</option>
          <option v-for="r in rankLevels" :key="r" :value="r">{{ r }}</option>
        </select>
      </label>
      <label>显示数量
        <input type="number" v-model.number="top" min="5" max="200" @change="loadUsage" style="width:70px" />
      </label>
      <label class="checkbox">
        <input type="checkbox" v-model="careerOnly" @change="loadUsage" /> 仅职业物品
      </label>
    </div>

    <!-- 图表区 -->
    <div v-if="usage && usage.items.length" class="charts">
      <ItemUsageBar :data="usage.items" />
      <div class="charts-row">
        <CareerPie :data="careerItems" />
        <MenPaiDistribution :data="stats?.by_menpai ?? []" />
      </div>
      <!-- 按物品类型分组：每类型一行，左 Top20 / 右 Last20 -->
      <UsageByTypeSection :menPai="menPai" :rankLevel="rankLevel" :sinceDays="sinceDays" />
      <!-- 各门派职业物品占比：5 行 2 列，每格一个门派（段位跟随筛选） -->
      <MenPaiCareerGrid :menpais="menpais" :rankLevel="rankLevel" :sinceDays="sinceDays" />
      <!-- 选用失衡度：基尼系数 + 偏冷物品清单 -->
      <ImbalanceSection :menPai="menPai" :rankLevel="rankLevel" :sinceDays="sinceDays" />
    </div>
    <div v-else class="empty">暂无数据，点「立即拉取」开始采集。</div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue';
import api from '../../api';
import ItemUsageBar from './ItemUsageBar.vue';
import CareerPie from './CareerPie.vue';
import MenPaiDistribution from './MenPaiDistribution.vue';
import UsageByTypeSection from './UsageByTypeSection.vue';
import MenPaiCareerGrid from './MenPaiCareerGrid.vue';
import ImbalanceSection from './ImbalanceSection.vue';

// 职业物品占比饼图：独立拉取（careerOnly=true），不依赖主列表是否勾选"仅职业物品"
const careerData = ref<any>(null);
const careerItems = computed(() => careerData.value?.items ?? []);

const menpais = ref<any[]>([]);
const rankLevels = ref<number[]>([]);
const menPai = ref<number | null>(null);
const rankLevel = ref<number | null>(null);
const top = ref(50);
const careerOnly = ref(false);

// 时间范围：按 first_seen_at 过滤，默认近 7 天
const sinceDays = ref<number | null>(7);
const sinceOptions = [
  { value: 1, label: '近1天' },
  { value: 3, label: '近3天' },
  { value: 7, label: '近7天' },
  { value: 14, label: '近14天' },
];

const usage = ref<any>(null);
const stats = ref<any>(null);
const job = ref<any>(null);
const fetching = ref(false);

// 自动拉取调度
const schedule = ref<any>(null);
const autoEnabled = ref(true);
const autoInterval = ref(1);
const savingSchedule = ref(false);

let pollTimer: number | null = null;

function autoStatusText(s: string) {
  return s === 'running' ? '进行中' : s === 'done' ? '成功' : s === 'failed' ? '失败' : s;
}

async function loadSchedule() {
  const { data } = await api.get('/lineup/schedule');
  schedule.value = data;
  autoEnabled.value = data.enabled;
  autoInterval.value = data.interval_hours;
}

async function saveSchedule() {
  if (autoEnabled.value && (autoInterval.value < 1 || autoInterval.value > 168)) {
    alert('拉取间隔需在 1~168 小时之间');
    return;
  }
  savingSchedule.value = true;
  try {
    const { data } = await api.put('/lineup/schedule', {
      enabled: autoEnabled.value,
      interval_hours: autoInterval.value,
    });
    schedule.value = data;
    autoEnabled.value = data.enabled;
    autoInterval.value = data.interval_hours;
  } catch (e: any) {
    alert('保存失败：' + (e.response?.data?.detail || e.message));
  } finally {
    savingSchedule.value = false;
  }
}

const statusText = computed(() => {
  const s = job.value?.status;
  return s === 'running' ? '拉取进行中' : s === 'done' ? '拉取完成' : s === 'failed' ? '拉取失败' : s;
});

function fmt(iso: string) {
  try { return new Date(iso).toLocaleString('zh-CN'); } catch { return iso; }
}

async function loadOptions() {
  const { data } = await api.get('/lineup/menpais');
  menpais.value = data.menpais;
  rankLevels.value = data.rank_levels;
}

async function loadUsage() {
  const params: any = { top: top.value, careerOnly: careerOnly.value };
  if (menPai.value != null) params.menPai = menPai.value;
  if (rankLevel.value != null) params.rankLevel = rankLevel.value;
  if (sinceDays.value != null) params.sinceDays = sinceDays.value;
  const { data } = await api.get('/lineup/usage', { params });
  usage.value = data;
}

// 职业物品占比饼图独立数据：始终 careerOnly=true，跟随门派/段位筛选
async function loadCareerData() {
  const params: any = { top: 15, careerOnly: true };
  if (menPai.value != null) params.menPai = menPai.value;
  if (rankLevel.value != null) params.rankLevel = rankLevel.value;
  if (sinceDays.value != null) params.sinceDays = sinceDays.value;
  const { data } = await api.get('/lineup/usage', { params });
  careerData.value = data;
}

// 门派/段位筛选变化：主列表与职业饼图都刷新
function onFilterChange() {
  loadUsage();
  loadCareerData();
}

async function loadStats() {
  const { data } = await api.get('/lineup/stats');
  stats.value = data;
}

async function loadJob() {
  const { data } = await api.get('/lineup/job');
  job.value = data.job;
  fetching.value = data.running || data.job?.status === 'running';
  // 拉取进行中时持续轮询；完成后刷新数据并停止轮询
  if (fetching.value) {
    startPoll();
  } else {
    stopPoll();
    await Promise.all([loadStats(), loadUsage(), loadCareerData(), loadSchedule()]);
  }
}

function startPoll() {
  if (pollTimer) return;
  pollTimer = window.setInterval(loadJob, 3000);
}
function stopPoll() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
}

async function triggerFetch() {
  try {
    await api.post('/lineup/fetch');
    fetching.value = true;
    startPoll();
  } catch (e: any) {
    if (e.response?.status === 409) {
      alert('已有拉取任务在运行');
    } else {
      alert('触发失败：' + (e.response?.data?.detail || e.message));
    }
  }
}

onMounted(async () => {
  await loadOptions();
  await Promise.all([loadStats(), loadUsage(), loadCareerData(), loadJob(), loadSchedule()]);
});
onUnmounted(stopPoll);
</script>

<style scoped>
.lineup-page { padding: 24px; }
/* 顶部工具栏 */
.toolbar {
  padding: 12px 14px; margin-bottom: 16px;
  background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius);
}
.toolbar-row {
  display: flex; justify-content: space-between; align-items: center; gap: 16px; flex-wrap: wrap;
}
.toolbar-row h2 { font-size: 18px; color: var(--text-primary); }
.controls { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
.controls .switch, .controls .interval {
  display: flex; align-items: center; gap: 6px;
  font-size: 13px; color: var(--text-secondary);
}
.controls input[type="number"] {
  padding: 6px 8px; background: var(--bg-primary); border: 1px solid var(--border);
  border-radius: var(--radius); color: var(--text-primary); font-size: 13px; outline: none;
}
.btn {
  padding: 8px 18px; border: none; border-radius: var(--radius);
  background: var(--accent); color: #fff; font-size: 14px; cursor: pointer;
}
.btn:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-small {
  padding: 6px 14px; border: none; border-radius: var(--radius);
  background: var(--accent); color: #fff; font-size: 13px; cursor: pointer;
}
.btn-small:disabled { opacity: 0.6; cursor: not-allowed; }
.toolbar-status {
  display: flex; gap: 8px; align-items: center; flex-wrap: wrap;
  margin-top: 10px; font-size: 12px; color: var(--text-secondary);
}
.toolbar-status .sep { color: var(--text-muted); }
.status.running { color: var(--accent); }
.status.done { color: #27ae60; }
.status.failed { color: var(--danger); }
.muted { color: var(--text-muted); }
.err { color: var(--danger); }
.stat-cards { display: flex; gap: 16px; margin-bottom: 16px; }
.stat-card {
  flex: 1; background: var(--bg-card); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 16px; text-align: center;
}
.stat-card .num { font-size: 24px; font-weight: 700; color: var(--text-primary); }
.stat-card .label { font-size: 12px; color: var(--text-muted); margin-top: 4px; }
.filters {
  display: flex; gap: 18px; align-items: center; flex-wrap: wrap;
  padding: 14px; margin-bottom: 16px;
  background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius);
}
.filters label { font-size: 13px; color: var(--text-secondary); display: flex; align-items: center; gap: 6px; }
.filters select, .filters input {
  padding: 6px 8px; background: var(--bg-primary); border: 1px solid var(--border);
  border-radius: var(--radius); color: var(--text-primary); font-size: 13px; outline: none;
}
.filters .checkbox { cursor: pointer; }
.empty { padding: 40px; text-align: center; color: var(--text-muted); }
.charts { display: flex; flex-direction: column; gap: 16px; }
.charts-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
</style>
