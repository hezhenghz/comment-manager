<template>
  <div class="page">
    <!-- 顶部操作栏 -->
    <div class="toolbar">
      <div class="filters">
        <input
          v-model="filters.keyword"
          placeholder="搜索公告标题…"
          class="search-input"
          @keyup.enter="onFilter"
        />
        <button class="btn-search" @click="onFilter">搜索</button>
      </div>
      <div class="sync-area">
        <span class="last-sync" v-if="syncStatus.last_sync_at">
          上次同步：{{ formatTime(syncStatus.last_sync_at) }}
        </span>
        <span class="last-sync" v-else>尚未同步</span>
        <button
          v-if="authStore.user?.is_admin"
          class="btn-sync"
          :disabled="syncStatus.is_syncing || syncing"
          @click="doSync"
        >
          {{ syncStatus.is_syncing || syncing ? '同步中…' : '手动同步' }}
        </button>
      </div>
    </div>

    <!-- 统计卡片 -->
    <div class="stat-cards">
      <div class="stat-card">
        <div class="stat-val">{{ stats.total }}</div>
        <div class="stat-label">公告总数</div>
      </div>
      <div class="stat-card">
        <div class="stat-val">{{ stats.today_new }}</div>
        <div class="stat-label">今日新增</div>
      </div>
    </div>

    <!-- 列表 -->
    <div class="list-wrap">
      <div v-if="loading" class="loading">加载中…</div>
      <div v-else-if="!items.length" class="empty">暂无公告（请先在右上角触发同步）</div>
      <template v-else>
        <div
          v-for="ann in items"
          :key="ann.id"
          class="ann-card"
        >
          <div class="ann-head">
            <div class="ann-title-row">
              <span class="ann-title">{{ ann.title_zh }}</span>
              <span v-if="ann.is_translated" class="badge-mt" title="由英文/其他语言机器翻译">机翻</span>
            </div>
            <span class="ann-date">{{ formatDate(ann.published_at) }}</span>
          </div>
          <div class="ann-body-wrap">
            <div class="announcement-body" v-html="ann.body_zh"></div>
            <a
              v-if="ann.source_url"
              class="ann-source"
              :href="ann.source_url"
              target="_blank"
              rel="noopener"
            >查看 Steam 原文 ↗</a>
          </div>
        </div>
      </template>
    </div>

    <!-- 分页 -->
    <div class="pagination" v-if="total > perPage">
      <button :disabled="page <= 1" @click="goPage(page - 1)">‹ 上一页</button>
      <span>第 {{ page }} / {{ Math.ceil(total / perPage) }} 页，共 {{ total }} 条</span>
      <button :disabled="page >= Math.ceil(total / perPage)" @click="goPage(page + 1)">下一页 ›</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, watch } from 'vue';
import api from '../../api';
import { useAuthStore } from '../../stores/auth';
import { useGameStore } from '../../stores/game';

const authStore = useAuthStore();
const gameStore = useGameStore();

const items      = ref<any[]>([]);
const total      = ref(0);
const page       = ref(1);
const perPage    = ref(20);
const loading    = ref(false);
const syncing    = ref(false);

const stats = reactive({ total: 0, today_new: 0 });
const syncStatus = reactive({
  last_sync_at: null as string | null,
  is_syncing:   false,
});
const filters = reactive({ keyword: '' });

onMounted(async () => {
  await Promise.all([loadList(), loadStats(), loadSyncStatus()]);
});

// 切换游戏时刷新列表与统计
watch(() => gameStore.selectedGameId, () => {
  page.value = 1;
  Promise.all([loadList(), loadStats()]);
});

async function loadList() {
  loading.value = true;
  try {
    const params: Record<string, any> = {
      page:     page.value,
      per_page: perPage.value,
    };
    if (gameStore.selectedGameId) params.game_id = gameStore.selectedGameId;
    if (filters.keyword)          params.keyword = filters.keyword;

    const { data } = await api.get('/announcements', { params });
    items.value = data.items;
    total.value = data.total;
  } catch (e) {
    console.error('[announcements] loadList error', e);
  } finally {
    loading.value = false;
  }
}

async function loadStats() {
  try {
    const params = gameStore.selectedGameId ? { game_id: gameStore.selectedGameId } : {};
    const { data } = await api.get('/announcements/stats', { params });
    Object.assign(stats, data);
  } catch {}
}

async function loadSyncStatus() {
  try {
    const { data } = await api.get('/announcements/sync/status');
    Object.assign(syncStatus, data);
  } catch {}
}

function onFilter() {
  page.value = 1;
  loadList();
}

function goPage(p: number) {
  page.value = p;
  loadList();
}

