<template>
  <div class="page">
    <div class="page-header">
      <h2>话题<span class="page-desc">QQ 群玩家讨论话题聚合，由 AI 自动提取</span></h2>
      <div class="header-actions">
        <span v-if="reclusterMsg" class="recluster-msg">{{ reclusterMsg }}</span>
        <button class="btn-recluster" :disabled="reclustering" @click="recluster">
          {{ reclustering ? '聚合中…' : '重新聚合话题' }}
        </button>
      </div>
    </div>

    <div v-if="loading" class="empty">加载中…</div>
    <div v-else-if="!topics.length" class="empty">
      暂无话题，触发一次 QQ 群爬取后自动生成
    </div>

    <div v-else class="topic-list">
      <div
        v-for="t in topics"
        :key="t.id"
        class="topic-card"
        @click="toggle(t.id)"
      >
        <!-- 话题头部 -->
        <div class="topic-header">
          <span class="topic-title">{{ t.title }}</span>
          <div class="topic-meta">
            <span v-if="t.group_id" class="badge badge-group">{{ groupLabel(t.group_id) }}</span>
            <span v-if="t.category" class="badge" :class="`cat-${t.category}`">{{ CATEGORY_LABEL[t.category] ?? t.category }}</span>
            <span v-if="t.sentiment" class="badge" :class="`sent-${t.sentiment}`">{{ SENTIMENT_LABEL[t.sentiment] ?? t.sentiment }}</span>
            <span class="meta-text">{{ formatTimeRange(t.started_at, t.ended_at) }}</span>
            <span class="meta-text">{{ t.comment_count }} 条消息</span>
            <span class="expand-icon">{{ expanded.has(t.id) ? '▲' : '▼' }}</span>
          </div>
        </div>

        <!-- 摘要 -->
        <div class="topic-summary">{{ t.summary }}</div>

        <!-- 展开：原始消息 -->
        <div v-if="expanded.has(t.id)" class="topic-messages" @click.stop>
          <div v-if="loadingComments.has(t.id)" class="msg-loading">加载消息中…</div>
          <div v-else-if="!topicComments[t.id]?.length" class="msg-loading">无关联消息</div>
          <div
            v-else
            v-for="c in topicComments[t.id]"
            :key="c.id"
            class="msg-row"
          >
            <span class="msg-author">{{ c.author_name || '匿名' }}</span>
            <span class="msg-time">{{ formatMsgTime(c.published_at) }}</span>
            <span class="msg-content">{{ c.content }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 分页 -->
    <div v-if="total > pageSize" class="pagination">
      <button :disabled="page <= 1" @click="page--; load()">上一页</button>
      <span>{{ page }} / {{ Math.ceil(total / pageSize) }}</span>
      <button :disabled="page >= Math.ceil(total / pageSize)" @click="page++; load()">下一页</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue';
import { useGameStore } from '../../stores/game';
import api from '../../api';

const CATEGORY_LABEL: Record<string, string> = {
  bug: 'Bug', suggestion: '建议', complaint: '投诉', praise: '好评', other: '其他',
};
const SENTIMENT_LABEL: Record<string, string> = {
  positive: '正面', negative: '负面', neutral: '中性',
};

interface TopicItem {
  id: string;
  title: string;
  summary: string;
  category: string | null;
  sentiment: string | null;
  group_id: string | null;
  comment_count: number;
  started_at: string | null;
  ended_at: string | null;
  created_at: string;
}

interface CommentItem {
  id: string;
  author_name: string | null;
  content: string;
  published_at: string | null;
}

const gameStore = useGameStore();
const topics = ref<TopicItem[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = 20;
const loading = ref(false);
const expanded = ref<Set<string>>(new Set());
const topicComments = ref<Record<string, CommentItem[]>>({});
const loadingComments = ref<Set<string>>(new Set());
const reclustering = ref(false);
const reclusterMsg = ref('');
const groupNames = ref<Record<string, string>>({});  // group_id → 真实群名

async function loadGroupNames() {
  const gameId = gameStore.selectedGameId;
  if (!gameId) return;
  try {
    const { data } = await api.get(`/crawlers/qq/group-names?game_id=${gameId}`);
    groupNames.value = data;
  } catch {}
}

async function load() {
  const gameId = gameStore.selectedGameId;
  if (!gameId) { topics.value = []; return; }
  loading.value = true;
  try {
    const { data } = await api.get('/topics', { params: { game_id: gameId, page: page.value, page_size: pageSize } });
    topics.value = data.items;
    total.value = data.total;
  } catch {
    topics.value = [];
  } finally {
    loading.value = false;
  }
}

async function toggle(topicId: string) {
  const next = new Set(expanded.value);
  if (next.has(topicId)) {
    next.delete(topicId);
    expanded.value = next;
    return;
  }
  next.add(topicId);
  expanded.value = next;

  if (topicComments.value[topicId]) return; // 已加载

  const loading2 = new Set(loadingComments.value);
  loading2.add(topicId);
  loadingComments.value = loading2;
  try {
    const { data } = await api.get(`/topics/${topicId}/comments`);
    topicComments.value = { ...topicComments.value, [topicId]: data };
  } catch {
    topicComments.value = { ...topicComments.value, [topicId]: [] };
  } finally {
    const l = new Set(loadingComments.value);
    l.delete(topicId);
    loadingComments.value = l;
  }
}

function formatTimeRange(start: string | null, end: string | null): string {
  if (!start) return '';
  const fmt = (t: string) => {
    const iso = t.endsWith('Z') || t.includes('+') ? t : t + 'Z';
    return new Date(iso).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
  };
  if (!end || start === end) return fmt(start);
  return `${fmt(start)} — ${fmt(end)}`;
}

function formatMsgTime(t: string | null): string {
  if (!t) return '';
  const iso = t.endsWith('Z') || t.includes('+') ? t : t + 'Z';
  return new Date(iso).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
}

function groupLabel(groupId: string): string {
  // 优先用 NapCat 返回的真实群名，没有则降级为群 ID
  const realName = groupNames.value[groupId];
  return realName ? realName : groupId;
}

async function recluster() {
  const gameId = gameStore.selectedGameId;
  if (!gameId) return;
  reclustering.value = true;
  reclusterMsg.value = '';
  try {
    await api.post(`/topics/recluster?game_id=${gameId}`);
    reclusterMsg.value = '聚合已触发，AI 处理中，约 30 秒后刷新页面';
    // 30 秒后自动刷新列表
    setTimeout(() => { load(); reclusterMsg.value = ''; }, 30000);
  } catch {
    reclusterMsg.value = '触发失败，请重试';
  } finally {
    reclustering.value = false;
  }
}

onMounted(() => { load(); loadGroupNames(); });
watch(() => gameStore.selectedGameId, () => {
  page.value = 1; expanded.value = new Set(); topicComments.value = {};
  load(); loadGroupNames();
});
</script>

<style scoped>
.page { max-width: 900px; }

.page-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
}
h2 {
  font-size: 22px;
  margin: 0;
  display: flex;
  align-items: baseline;
  gap: 10px;
  flex: 1;
}
.page-desc {
  font-size: 13px;
  color: var(--text-muted);
  font-weight: 400;
}
.header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}

