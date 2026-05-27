<template>
  <div class="page">
    <h2>游戏管理</h2>
    <div class="schedule-bar">
      <span class="schedule-dot" :class="scheduleEnabled ? 'active' : 'inactive'"></span>
      <span v-if="scheduleEnabled">
        定时自动爬取已启用 · 间隔 {{ scheduleInterval }} 分钟 · 下次执行：{{ scheduleNextRun }}
      </span>
      <span v-else style="color: var(--text-muted)">定时自动爬取未启用</span>
    </div>
    <GameForm @created="load" />

    <div v-if="!games.length" class="empty">还没有添加游戏</div>

    <div v-for="g in games" :key="g.id" class="game-card">
      <!-- 游戏主行 -->
      <div class="game-row">
        <img v-if="g.icon_url" :src="g.icon_url" class="game-icon" />
        <div class="game-icon-placeholder" v-else>🎮</div>
        <div class="game-info">
          <div class="game-name">{{ g.name }}</div>
          <div class="game-meta">App ID: {{ g.steam_app_id || '—' }} · {{ g.comment_count }} 条评论</div>
        </div>
        <div class="game-actions">
          <button class="btn-del" @click="askDelete(g)">删除</button>
        </div>
      </div>

      <!-- 详情面板（常显） -->
      <div class="game-detail">

        <!-- 爬虫状态 -->
        <div class="detail-section">
          <div class="detail-title">爬取状态</div>
          <div v-if="!crawlJobs[g.id]" class="loading-text">加载中…</div>
          <div v-else class="platform-jobs">
            <div v-for="item in crawlJobs[g.id]" :key="item.platform" class="platform-job">

              <!-- 左侧：平台名 + 总量 -->
              <span class="platform-name">{{ PLATFORM_LABEL[item.platform] ?? item.platform }}</span>
              <span class="job-total">共 {{ item.total_comments }} 条</span>

              <!-- 中间：状态流水线 -->
              <div class="job-pipeline">

                <template v-if="isSending(g.id, item.platform)">
                  <span class="pipe-dot sending"></span>
                  <span class="pipe-label">前端已发送，等待响应…</span>
                </template>

                <template v-else-if="getPostError(g.id, item.platform)">
                  <span class="pipe-dot failed"></span>
                  <span class="pipe-label err">请求失败：{{ getPostError(g.id, item.platform) }}</span>
                </template>

                <template v-else v-for="activeJob in [getActiveJob(g.id, item.platform)]" :key="'aj'">

                  <template v-if="activeJob && activeJob.status === 'running' && activeJob.phase === 'crawl'">
                    <span class="pipe-dot running"></span>
                    <span class="pipe-label">爬取中</span>
                    <div class="pipe-progress">
                      <span class="pipe-time">已用 {{ formatDuration(getElapsedSec(activeJob.started_at)) }}</span>
                      <span class="pipe-sep">/</span>
                      <span class="pipe-time">预计 {{ formatDuration(getEstimateSec(g.id, item.platform)) }}</span>
                      <span class="pipe-remain">{{ getRemainingText(activeJob.started_at, g.id, item.platform) }}</span>
                    </div>
                    <div class="pipe-bar">
                      <div
                        class="pipe-bar-fill"
                        :class="{ overrun: getProgressPct(activeJob.started_at, g.id, item.platform) >= 100 }"
                        :style="{ width: getProgressPct(activeJob.started_at, g.id, item.platform) + '%' }"
                      />
                    </div>
                  </template>

                  <template v-else-if="activeJob && activeJob.status === 'running' && activeJob.phase === 'ai'">
                    <span class="pipe-dot ai"></span>
                    <span class="pipe-label">AI 分析中</span>
                    <span class="pipe-badge ai-badge">{{ activeJob.ai_done }}/{{ activeJob.ai_total }}</span>
                    <div class="pipe-bar">
                      <div
                        class="pipe-bar-fill ai-fill"
                        :style="{ width: (activeJob.ai_total > 0 ? Math.round(activeJob.ai_done / activeJob.ai_total * 100) : 0) + '%' }"
                      />
                    </div>
                  </template>

                  <template v-else-if="activeJob && activeJob.status === 'done'">
                    <span class="pipe-dot done"></span>
                    <span class="pipe-label">爬取完成</span>
                    <span class="pipe-badge success">+{{ activeJob.new_count }} 新增</span>
                    <template v-if="activeJob.ai_total > 0">
                      <span class="pipe-sep">·</span>
                      <span class="pipe-label muted">已分析 {{ activeJob.ai_total }} 条</span>
                    </template>
                    <span class="pipe-time muted">{{ activeJob.finished_at ? formatTime(activeJob.finished_at) : '' }}</span>
                  </template>

                  <template v-else-if="activeJob && activeJob.status === 'failed'">
                    <span class="pipe-dot failed"></span>
                    <span class="pipe-label err">爬取失败</span>
                    <span class="pipe-errmsg" :title="activeJob.error_msg">{{ activeJob.error_msg || '未知错误' }}</span>
                  </template>

                  <template v-else-if="activeJob && activeJob.status === 'running'">
                    <span class="pipe-dot running"></span>
                    <span class="pipe-label">爬取中</span>
                    <div class="pipe-bar"><div class="pipe-bar-fill indeterminate"/></div>
                  </template>

                  <template v-else>
                    <span class="pipe-dot none"></span>
                    <span class="pipe-label muted">从未爬取</span>
                  </template>

                </template>

              </div>

              <!-- 右侧：按钮组 -->
              <div class="job-btns">
                <button
                  class="btn-clear"
                  :disabled="item.total_comments === 0 || isBusy(g.id, item.platform)"
                  @click="askClear(g, item.platform, item.total_comments)"
                >清空</button>
                <button
                  class="btn-trial"
                  :disabled="isBusy(g.id, item.platform) || !isConfigured(g, item.platform)"
                  :title="!isConfigured(g, item.platform) ? (item.platform === 'qq' ? '请先在下方配置 QQ 群号并保存' : '请先在下方配置频道 ID 并保存') : '只抓5条，快速验证爬虫机制是否正常'"
                  @click="triggerTrial(g, item.platform)"
                >试爬</button>
                <button
                  class="btn-crawl"
                  :disabled="isBusy(g.id, item.platform) || !isConfigured(g, item.platform)"
                  :title="!isConfigured(g, item.platform) ? (item.platform === 'qq' ? '请先在下方配置 QQ 群号并保存' : '请先在下方配置频道 ID 并保存') : ''"
                  @click="triggerCrawl(g, item.platform)"
                >{{ getCrawlBtnText(g.id, item.platform) }}</button>
              </div>

            </div>
          </div>
        </div>

        <!-- Discord 频道配置 -->
        <div class="detail-section">
          <div class="detail-title">
            Discord 频道 ID
            <span v-if="discordSaveStatus[g.id]" class="sw-save-hint" :class="discordSaveStatus[g.id]">
              {{ discordSaveStatus[g.id] === 'saving' ? '保存中…' : discordSaveStatus[g.id] === 'error' ? '保存失败' : '已保存 ✓' }}
            </span>
          </div>
          <input
            class="sw-input"
            placeholder="输入频道 ID 后回车添加"
            v-model="discordInput[g.id]"
            @keydown.enter.prevent="addDiscordChannel(g.id, $event)"
          />
          <div v-if="discordDupWarning[g.id]" class="sw-dup-hint">ID 格式无效或已存在（应为 17-19 位纯数字）</div>
          <div v-if="editingDiscordIds[g.id]?.length" class="sw-tags-list">
            <span v-for="(chId, i) in editingDiscordIds[g.id]" :key="i" class="sw-tag discord-tag">
              <!-- 内联重命名：点击名称触发 -->
              <template v-if="renamingChannel?.gameId === g.id && renamingChannel?.channelId === chId">
                <input
                  class="ch-name-input"
                  v-model="renameInput"
                  placeholder="输入频道名称"
                  @blur="saveChannelName(g.id, chId)"
                  @keydown.enter.prevent="saveChannelName(g.id, chId)"
                  @keydown.escape.prevent="renamingChannel = null"
                  @click.stop
                />
              </template>
              <template v-else>
                <span
                  class="ch-label"
                  :title="'点击重命名\n频道 ID：' + chId"
                  @click.stop="startRename(g.id, chId)"
                >{{ discordChannelNames[g.id]?.[chId] || chId }}</span>
              </template>
              <button class="sw-del" @click.stop="removeDiscordChannel(g.id, i)">×</button>
            </span>
          </div>
          <div v-else class="discord-hint">尚未配置频道 ID</div>
          <div class="discord-hint" style="margin-top:4px">💡 点击频道 ID 可设置自定义名称</div>
        </div>

        <!-- QQ 群号配置 -->
        <div class="detail-section">
          <div class="detail-title">
            QQ 群号
            <span v-if="qqSaveStatus[g.id]" class="sw-save-hint" :class="qqSaveStatus[g.id]">
              {{ qqSaveStatus[g.id] === 'saving' ? '保存中…' : qqSaveStatus[g.id] === 'error' ? '保存失败' : '已保存 ✓' }}
            </span>
          </div>
          <input
            class="sw-input"
            placeholder="输入 QQ 群号后回车添加"
            v-model="qqInput[g.id]"
            @keydown.enter.prevent="addQQGroup(g.id, $event)"
          />
          <div v-if="qqDupWarning[g.id]" class="sw-dup-hint">群号格式无效或已存在（应为 5-12 位纯数字）</div>
          <div v-if="editingQQIds[g.id]?.length" class="sw-tags-list">
            <span v-for="(gid, i) in editingQQIds[g.id]" :key="i" class="sw-tag qq-tag">
              {{ gid }}<button class="sw-del" @click="removeQQGroup(g.id, i)">×</button>
            </span>
          </div>
          <div v-else class="discord-hint">尚未配置 QQ 群号</div>
        </div>

      </div>
    </div>

    <!-- 删除游戏确认弹窗 -->
    <Teleport to="body">
      <div v-if="deleteTarget" class="overlay" @click.self="deleteTarget = null">
        <div class="confirm-box">
          <div class="confirm-title">确认删除</div>
          <p class="confirm-body">
            即将删除游戏 <strong>{{ deleteTarget.name }}</strong>。
            <template v-if="deleteTarget.comment_count > 0">
              <br />关联的 <strong>{{ deleteTarget.comment_count }}</strong> 条评论也将一并删除。
            </template>
          </p>
          <div class="confirm-btns">
            <button class="btn-cancel" @click="deleteTarget = null">取消</button>
            <button class="btn-danger" @click="confirmDelete">确认删除</button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- 清空来源数据确认弹窗 -->
    <Teleport to="body">
      <div v-if="clearTarget" class="overlay" @click.self="clearTarget = null">
        <div class="confirm-box">
          <div class="confirm-title">确认清空</div>
          <p class="confirm-body">
            即将清空游戏 <strong>{{ clearTarget.gameName }}</strong> 的
            <strong>{{ PLATFORM_LABEL[clearTarget.platform] ?? clearTarget.platform }}</strong> 全部数据
            （共 <strong>{{ clearTarget.count }}</strong> 条）。
            <br />此操作不可撤销。
          </p>
          <div v-if="clearError" class="confirm-error">{{ clearError }}</div>
          <div class="confirm-btns">
            <button class="btn-cancel" @click="clearTarget = null; clearError = ''">取消</button>
            <button class="btn-danger" :disabled="clearing" @click="confirmClear">
              {{ clearing ? '清空中…' : '确认清空' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue';
import api from '../../api';
import GameForm from './GameForm.vue';

const PLATFORM_LABEL: Record<string, string> = {
  steam_store: 'Steam评价', steam_hub: 'Steam论坛',
  discord: 'Discord', qq: 'QQ群', xiaoheihe: '小黑盒',
};

interface GameRow {
  id: string;
  name: string;
  steam_app_id: string | null;
  icon_url: string | null;
  comment_count: number;
  discord_channel_ids: string[];
  discord_channel_names: Record<string, string>;
  qq_group_ids: string[];
  created_at: string;
}

interface JobData {
  id: string | null;
  status: string | null;
  phase: string | null;
  new_count: number;
  ai_total: number;
  ai_done: number;
  started_at: string | null;
  finished_at: string | null;
  error_msg: string | null;
}

const games = ref<GameRow[]>([]);
const crawlJobs = ref<Record<string, any[]>>({});

const scheduleEnabled = ref(false);
const scheduleInterval = ref(120);
const scheduleNextRun = ref('—');
let scheduleTimer: number | null = null;

async function loadSchedule() {
  try {
    const { data } = await api.get('/crawlers/schedule');
    scheduleEnabled.value = data.enabled;
    scheduleInterval.value = data.interval_minutes;
    if (data.next_run_time) {
      const d = new Date(data.next_run_time);
      scheduleNextRun.value = d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
    } else {
      scheduleNextRun.value = '—';
    }
  } catch {}
}
const editingDiscordIds = ref<Record<string, string[]>>({});
const discordInput = ref<Record<string, string>>({});
const discordSaveStatus = ref<Record<string, string | null>>({});
const discordDupWarning = ref<Record<string, boolean>>({});

// Discord 频道自定义名称
const discordChannelNames = ref<Record<string, Record<string, string>>>({}); // gameId → {channelId → name}
const renamingChannel = ref<{ gameId: string; channelId: string } | null>(null);
const renameInput = ref('');

const editingQQIds = ref<Record<string, string[]>>({});
const qqInput = ref<Record<string, string>>({});
const qqSaveStatus = ref<Record<string, string | null>>({});
const qqDupWarning = ref<Record<string, boolean>>({});
const deleteTarget = ref<GameRow | null>(null);
const clearTarget = ref<{ gameId: string; gameName: string; platform: string; count: number } | null>(null);
const clearing = ref(false);
const clearError = ref('');

const postSending = ref<Set<string>>(new Set());
const postError = ref<Record<string, string>>({});
const trackedJobId = ref<Record<string, string>>({});
const trackedJobData = ref<Record<string, JobData>>({});
const trackedTimers = ref<Record<string, number>>({});
const crawlDurationSec = ref<Record<string, number>>({});

let pollTimer: number | null = null;
let tickTimer: number | null = null;
const now = ref(Date.now());

const ESTIMATED_SECONDS: Record<string, number> = {
  steam_store: 30,
  steam_hub:   240,
  xiaoheihe:   120,
};

function getElapsedSec(startedAt: string): number {
  const start = new Date(startedAt.endsWith('Z') ? startedAt : startedAt + 'Z');
  return Math.max(0, Math.floor((now.value - start.getTime()) / 1000));
}
function _storeDuration(gameId: string, platform: string, startedAt: string | null, finishedAt: string | null) {
  if (!startedAt || !finishedAt) return;
  const sec = Math.round((new Date(finishedAt).getTime() - new Date(startedAt).getTime()) / 1000);
  if (sec > 0) crawlDurationSec.value[`${gameId}_${platform}`] = sec;
}
function getEstimateSec(gameId: string, platform: string): number {
  return crawlDurationSec.value[`${gameId}_${platform}`] ?? ESTIMATED_SECONDS[platform] ?? 120;
}
function getProgressPct(startedAt: string, gameId: string, platform: string): number {
  return Math.min(100, Math.round(getElapsedSec(startedAt) / getEstimateSec(gameId, platform) * 100));
}
function formatDuration(sec: number): string {
  const m = Math.floor(Math.abs(sec) / 60);
  const s = Math.abs(sec) % 60;
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}
function getRemainingText(startedAt: string, gameId: string, platform: string): string {
  const remaining = getEstimateSec(gameId, platform) - getElapsedSec(startedAt);
  if (remaining <= 0) return '即将完成…';
  return `剩余约 ${formatDuration(remaining)}`;
}
function formatTime(t: string) {
  const iso = t.endsWith('Z') || t.includes('+') ? t : t + 'Z';
  return new Date(iso).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
}

function getActiveJob(gameId: string, platform: string): JobData | null {
  const key = `${gameId}_${platform}`;
  const tracked = trackedJobData.value[key];
  if (tracked) return tracked;
  const list = crawlJobs.value[gameId];
  if (!list) return null;
  const item = list.find((it: any) => it.platform === platform);
  return item?.job ?? null;
}

function isBusy(gameId: string, platform: string): boolean {
  const key = `${gameId}_${platform}`;
  if (postSending.value.has(key)) return true;
  const tracked = trackedJobData.value[key];
  if (tracked && tracked.status === 'running') return true;
  return false;
}

function isSending(gameId: string, platform: string): boolean {
  return postSending.value.has(`${gameId}_${platform}`);
}
function getPostError(gameId: string, platform: string): string | null {
  return postError.value[`${gameId}_${platform}`] ?? null;
}

function isConfigured(g: GameRow, platform: string): boolean {
  if (platform === 'discord') return (g.discord_channel_ids ?? []).length > 0;
  if (platform === 'qq') return (g.qq_group_ids ?? []).length > 0;
  return !!g.steam_app_id;
}

function getCrawlBtnText(gameId: string, platform: string): string {
  const key = `${gameId}_${platform}`;
  if (postSending.value.has(key)) return '发送中…';
  const tracked = trackedJobData.value[key];
  if (tracked?.status === 'running') {
    return tracked.phase === 'ai' ? 'AI分析中…' : '爬取中…';
  }
  return '立即爬取';
}

async function triggerCrawl(g: GameRow, platform: string) {
  const key = `${g.id}_${platform}`;
  delete postError.value[key];
  postSending.value = new Set(postSending.value).add(key);
  try {
    const resp = await api.post(`/crawlers/${platform}/run`, null, { params: { game_id: g.id } });
    const jobId: string = resp.data.job_id;
    postSending.value.delete(key);
    postSending.value = new Set(postSending.value);
    startTracking(key, jobId, g.id);
  } catch (e: any) {
    const msg = (e?.response?.data?.detail ?? e?.message ?? '未知错误') as string;
    postSending.value.delete(key);
    postSending.value = new Set(postSending.value);
    postError.value = { ...postError.value, [key]: msg };
  }
}

async function triggerTrial(g: GameRow, platform: string) {
  const key = `${g.id}_${platform}`;
  delete postError.value[key];
  postSending.value = new Set(postSending.value).add(key);
  try {
    const resp = await api.post(`/crawlers/${platform}/trial`, null, { params: { game_id: g.id } });
    const jobId: string = resp.data.job_id;
    postSending.value.delete(key);
    postSending.value = new Set(postSending.value);
    startTracking(key, jobId, g.id);
  } catch (e: any) {
    const msg = (e?.response?.data?.detail ?? e?.message ?? '未知错误') as string;
    postSending.value.delete(key);
    postSending.value = new Set(postSending.value);
    postError.value = { ...postError.value, [key]: msg };
  }
}

function startTracking(key: string, jobId: string, gameId: string) {
  if (trackedTimers.value[key]) {
    clearInterval(trackedTimers.value[key]);
  }
  trackedJobId.value = { ...trackedJobId.value, [key]: jobId };
  trackedJobData.value = {
    ...trackedJobData.value,
    [key]: {
      id: jobId, status: 'running', phase: 'crawl',
      new_count: 0, ai_total: 0, ai_done: 0,
      started_at: new Date().toISOString(), finished_at: null, error_msg: null,
    },
  };
  fetchTrackedJob(key, jobId, gameId);
  trackedTimers.value[key] = window.setInterval(() => {
    fetchTrackedJob(key, jobId, gameId);
  }, 2000);
}

async function fetchTrackedJob(key: string, jobId: string, gameId: string) {
  try {
    const { data } = await api.get(`/crawlers/jobs/${jobId}`);
    trackedJobData.value = { ...trackedJobData.value, [key]: data };
    if (data.status === 'done' || data.status === 'failed') {
      if (trackedTimers.value[key]) {
        clearInterval(trackedTimers.value[key]);
        delete trackedTimers.value[key];
      }
      if (data.status === 'done') {
        const platform = key.substring(gameId.length + 1);
        _storeDuration(gameId, platform, data.started_at, data.finished_at);
      }
      await loadJobs(gameId);
      const next = { ...trackedJobData.value };
      delete next[key];
      trackedJobData.value = next;
      await load();
    }
  } catch {}
}

async function load() {
  const { data } = await api.get('/games');
  games.value = data;
  // 初始化 discord / qq 编辑态（只对尚未初始化的游戏）
  for (const g of data) {
    if (!editingDiscordIds.value[g.id]) {
      editingDiscordIds.value[g.id] = [...(g.discord_channel_ids ?? [])];
    }
    if (!editingQQIds.value[g.id]) {
      editingQQIds.value[g.id] = [...(g.qq_group_ids ?? [])];
    }
    // 始终同步最新的频道命名（服务端可能更新）
    discordChannelNames.value[g.id] = { ...(g.discord_channel_names ?? {}) };
  }
}

async function loadAllJobs() {
  for (const g of games.value) {
    loadJobs(g.id);
  }
}

async function loadJobs(gameId: string) {
  try {
    const { data } = await api.get('/crawlers/jobs', { params: { game_id: gameId } });
    crawlJobs.value = { ...crawlJobs.value, [gameId]: data };
    for (const item of data) {
      if (item.job?.status === 'done') {
        _storeDuration(gameId, item.platform, item.job.started_at, item.job.finished_at);
      }
    }
  } catch {
    crawlJobs.value = { ...crawlJobs.value, [gameId]: [] };
  }
}

// ── Clear platform data ────────────────────────────────────────────────────
function askClear(g: GameRow, platform: string, count: number) {
  clearError.value = '';
  clearTarget.value = { gameId: g.id, gameName: g.name, platform, count };
}

async function confirmClear() {
  if (!clearTarget.value) return;
  clearing.value = true;
  clearError.value = '';
  try {
    await api.post('/comments/clear', null, { params: { game_id: clearTarget.value.gameId, platform: clearTarget.value.platform } });
    clearTarget.value = null;
    await load();
    await loadAllJobs();
  } catch (e: any) {
    clearError.value = e?.response?.data?.detail ?? e?.message ?? '清空失败，请重试';
  } finally {
    clearing.value = false;
  }
}

// ── Discord Channels ───────────────────────────────────────────────────────
function _addDiscordId(gameId: string, raw: string) {
  const id = raw.trim();
  if (!id) return false;
  if (!/^\d{17,20}$/.test(id)) {
    discordDupWarning.value = { ...discordDupWarning.value, [gameId]: true };
    setTimeout(() => { discordDupWarning.value = { ...discordDupWarning.value, [gameId]: false }; }, 3000);
    return false;
  }
  const list = editingDiscordIds.value[gameId] ?? [];
  if (list.includes(id)) {
    discordDupWarning.value = { ...discordDupWarning.value, [gameId]: true };
    setTimeout(() => { discordDupWarning.value = { ...discordDupWarning.value, [gameId]: false }; }, 2000);
    return false;
  }
  editingDiscordIds.value = { ...editingDiscordIds.value, [gameId]: [...list, id] };
  return true;
}
async function _persistDiscordChannels(gameId: string) {
  const game = games.value.find(g => g.id === gameId);
  if (!game) return;
  discordSaveStatus.value = { ...discordSaveStatus.value, [gameId]: 'saving' };
  try {
    const ids = editingDiscordIds.value[gameId] ?? [];
    await api.put(`/games/${gameId}`, { discord_channel_ids: ids });
    game.discord_channel_ids = [...ids];
    discordSaveStatus.value = { ...discordSaveStatus.value, [gameId]: 'saved' };
    setTimeout(() => { discordSaveStatus.value = { ...discordSaveStatus.value, [gameId]: null }; }, 2000);
  } catch {
    discordSaveStatus.value = { ...discordSaveStatus.value, [gameId]: 'error' };
    setTimeout(() => { discordSaveStatus.value = { ...discordSaveStatus.value, [gameId]: null }; }, 3000);
  }
}
async function addDiscordChannel(gameId: string, e: Event) {
  if (_addDiscordId(gameId, discordInput.value[gameId] ?? '')) {
    discordInput.value = { ...discordInput.value, [gameId]: '' };
    await _persistDiscordChannels(gameId);
  }
}
async function removeDiscordChannel(gameId: string, idx: number) {
  const list = [...(editingDiscordIds.value[gameId] ?? [])];
  list.splice(idx, 1);
  editingDiscordIds.value = { ...editingDiscordIds.value, [gameId]: list };
  await _persistDiscordChannels(gameId);
}

// ── Discord 频道命名 ──────────────────────────────────────────────────────────
function startRename(gameId: string, channelId: string) {
  renamingChannel.value = { gameId, channelId };
  renameInput.value = discordChannelNames.value[gameId]?.[channelId] ?? '';
  // nextTick 后聚焦
  import('vue').then(({ nextTick }) => nextTick(() => {
    const el = document.querySelector('.ch-name-input') as HTMLInputElement | null;
    el?.focus();
    el?.select();
  }));
}

async function saveChannelName(gameId: string, channelId: string) {
  renamingChannel.value = null;
  const name = renameInput.value.trim();
  const names = { ...(discordChannelNames.value[gameId] ?? {}) };
  if (name) {
    names[channelId] = name;
  } else {
    delete names[channelId]; // 空值 = 清除命名，显示回原始 ID
  }
  discordChannelNames.value = { ...discordChannelNames.value, [gameId]: names };
  try {
    await api.put(`/games/${gameId}`, { discord_channel_names: names });
  } catch {
    // 静默失败，下次 load 会重新同步
  }
}

// ── QQ Groups ─────────────────────────────────────────────────────────────
function _addQQId(gameId: string, raw: string) {
  const id = raw.trim();
  if (!id) return false;
  if (!/^\d{5,12}$/.test(id)) {
    qqDupWarning.value = { ...qqDupWarning.value, [gameId]: true };
    setTimeout(() => { qqDupWarning.value = { ...qqDupWarning.value, [gameId]: false }; }, 3000);
    return false;
  }
  const list = editingQQIds.value[gameId] ?? [];
  if (list.includes(id)) {
    qqDupWarning.value = { ...qqDupWarning.value, [gameId]: true };
    setTimeout(() => { qqDupWarning.value = { ...qqDupWarning.value, [gameId]: false }; }, 2000);
    return false;
  }
  editingQQIds.value = { ...editingQQIds.value, [gameId]: [...list, id] };
  return true;
}
async function _persistQQGroups(gameId: string) {
  const game = games.value.find(g => g.id === gameId);
  if (!game) return;
  qqSaveStatus.value = { ...qqSaveStatus.value, [gameId]: 'saving' };
  try {
    const ids = editingQQIds.value[gameId] ?? [];
    await api.put(`/games/${gameId}`, { qq_group_ids: ids });
    game.qq_group_ids = [...ids];
    qqSaveStatus.value = { ...qqSaveStatus.value, [gameId]: 'saved' };
    setTimeout(() => { qqSaveStatus.value = { ...qqSaveStatus.value, [gameId]: null }; }, 2000);
  } catch {
    qqSaveStatus.value = { ...qqSaveStatus.value, [gameId]: 'error' };
    setTimeout(() => { qqSaveStatus.value = { ...qqSaveStatus.value, [gameId]: null }; }, 3000);
  }
}
async function addQQGroup(gameId: string, _e: Event) {
  if (_addQQId(gameId, qqInput.value[gameId] ?? '')) {
    qqInput.value = { ...qqInput.value, [gameId]: '' };
    await _persistQQGroups(gameId);
  }
}
async function removeQQGroup(gameId: string, idx: number) {
  const list = [...(editingQQIds.value[gameId] ?? [])];
  list.splice(idx, 1);
  editingQQIds.value = { ...editingQQIds.value, [gameId]: list };
  await _persistQQGroups(gameId);
}

// ── Delete game ────────────────────────────────────────────────────────────
function askDelete(g: GameRow) { deleteTarget.value = g; }
async function confirmDelete() {
  if (!deleteTarget.value) return;
  await api.delete(`/games/${deleteTarget.value.id}`);
  deleteTarget.value = null;
  load();
}

onMounted(async () => {
  await load();
  await loadAllJobs();
  await loadSchedule();
  pollTimer = window.setInterval(loadAllJobs, 3000);
  tickTimer = window.setInterval(() => { now.value = Date.now(); }, 1000);
  scheduleTimer = window.setInterval(loadSchedule, 60000);
});

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer);
  if (tickTimer) clearInterval(tickTimer);
  if (scheduleTimer) clearInterval(scheduleTimer);
  Object.values(trackedTimers.value).forEach(clearInterval);
});
</script>

