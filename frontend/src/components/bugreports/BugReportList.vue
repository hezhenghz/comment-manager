<template>
  <div class="page">
    <!-- 顶部操作栏 -->
    <div class="toolbar">
      <div class="filters">
        <select v-model="filters.status" @change="onFilter">
          <option value="">全部状态</option>
          <option value="active">激活</option>
          <option value="resolved">已解决</option>
          <option value="closed">已关闭</option>
        </select>
        <select v-model="filters.priority" @change="onFilter">
          <option value="">全部优先级</option>
          <option value="1">紧急</option>
          <option value="2">重要</option>
          <option value="3">中</option>
          <option value="4">低</option>
        </select>
        <input
          v-model="filters.keyword"
          placeholder="搜索标题…"
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
        <div class="stat-label">BUG 总数</div>
      </div>
      <div class="stat-card danger">
        <div class="stat-val">{{ stats.active }}</div>
        <div class="stat-label">激活中</div>
      </div>
      <div class="stat-card success">
        <div class="stat-val">{{ stats.resolved }}</div>
        <div class="stat-label">已解决</div>
      </div>
      <div class="stat-card">
        <div class="stat-val">{{ stats.today_new }}</div>
        <div class="stat-label">今日新增</div>
      </div>
    </div>

    <!-- 表格 -->
    <div class="table-wrap">
      <div v-if="loading" class="loading">加载中…</div>
      <div v-else-if="!items.length" class="empty">暂无数据（请先触发同步）</div>
      <table v-else>
        <thead>
          <tr>
            <th style="width:64px">ID</th>
            <th>标题</th>
            <th style="width:88px">状态</th>
            <th style="width:72px">优先级</th>
            <th style="width:72px">严重度</th>
            <th style="width:90px">提交人</th>
            <th style="width:90px">指派人</th>
            <th style="width:120px">提交时间</th>
          </tr>
        </thead>
        <tbody>
          <template v-for="bug in items" :key="bug.id">
            <tr
              class="bug-row"
              :class="{ expanded: expandedId === bug.id }"
              @click="toggleExpand(bug.id)"
            >
              <td class="bug-id">#{{ bug.external_id }}</td>
              <td class="bug-title">{{ bug.title }}</td>
              <td>
                <span class="badge" :class="statusClass(bug.status)">
                  {{ bug.status_label }}
                </span>
              </td>
              <td>
                <span v-if="bug.priority" class="priority" :class="priorityClass(bug.priority)">
                  {{ bug.priority_label }}
                </span>
                <span v-else class="muted">—</span>
              </td>
              <td>
                <span v-if="bug.severity" class="severity" :class="severityClass(bug.severity)">
                  {{ bug.severity_label }}
                </span>
                <span v-else class="muted">—</span>
              </td>
              <td class="muted">{{ bug.submitter || '—' }}</td>
              <td class="muted">{{ bug.assignee || '—' }}</td>
              <td class="muted">{{ formatDate(bug.submitted_at) }}</td>
            </tr>
            <!-- 展开行 -->
            <tr v-if="expandedId === bug.id" class="expand-row">
              <td colspan="8">
                <div class="expand-content">
                  <div v-if="bug.module" class="expand-field">
                    <span class="expand-label">模块：</span>{{ bug.module }}
                  </div>
                  <div v-if="bug.resolved_at" class="expand-field">
                    <span class="expand-label">解决时间：</span>{{ formatTime(bug.resolved_at) }}
                  </div>
                  <div v-if="bug.description" class="expand-desc">
                    <div class="expand-label">重现步骤 / 描述：</div>
                    <pre class="desc-pre">{{ bug.description }}</pre>
                  </div>
                  <div v-if="bug.source_url" class="expand-link">
                    <a :href="bug.source_url" target="_blank" rel="noopener">下载 Dump 文件 ↗</a>
                  </div>
                </div>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
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
import { ref, reactive, onMounted } from 'vue';
import api from '../../api';
import { useAuthStore } from '../../stores/auth';

const authStore = useAuthStore();

// ── 数据 ────────────────────────────────────────────────────────────────────
const items     = ref<any[]>([]);
const total     = ref(0);
const page      = ref(1);
const perPage   = ref(20);
const loading   = ref(false);
const expandedId = ref<string | null>(null);
const syncing   = ref(false);

const stats = reactive({
  total: 0, active: 0, resolved: 0, closed: 0, today_new: 0,
});

const syncStatus = reactive({
  last_sync_at:    null as string | null,
  last_sync_count: 0,
  is_syncing:      false,
});

const filters = reactive({
  status:   '',
  priority: '',
  keyword:  '',
});

// ── 生命周期 ─────────────────────────────────────────────────────────────────
onMounted(async () => {
  await Promise.all([loadList(), loadStats(), loadSyncStatus()]);
});

// ── 数据加载 ─────────────────────────────────────────────────────────────────
async function loadList() {
  loading.value = true;
  try {
    const params: Record<string, any> = {
      page:     page.value,
      per_page: perPage.value,
    };
    if (filters.status)   params.status   = filters.status;
    if (filters.priority) params.priority  = Number(filters.priority);
    if (filters.keyword)  params.keyword   = filters.keyword;

    const { data } = await api.get('/bugreports', { params });
    items.value = data.items;
    total.value = data.total;
  } catch (e) {
    console.error('[bugreports] loadList error', e);
  } finally {
    loading.value = false;
  }
}