/* 已合并进 page-header，保留 toolbar 供兼容 */
.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.btn-recluster {
  padding: 6px 16px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  color: var(--text-primary);
  font-size: 13px;
  cursor: pointer;
}
.btn-recluster:hover:not(:disabled) { border-color: var(--accent); color: var(--accent); }
.btn-recluster:disabled { opacity: 0.5; cursor: not-allowed; }

.recluster-msg { font-size: 12px; color: var(--text-muted); }

.empty {
  text-align: center;
  padding: 48px;
  color: var(--text-muted);
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
}

.topic-list { display: flex; flex-direction: column; gap: 10px; }

.topic-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 14px 16px;
  cursor: pointer;
  transition: border-color 0.15s;
}
.topic-card:hover { border-color: var(--accent); }

.topic-header {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}
.topic-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  flex: 1;
  min-width: 0;
}
.topic-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}
.meta-text { font-size: 12px; color: var(--text-muted); white-space: nowrap; }
.expand-icon { font-size: 10px; color: var(--text-muted); }

.topic-summary {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
}

/* 分类/情感徽章 */
.badge {
  font-size: 11px;
  padding: 2px 7px;
  border-radius: 4px;
  white-space: nowrap;
}
.badge-group    { background: var(--bg-hover); color: var(--text-secondary); font-size: 11px; }
.cat-bug        { background: rgba(239,68,68,0.12);  color: var(--danger); }
.cat-suggestion { background: rgba(99,102,241,0.12); color: var(--accent); }
.cat-complaint  { background: rgba(245,158,11,0.12); color: var(--warning); }
.cat-praise     { background: rgba(34,197,94,0.12);  color: var(--success); }
.cat-other      { background: var(--bg-hover);        color: var(--text-muted); }
.sent-positive  { background: rgba(34,197,94,0.12);  color: var(--success); }
.sent-negative  { background: rgba(239,68,68,0.12);  color: var(--danger); }
.sent-neutral   { background: var(--bg-hover);        color: var(--text-muted); }

/* 展开的消息列表 */
.topic-messages {
  margin-top: 12px;
  border-top: 1px solid var(--border);
  padding-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.msg-loading { font-size: 12px; color: var(--text-muted); padding: 4px 0; }
.msg-row {
  display: flex;
  align-items: baseline;
  gap: 8px;
  font-size: 13px;
}
.msg-author {
  font-weight: 500;
  color: var(--accent);
  white-space: nowrap;
  flex-shrink: 0;
}
.msg-time {
  font-size: 11px;
  color: var(--text-muted);
  white-space: nowrap;
  flex-shrink: 0;
}
.msg-content {
  color: var(--text-secondary);
  line-height: 1.5;
}

/* 分页 */
.pagination {
  display: flex;
  align-items: center;
  gap: 12px;
  justify-content: center;
  margin-top: 20px;
  font-size: 13px;
  color: var(--text-secondary);
}
.pagination button {
  padding: 5px 14px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  color: var(--text-primary);
  cursor: pointer;
  font-size: 13px;
}
.pagination button:disabled { opacity: 0.4; cursor: not-allowed; }
.pagination button:hover:not(:disabled) { border-color: var(--accent); }
</style>