<style scoped>
.page { max-width: 900px; }
h2 { font-size: 22px; margin-bottom: 12px; }

.schedule-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 20px;
}
.schedule-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}
.schedule-dot.active   { background: var(--success); }
.schedule-dot.inactive { background: var(--text-muted); }

.empty {
  text-align: center;
  padding: 48px;
  color: var(--text-muted);
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
}

/* ── Game card ── */
.game-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  margin-bottom: 12px;
  overflow: hidden;
}

.game-row {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px 16px;
}

.game-icon { width: 40px; height: 40px; border-radius: 6px; object-fit: cover; flex-shrink: 0; }
.game-icon-placeholder { width: 40px; height: 40px; display: flex; align-items: center; justify-content: center; font-size: 22px; flex-shrink: 0; }

.game-info { flex: 1; }
.game-name { font-size: 15px; font-weight: 600; color: var(--text-primary); }
.game-meta { font-size: 12px; color: var(--text-secondary); margin-top: 2px; }

.game-actions { display: flex; align-items: center; gap: 10px; }
.btn-del { background: none; border: none; color: var(--danger); cursor: pointer; font-size: 13px; }

/* ── Detail panel ── */
.game-detail {
  border-top: 1px solid var(--border);
  padding: 16px;
  background: var(--bg-secondary);
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.detail-section {}
.detail-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 10px;
}