async function doSync() {
  if (syncing.value || syncStatus.is_syncing) return;
  syncing.value = true;
  try {
    const params = gameStore.selectedGameId ? { game_id: gameStore.selectedGameId } : {};
    await api.post('/announcements/sync', null, { params });
    let tries = 0;
    const poll = setInterval(async () => {
      tries++;
      await loadSyncStatus();
      if (!syncStatus.is_syncing || tries > 120) {
        clearInterval(poll);
        syncing.value = false;
        await Promise.all([loadList(), loadStats()]);
      }
    }, 2000);
  } catch (e: any) {
    syncing.value = false;
    alert(e?.response?.data?.detail || '同步失败');
  }
}

function formatDate(iso: string | null): string {
  if (!iso) return '—';
  return iso.replace('T', ' ').substring(0, 10);
}

function formatTime(iso: string | null): string {
  if (!iso) return '—';
  return iso.replace('T', ' ').substring(0, 16);
}
</script>

<style scoped>
.page {
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 100%;
}

/* ── 工具栏 ── */
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.filters { display: flex; gap: 8px; align-items: center; }

.search-input {
  width: 240px;
  padding: 7px 10px;
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  color: var(--text-primary);
  font-size: 13px;
  outline: none;
}
.search-input:focus { border-color: var(--accent); }

.btn-search {
  padding: 7px 14px;
  background: var(--accent);
  color: #fff;
  border: none;
  border-radius: var(--radius);
  font-size: 13px;
  cursor: pointer;
}
.btn-search:hover { opacity: 0.85; }

.sync-area { display: flex; align-items: center; gap: 10px; }
.last-sync { font-size: 12px; color: var(--text-muted); }

.btn-sync {
  padding: 7px 14px;
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  color: var(--text-secondary);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s;
}
.btn-sync:hover:not(:disabled) { border-color: var(--accent); color: var(--accent); }
.btn-sync:disabled { opacity: 0.5; cursor: not-allowed; }

/* ── 统计卡片 ── */
.stat-cards { display: flex; gap: 12px; flex-wrap: wrap; }
.stat-card {
  flex: 1;
  min-width: 120px;
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 14px 20px;
}
.stat-val   { font-size: 28px; font-weight: 700; color: var(--text-primary); }
.stat-label { font-size: 12px; color: var(--text-muted); margin-top: 4px; }

/* ── 列表 ── */
.list-wrap { display: flex; flex-direction: column; gap: 10px; }
.loading, .empty {
  padding: 40px;
  text-align: center;
  color: var(--text-muted);
  font-size: 14px;
}

.ann-card {
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
}

.ann-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 18px;
}

.ann-title-row { display: flex; align-items: center; gap: 8px; min-width: 0; }
.ann-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.badge-mt {
  flex-shrink: 0;
  font-size: 11px;
  padding: 1px 7px;
  border-radius: 10px;
  background: rgba(156,163,175,0.18);
  color: var(--text-muted);
}
.ann-date { flex-shrink: 0; font-size: 12px; color: var(--text-muted); }

.ann-body-wrap {
  padding: 4px 18px 18px;
  border-top: 1px solid var(--border);
}
.ann-source {
  display: inline-block;
  margin-top: 12px;
  font-size: 13px;
  color: var(--accent);
  text-decoration: none;
}
.ann-source:hover { text-decoration: underline; }

/* ── 公告正文 HTML 渲染样式 ── */
.announcement-body {
  font-size: 14px;
  line-height: 1.7;
  color: var(--text-secondary);
  word-break: break-word;
}
.announcement-body :deep(h1) { font-size: 18px; margin: 16px 0 8px; color: var(--text-primary); }
.announcement-body :deep(h2) { font-size: 16px; margin: 14px 0 7px; color: var(--text-primary); }
.announcement-body :deep(h3) { font-size: 15px; margin: 12px 0 6px; color: var(--text-primary); }
.announcement-body :deep(p)  { margin: 8px 0; }
.announcement-body :deep(strong) { color: var(--text-primary); }
.announcement-body :deep(ol),
.announcement-body :deep(ul) { margin: 8px 0; padding-left: 24px; }
.announcement-body :deep(li) { margin: 4px 0; }
.announcement-body :deep(a)  { color: var(--accent); text-decoration: none; }
.announcement-body :deep(a:hover) { text-decoration: underline; }
.announcement-body :deep(img) {
  max-width: 100%;
  height: auto;
  border-radius: var(--radius);
  margin: 8px 0;
  display: block;
}
.announcement-body :deep(table) {
  border-collapse: collapse;
  margin: 10px 0;
  width: 100%;
}
.announcement-body :deep(td),
.announcement-body :deep(th) {
  border: 1px solid var(--border);
  padding: 6px 10px;
  text-align: left;
}
.announcement-body :deep(th) { background: var(--bg-primary); color: var(--text-primary); }

/* ── 分页 ── */
.pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
  font-size: 13px;
  color: var(--text-muted);
}
.pagination button {
  padding: 6px 14px;
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 13px;
  transition: all 0.15s;
}
.pagination button:hover:not(:disabled) { border-color: var(--accent); color: var(--accent); }
.pagination button:disabled { opacity: 0.4; cursor: not-allowed; }
</style>