async function loadStats() {
  try {
    const { data } = await api.get('/bugreports/stats');
    Object.assign(stats, data);
  } catch {}
}

async function loadSyncStatus() {
  try {
    const { data } = await api.get('/bugreports/sync/status');
    Object.assign(syncStatus, data);
  } catch {}
}

// ── 交互 ─────────────────────────────────────────────────────────────────────
function onFilter() {
  page.value = 1;
  expandedId.value = null;
  loadList();
}

function goPage(p: number) {
  page.value = p;
  expandedId.value = null;
  loadList();
}

function toggleExpand(id: string) {
  expandedId.value = expandedId.value === id ? null : id;
}

async function doSync() {
  if (syncing.value || syncStatus.is_syncing) return;
  syncing.value = true;
  try {
    await api.post('/bugreports/sync');
    // 轮询同步状态直到完成
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

// ── 格式化 ───────────────────────────────────────────────────────────────────
function formatDate(iso: string | null): string {
  if (!iso) return '—';
  return iso.replace('T', ' ').substring(0, 10);
}

function formatTime(iso: string | null): string {
  if (!iso) return '—';
  return iso.replace('T', ' ').substring(0, 16);
}

// ── 样式辅助 ─────────────────────────────────────────────────────────────────
function statusClass(status: string) {
  return {
    'badge-active':   status === 'active',
    'badge-resolved': status === 'resolved',
    'badge-closed':   status === 'closed',
  };
}

function priorityClass(pri: number) {
  return {
    'pri-urgent': pri === 1,
    'pri-high':   pri === 2,
    'pri-mid':    pri === 3,
    'pri-low':    pri === 4,
  };
}

function severityClass(sev: number) {
  return {
    'sev-critical': sev === 1,
    'sev-high':     sev === 2,
    'sev-mid':      sev === 3,
    'sev-low':      sev === 4,
  };
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

.filters {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
}

.filters select,
.search-input {
  padding: 7px 10px;
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  color: var(--text-primary);
  font-size: 13px;
  outline: none;
}

.search-input { width: 200px; }

.filters select:focus,
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

/* ── 同步区 ── */
.sync-area {
  display: flex;
  align-items: center;
  gap: 10px;
}

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
.btn-sync:hover:not(:disabled) {
  border-color: var(--accent);
  color: var(--accent);
}
.btn-sync:disabled { opacity: 0.5; cursor: not-allowed; }

/* ── 统计卡片 ── */
.stat-cards {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.stat-card {
  flex: 1;
  min-width: 120px;
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 14px 20px;
}

.stat-card.danger .stat-val  { color: var(--negative, #ef4444); }
.stat-card.success .stat-val { color: var(--positive, #22c55e); }

.stat-val   { font-size: 28px; font-weight: 700; color: var(--text-primary); }
.stat-label { font-size: 12px; color: var(--text-muted); margin-top: 4px; }

/* ── 表格 ── */
.table-wrap {
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow-x: auto;
}

.loading, .empty {
  padding: 40px;
  text-align: center;
  color: var(--text-muted);
  font-size: 14px;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

th {
  padding: 10px 12px;
  text-align: left;
  color: var(--text-muted);
  border-bottom: 1px solid var(--border);
  font-weight: 500;
  white-space: nowrap;
}

.bug-row td {
  padding: 10px 12px;
  border-bottom: 1px solid var(--border);
  vertical-align: middle;
  cursor: pointer;
}

.bug-row:hover td { background: var(--bg-hover); }
.bug-row.expanded td { background: var(--bg-hover); }

.bug-id { color: var(--text-muted); font-size: 12px; white-space: nowrap; }
.bug-title { color: var(--text-primary); max-width: 360px; }
.muted { color: var(--text-muted); }

/* ── 状态徽章 ── */
.badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 600;
  white-space: nowrap;
}

.badge-active   { background: rgba(239,68,68,0.15); color: var(--negative, #ef4444); }
.badge-resolved { background: rgba(34,197,94,0.15); color: var(--positive, #22c55e); }
.badge-closed   { background: rgba(156,163,175,0.15); color: var(--text-muted); }

/* ── 优先级 / 严重度 ── */
.priority, .severity {
  display: inline-block;
  font-size: 12px;
  padding: 1px 6px;
  border-radius: 4px;
}

.pri-urgent { color: #ef4444; }
.pri-high   { color: #f97316; }
.pri-mid    { color: var(--text-secondary); }
.pri-low    { color: var(--text-muted); }

.sev-critical { color: #ef4444; font-weight: 600; }
.sev-high     { color: #f97316; }
.sev-mid      { color: var(--text-secondary); }
.sev-low      { color: var(--text-muted); }

/* ── 展开行 ── */
.expand-row td {
  background: var(--bg-primary);
  border-bottom: 1px solid var(--border);
  padding: 0;
}

.expand-content {
  padding: 14px 20px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.expand-field {
  font-size: 13px;
  color: var(--text-secondary);
}

.expand-label {
  color: var(--text-muted);
  font-size: 12px;
}

.expand-desc {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.desc-pre {
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 10px 14px;
  font-size: 12px;
  color: var(--text-secondary);
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 200px;
  overflow-y: auto;
}

.expand-link a {
  font-size: 13px;
  color: var(--accent);
  text-decoration: none;
}
.expand-link a:hover { text-decoration: underline; }

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

.pagination button:hover:not(:disabled) {
  border-color: var(--accent);
  color: var(--accent);
}

.pagination button:disabled { opacity: 0.4; cursor: not-allowed; }
</style>