/* ── Platform jobs ── */
.platform-jobs { display: flex; flex-direction: column; gap: 8px; }
.platform-job {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
  color: var(--text-primary);
}
.platform-name { min-width: 80px; font-weight: 500; }
.job-total { min-width: 70px; color: var(--text-secondary); }

/* ── 状态流水线 ── */
.job-pipeline {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  min-width: 0;
}

.pipe-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}
.pipe-dot.sending   { background: var(--warning); animation: pulse-dot 1s ease-in-out infinite; }
.pipe-dot.running   { background: var(--accent);  animation: pulse-dot 1s ease-in-out infinite; }
.pipe-dot.ai        { background: #a855f7;         animation: pulse-dot 1s ease-in-out infinite; }
.pipe-dot.done      { background: var(--success); }
.pipe-dot.failed    { background: var(--danger); }
.pipe-dot.none      { background: var(--border); }
@keyframes pulse-dot {
  0%, 100% { opacity: 1;   transform: scale(1); }
  50%       { opacity: 0.5; transform: scale(0.8); }
}

.pipe-label        { font-size: 12px; color: var(--text-secondary); white-space: nowrap; }
.pipe-label.err    { color: var(--danger); }
.pipe-label.muted  { color: var(--text-muted); }

.pipe-badge         { font-size: 11px; padding: 1px 6px; border-radius: 4px; }
.pipe-badge.success { background: rgba(34,197,94,0.15);  color: var(--success); }
.pipe-badge.ai-badge{ background: rgba(168,85,247,0.15); color: #a855f7; }

.pipe-progress { display: flex; align-items: center; gap: 4px; }
.pipe-time       { font-size: 12px; color: var(--text-secondary); white-space: nowrap; }
.pipe-time.muted { color: var(--text-muted); }
.pipe-sep        { font-size: 12px; color: var(--border); }
.pipe-remain     { font-size: 12px; color: var(--warning); font-weight: 500; margin-left: 4px; white-space: nowrap; }

.pipe-errmsg {
  font-size: 12px;
  color: var(--danger);
  opacity: 0.8;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 220px;
  cursor: help;
}

.pipe-bar {
  flex-basis: 100%;
  height: 4px;
  background: var(--border);
  border-radius: 2px;
  overflow: hidden;
  margin-top: 2px;
}
.pipe-bar-fill {
  height: 100%;
  background: var(--accent);
  border-radius: 2px;
  transition: width 0.9s linear;
}
.pipe-bar-fill.ai-fill  { background: #a855f7; }
.pipe-bar-fill.overrun {
  background: var(--warning);
  animation: pulse-bar 1.2s ease-in-out infinite;
}
@keyframes pulse-bar {
  0%, 100% { opacity: 1; }
  50%       { opacity: 0.5; }
}
.pipe-bar-fill.indeterminate {
  width: 40% !important;
  animation: indeterminate-slide 1.2s ease-in-out infinite;
}
@keyframes indeterminate-slide {
  0%   { transform: translateX(-150%); }
  100% { transform: translateX(350%); }
}

/* ── 按钮组 ── */
.job-btns { display: flex; gap: 6px; flex-shrink: 0; align-self: flex-start; margin-top: 1px; }

.btn-clear {
  padding: 4px 10px;
  font-size: 12px;
  background: transparent;
  color: var(--danger);
  border: 1px solid var(--danger);
  border-radius: var(--radius);
  cursor: pointer;
  white-space: nowrap;
}
.btn-clear:hover:not(:disabled) { background: rgba(239,68,68,0.08); }
.btn-clear:disabled { opacity: 0.35; cursor: not-allowed; }

.btn-trial {
  padding: 4px 10px;
  font-size: 12px;
  background: transparent;
  color: var(--accent);
  border: 1px solid var(--accent);
  border-radius: var(--radius);
  cursor: pointer;
  white-space: nowrap;
}
.btn-trial:hover { background: rgba(99,102,241,0.08); }
.btn-trial:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-crawl {
  padding: 4px 12px;
  font-size: 12px;
  background: var(--accent);
  color: #fff;
  border: none;
  border-radius: var(--radius);
  cursor: pointer;
  white-space: nowrap;
}
.btn-crawl:disabled { opacity: 0.5; cursor: not-allowed; }
.loading-text { font-size: 13px; color: var(--text-muted); }

/* ── Discord channels / QQ groups ── */
.discord-hint { font-size: 11px; color: var(--text-muted); margin-top: 6px; }
.discord-tag { font-family: monospace; }
.qq-tag { font-family: monospace; }

/* ── 频道命名内联编辑 ── */
.ch-label {
  cursor: pointer;
  border-bottom: 1px dashed var(--text-muted);
  padding-bottom: 1px;
}
.ch-label:hover { color: var(--accent); border-bottom-color: var(--accent); }
.ch-name-input {
  width: 120px;
  padding: 1px 4px;
  background: var(--bg-primary);
  border: 1px solid var(--accent);
  border-radius: 3px;
  color: var(--text-primary);
  font-size: 12px;
  font-family: monospace;
  outline: none;
}

/* ── Shared input/tag styles ── */
.sw-input {
  width: 100%;
  padding: 6px 10px;
  background: var(--bg-primary);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  outline: none;
  font-size: 12px;
  color: var(--text-primary);
  box-sizing: border-box;
}
.sw-input:focus { border-color: var(--accent); }
.sw-save-hint {
  font-size: 11px;
  font-weight: normal;
  margin-left: 8px;
  text-transform: none;
  letter-spacing: 0;
}
.sw-save-hint.saving { color: var(--text-muted); }
.sw-save-hint.saved  { color: var(--success); }
.sw-save-hint.error  { color: var(--danger); }
.sw-dup-hint {
  font-size: 11px;
  color: var(--warning);
  margin-top: 4px;
}
.sw-tags-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 10px;
}
.sw-tag {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  background: var(--bg-hover);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 2px 4px 2px 8px;
  font-size: 12px;
  color: var(--text-primary);
}
.sw-del {
  background: none;
  border: none;
  cursor: pointer;
  color: var(--text-muted);
  font-size: 13px;
  padding: 0 2px;
  line-height: 1;
}
.sw-del:hover { color: var(--danger); }

/* ── Confirm dialogs ── */
.overlay {
  position: fixed; inset: 0;
  background: rgba(0,0,0,0.5);
  display: flex; align-items: center; justify-content: center;
  z-index: 1000;
}
.confirm-box {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 24px;
  width: 380px;
}
.confirm-title { font-size: 16px; font-weight: 600; margin-bottom: 12px; }
.confirm-body { font-size: 14px; color: var(--text-secondary); line-height: 1.6; margin-bottom: 12px; }
.confirm-error { font-size: 13px; color: var(--danger); margin-bottom: 12px; }
.confirm-btns { display: flex; gap: 10px; justify-content: flex-end; }
.btn-cancel {
  padding: 7px 18px; font-size: 13px;
  background: var(--bg-hover); border: 1px solid var(--border);
  border-radius: var(--radius); color: var(--text-primary); cursor: pointer;
}
.btn-danger {
  padding: 7px 18px; font-size: 13px;
  background: var(--danger); border: none;
  border-radius: var(--radius); color: #fff; cursor: pointer;
}
.btn-danger:disabled { opacity: 0.6; cursor: not-allowed; }
</style>
