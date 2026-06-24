<template>
  <div class="page">
    <h2>{{ fixedCategory === 'bug' ? 'BUG' : fixedCategory === 'suggestion' ? '建议' : '评论' }}</h2>
    <table>
      <thead>
        <tr class="filter-row">
          <!-- 平台 -->
          <th class="th-platform">
            <span class="col-label">平台</span>
            <select v-model="platform" @change="onFilterChange">
              <option value="">全部</option>
              <option value="steam_store">Steam评价</option>
              <option value="steam_hub">Steam论坛</option>
              <option value="xiaoheihe">小黑盒</option>
              <option value="discord">Discord</option>
              <!-- QQ群仅在BUG/建议模式下可筛选 -->
              <option v-if="fixedCategory" value="qq">QQ群</option>
            </select>
          </th>
          <!-- 内容（搜索） -->
          <th class="th-content">
            <span class="col-label">内容</span>
            <div class="search-wrap">
              <input v-model="searchQuery" @input="onSearch" placeholder="搜索评论内容…" />
            </div>
          </th>
          <!-- 情感 -->
          <th class="th-sentiment">
            <span class="col-label">情感</span>
            <select v-model="sentiment" @change="onFilterChange">
              <option value="">全部</option>
              <option value="positive">正面</option>
              <option value="negative">负面</option>
              <option value="neutral">中性</option>
            </select>
          </th>
          <!-- 分类（BUG/建议页隐藏） -->
          <th v-if="!fixedCategory" class="th-category">
            <span class="col-label">分类</span>
            <select v-model="category" @change="onFilterChange">
              <option value="">全部</option>
              <option value="bug">Bug</option>
              <option value="suggestion">建议</option>
              <option value="complaint">投诉</option>
              <option value="praise">好评</option>
              <option value="other">其他</option>
            </select>
          </th>
          <!-- 语言 -->
          <th class="th-lang">
            <span class="col-label">语言</span>
            <select v-model="lang" @change="onFilterChange">
              <option value="">全部</option>
              <option value="zh-cn">简中</option>
              <option value="zh-tw">繁中</option>
              <option value="en">英语</option>
              <option value="ja">日语</option>
              <option value="ko">韩语</option>
            </select>
          </th>
          <!-- 打分（BUG/建议页隐藏） -->
          <th v-if="!fixedCategory" class="th-rating">
            <span class="col-label">打分</span>
            <select v-model="recommended" @change="onFilterChange">
              <option value="">全部</option>
              <option value="true">推荐</option>
              <option value="false">不推荐</option>
            </select>
          </th>
          <!-- 处理状态（BUG/建议页） -->
          <th v-if="fixedCategory" class="th-bug-status">
            <span class="col-label">处理状态</span>
            <select v-model="bugStatusFilter" @change="onFilterChange">
              <option value="">全部</option>
              <option value="unprocessed">未处理</option>
              <option value="accepted">已接受</option>
              <option value="completed">已完成</option>
            </select>
          </th>
          <!-- 发布时间（不可筛选） -->
          <th class="th-date">发布时间</th>
          <!-- 链接（不可筛选） -->
          <th class="th-link">链接</th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="!store.items.length">
          <td :colspan="fixedCategory ? 7 : 8" class="empty-row">暂无符合条件的评论</td>
        </tr>
        <template v-for="c in store.items" :key="c.id">
          <tr
            class="data-row"
            :class="[{ expanded: expandedId === c.id }, bugStatusRowClass(c)]"
            @click="toggleExpand(c)"
          >
            <td>
              <span class="platform-badge" :class="platformClass(c.platform)">
                {{ platformLabel(c.platform) }}
              </span>
            </td>
            <td class="content-cell">
              {{ c.content.slice(0, 150) }}{{ c.content.length > 150 ? '…' : '' }}
            </td>
            <td @click.stop="c.ai_status === 'failed' ? retryAi(c) : null">
              <span v-if="c.ai_status === 'pending'" class="ai-badge ai-pending" title="等待 AI 分析中">⏳ 待分析</span>
              <span v-else-if="c.ai_status === 'failed'" class="ai-badge ai-failed" :title="c.last_ai_error || '点此重置为待分析状态'">⚠ AI 分析失败，点此重试</span>
              <span v-else-if="c.ai_status === 'skipped'" class="ai-badge ai-skipped" title="AI 判定为非游戏反馈（水群/广告/图片等）">— 已跳过</span>
              <span v-else class="sentiment" :class="c.sentiment || 'neutral'">
                {{ sentimentLabel(c.sentiment) }}
              </span>
            </td>
            <!-- 分类（BUG/建议页隐藏） -->
            <td v-if="!fixedCategory">{{ categoryLabel(c.category) }}</td>
            <td>{{ langLabel(c.content_lang) }}</td>
            <!-- 打分（BUG/建议页隐藏） -->
            <td v-if="!fixedCategory">
              <span v-if="c.platform === 'xiaoheihe' && c.thumbs_up != null" class="rating"
                :class="c.thumbs_up >= 4 ? 'recommended' : c.thumbs_up <= 3 ? 'not-recommended' : 'none'">
                ⭐ {{ c.thumbs_up }}
              </span>
              <span v-else-if="c.thumbs_up === 1" class="rating recommended">👍 推荐</span>
              <span v-else-if="c.thumbs_up === 0" class="rating not-recommended">👎 不推荐</span>
              <span v-else class="rating none">—</span>
            </td>
            <!-- 处理状态（BUG/建议页） -->
            <td v-if="fixedCategory" @click.stop>
              <select
                class="bug-status-select"
                :class="bugStatusClass(c.bug_status)"
                :value="c.bug_status || 'unprocessed'"
                @change="onBugStatusChange(c, ($event.target as HTMLSelectElement).value)"
              >
                <option value="unprocessed">未处理</option>
                <option value="accepted">已接受</option>
                <option value="completed">已完成</option>
              </select>
            </td>
            <td class="date-cell">{{ c.published_at ? new Date(c.published_at).toLocaleDateString('zh-CN') : '—' }}</td>
            <td><a v-if="c.source_url" :href="c.source_url" target="_blank" @click.stop>查看</a></td>
          </tr>
          <tr v-if="expandedId === c.id" class="expand-row">
            <td :colspan="fixedCategory ? 7 : 8">
              <div class="expand-body">
                <div class="expand-section">
                  <div class="expand-label">完整内容</div>
                  <div class="expand-content">{{ c.content }}</div>
                </div>
                <div v-if="needsTranslation(c.content_lang)" class="expand-section">
                  <div class="expand-label">翻译</div>
                  <div class="expand-content">
                    <span v-if="c.translation">{{ c.translation }}</span>
                    <span v-else class="translate-loading">—</span>
                  </div>
                </div>
                <div v-if="c.summary" class="expand-section">
                  <div class="expand-label">AI 摘要</div>
                  <div class="expand-content">{{ c.summary }}</div>
                </div>
                <div v-if="c.sentiment_score != null" class="expand-section">
                  <div class="expand-label">情感评分</div>
                  <div class="expand-content">{{ c.sentiment_score.toFixed(2) }}</div>
                </div>

                <!-- QQ/Discord 群聊上下文（仅 BUG/建议模式） -->

                <template v-if="(c.platform === 'qq' || c.platform === 'discord') && fixedCategory">
                  <div class="expand-section">
                    <div class="expand-label">来源</div>
                    <div class="expand-content qq-meta">
                      <template v-if="chatContext[c.id]">
                        <span class="qq-meta-item">
                          {{ c.platform === 'discord' ? '频道' : '群' }}：{{
                            c.platform === 'qq'
                              ? (groupNames[chatContext[c.id].group_id] || chatContext[c.id].group_id) + '（' + chatContext[c.id].group_id + '）'
                              : chatContext[c.id].group_id
                          }}
                        </span>
                        <span v-if="chatContext[c.id].sender_id" class="qq-meta-item">
                          发送者：{{ chatContext[c.id].sender_name }}
                          （QQ {{ chatContext[c.id].sender_id }}）
                        </span>
                        <span v-else class="qq-meta-item">
                          发送者：{{ chatContext[c.id].sender_name }}
                        </span>
                      </template>
                      <span v-else-if="loadingChatCtx.has(c.id)" class="translate-loading">加载中…</span>
                    </div>
                  </div>
                  <div class="expand-section">
                    <div class="expand-label">{{ c.platform === 'discord' ? '频道上下文' : '群上下文' }}</div>
                    <div class="expand-content">
                      <div v-if="loadingChatCtx.has(c.id)" class="translate-loading">加载中…</div>
                      <template v-else-if="chatContext[c.id]">
                        <div
                          v-if="!chatContext[c.id].prev_messages.length && !chatContext[c.id].next_messages.length"
                          class="translate-loading"
                        >无上下文消息</div>
                        <!-- 前10条 -->
                        <div
                          v-for="(m, i) in chatContext[c.id].prev_messages"
                          :key="'p' + i"
                          class="qq-ctx-msg"
                        >
                          <span class="qq-ctx-time">{{ formatMsgTime(m.published_at) }}</span>
                          <span class="qq-ctx-name">{{ m.author_name || '匿名' }}</span>
                          <span class="qq-ctx-text">{{ m.content }}</span>
                        </div>
                        <!-- 本条：高亮 -->
                        <div
                          v-if="chatContext[c.id].current_message"
                          class="qq-ctx-msg qq-ctx-current"
                        >
                          <span class="qq-ctx-time">{{ formatMsgTime(chatContext[c.id].current_message.published_at) }}</span>
                          <span class="qq-ctx-name qq-ctx-name--highlight">{{ chatContext[c.id].current_message.author_name || '匿名' }}</span>
                          <span class="qq-ctx-text qq-ctx-text--highlight">{{ chatContext[c.id].current_message.content }}</span>
                        </div>
                        <!-- 后10条 -->
                        <div
                          v-for="(m, i) in chatContext[c.id].next_messages"
                          :key="'n' + i"
                          class="qq-ctx-msg"
                        >
                          <span class="qq-ctx-time">{{ formatMsgTime(m.published_at) }}</span>
                          <span class="qq-ctx-name">{{ m.author_name || '匿名' }}</span>
                          <span class="qq-ctx-text">{{ m.content }}</span>
                        </div>
                      </template>
                    </div>
                  </div>
                </template>

                <!-- 需策划处理：采纳 / 不采纳 -->
                <div class="expand-actions">
                  <template v-if="decisions[c.id] === 'adopted'">
                    <span class="decision-badge adopted">✅ 已采纳（进需求板）</span>
                    <button class="btn-redo" :disabled="decidingId === c.id" @click.stop="decide(c, 'rejected')">改为不采纳</button>
                  </template>
                  <template v-else-if="decisions[c.id] === 'rejected'">
                    <span class="decision-badge rejected">⛔ 已不采纳</span>
                    <button class="btn-redo" :disabled="decidingId === c.id" @click.stop="decide(c, 'adopted')">改为采纳</button>
                  </template>
                  <template v-else>
                    <span class="decision-prompt">需策划处理：</span>
                    <button class="btn-adopt" :disabled="decidingId === c.id" @click.stop="decide(c, 'adopted')">
                      {{ decidingId === c.id ? '处理中…' : '采纳' }}
                    </button>
                    <button class="btn-reject" :disabled="decidingId === c.id" @click.stop="decide(c, 'rejected')">不采纳</button>
                  </template>
                </div>
              </div>
            </td>
          </tr>
        </template>
      </tbody>
    </table>

    <div class="pagination" v-if="store.total > store.pageSize">
      <button :disabled="store.page <= 1" @click="prevPage">上一页</button>
      <span>{{ store.page }} / {{ Math.ceil(store.total / store.pageSize) }}</span>
      <button :disabled="store.page >= Math.ceil(store.total / store.pageSize)" @click="nextPage">下一页</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue';
import { useCommentsStore } from '../../stores/comments';
import { useGameStore } from '../../stores/game';
import api from '../../api';

const props = defineProps<{ fixedCategory?: string }>();

const store = useCommentsStore();
const gameStore = useGameStore();

const platform      = ref('');
const sentiment     = ref('');
const category      = ref(props.fixedCategory ?? '');
const lang          = ref('');
const recommended   = ref('');
const bugStatusFilter = ref('');
const searchQuery   = ref('');
const expandedId    = ref<string | null>(null);

// 群聊上下文（QQ / Discord）
const groupNames    = ref<Record<string, string>>({});
const chatContext   = ref<Record<string, any>>({});
const loadingChatCtx = ref<Set<string>>(new Set());

// 需策划处理：source_id → 'adopted' | 'rejected'
const decisions  = ref<Record<string, string>>({});
const decidingId = ref<string | null>(null);

async function loadGroupNames() {
  if (!gameStore.selectedGameId) return;
  try {
    const { data } = await api.get(`/crawlers/qq/group-names?game_id=${gameStore.selectedGameId}`);
    groupNames.value = data;
  } catch {}
}

async function loadDecisions() {
  if (!gameStore.selectedGameId) return;
  try {
    const { data } = await api.get(`/curation/decisions?game_id=${gameStore.selectedGameId}`);
    decisions.value = data as Record<string, string>;
  } catch {}
}

async function decide(c: any, decision: 'adopted' | 'rejected') {
  if (decidingId.value) return;
  decidingId.value = c.id;
  try {
    const sourceType = props.fixedCategory === 'bug' ? 'bug'
      : props.fixedCategory === 'suggestion' ? 'suggestion'
      : 'comment';
    await api.post('/curation/decide', {
      game_id: gameStore.selectedGameId,
      source_type: sourceType,
      source_id: c.id,
      decision,
      source_snapshot: {
        content:      c.content,
        author_name:  c.author_name,
        platform:     c.platform,
        category:     c.category,
        sentiment:    c.sentiment,
        summary:      c.summary,
        published_at: c.published_at,
        source_url:   c.source_url,
      },
    });
    decisions.value = { ...decisions.value, [c.id]: decision };
  } catch (e) {
    console.error('[curation] decide error', e);
  } finally {
    decidingId.value = null;
  }
}

function formatMsgTime(t: string | null): string {
  if (!t) return '';
  const iso = t.endsWith('Z') || t.includes('+') ? t : t + 'Z';
  return new Date(iso).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
}

function needsTranslation(lang: string | null): boolean {
  return !!lang && lang !== 'zh-cn' && lang !== 'zh-tw';
}

async function toggleExpand(c: any) {
  expandedId.value = expandedId.value === c.id ? null : c.id;
  // BUG/建议模式下，展开 QQ/Discord 消息时懒加载频道上下文
  if (
    expandedId.value === c.id &&
    props.fixedCategory &&
    (c.platform === 'qq' || c.platform === 'discord') &&
    !chatContext.value[c.id] &&
    !loadingChatCtx.value.has(c.id)
  ) {
    const s = new Set(loadingChatCtx.value); s.add(c.id); loadingChatCtx.value = s;
    try {
      const { data } = await api.get(`/comments/${c.id}/chat-context`);
      chatContext.value = { ...chatContext.value, [c.id]: data };
    } catch {}
    finally {
      const s2 = new Set(loadingChatCtx.value); s2.delete(c.id); loadingChatCtx.value = s2;
    }
  }
}

// ─── BUG 处理状态 ────────────────────────────────────────────────────────────
function bugStatusClass(status: string | null): string {
  if (status === 'accepted')  return 'status-accepted';
  if (status === 'completed') return 'status-completed';
  return 'status-unprocessed';
}

function bugStatusRowClass(c: any): string {
  if (!props.fixedCategory) return '';
  if (c.bug_status === 'accepted')  return 'row-accepted';
  if (c.bug_status === 'completed') return 'row-completed';
  return '';
}

// ─── AI 重试 ─────────────────────────────────────────────────────────────────
async function retryAi(c: any) {
  if (c.ai_status !== 'failed') return;
  try {
    await api.post(`/comments/${c.id}/ai-retry`);
    c.ai_status = 'pending';
  } catch {}
}

async function onBugStatusChange(c: any, newStatus: string) {
  const prev = c.bug_status;
  // 乐观更新
  c.bug_status = newStatus === 'unprocessed' ? null : newStatus;
  try {
    await api.patch(`/comments/${c.id}/bug-status?status=${newStatus}`);
  } catch {
    // 回滚
    c.bug_status = prev;
  }
}

// ─── Labels ───────────────────────────────────────────────────────────────────
const PLATFORM_MAP: Record<string, string> = {
  steam_store: 'Steam评价',
  steam_hub:   'Steam论坛',
  discord:     'Discord',
  qq:          'QQ群',
  xiaoheihe:   '小黑盒',
};
const PLATFORM_CLASS: Record<string, string> = {
  steam_store: 'platform-steam-store',
  steam_hub:   'platform-steam-hub',
  discord:     'platform-discord',
  qq:          'platform-qq',
  xiaoheihe:   'platform-xiaoheihe',
};
const SENTIMENT_MAP: Record<string, string> = {
  positive: '正面', negative: '负面', neutral: '中性',
};
const CATEGORY_MAP: Record<string, string> = {
  bug: 'Bug', suggestion: '建议', complaint: '投诉', praise: '好评', other: '其他',
};
const LANG_MAP: Record<string, string> = {
  'zh-cn': '简中', 'zh-tw': '繁中', en: '英语', ja: '日语', ko: '韩语',
  unknown: '—',
};

function platformLabel(p: string) { return PLATFORM_MAP[p] ?? p; }
function platformClass(p: string) { return PLATFORM_CLASS[p] ?? 'platform-other'; }
function sentimentLabel(s: string | null) { return SENTIMENT_MAP[s ?? ''] ?? (s || '—'); }
function categoryLabel(c: string | null) { return CATEGORY_MAP[c ?? ''] ?? (c || '—'); }
function langLabel(l: string | null) { return LANG_MAP[l ?? ''] ?? (l || '—'); }

// ─── Load ─────────────────────────────────────────────────────────────────────
onMounted(() => { load(); loadGroupNames(); loadDecisions(); });

watch(() => props.fixedCategory, (val) => {
  category.value = val ?? '';
  load();
});

watch(() => gameStore.selectedGameId, () => {
  searchQuery.value = '';
  store.page = 1;
  chatContext.value = {};
  loadWithCurrentFilters();
  loadGroupNames();
  loadDecisions();
});

let searchTimer: ReturnType<typeof setTimeout>;
function onSearch() {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    store.page = 1;
    loadWithCurrentFilters();
  }, 300);
}

function onFilterChange() {
  store.page = 1;
  loadWithCurrentFilters();
}

function load() {
  searchQuery.value = '';
  store.page = 1;
  loadWithCurrentFilters();
}

function loadWithCurrentFilters() {
  const params: any = {};
  if (gameStore.selectedGameId) params.game_id     = gameStore.selectedGameId;
  // 评论模块（无 fixedCategory）隐藏所有 QQ/Discord 群聊消息
  if (!props.fixedCategory)     params.exclude_platform = 'qq,discord';
  // BUG/建议模式：QQ/Discord 消息按频道内位置去重（上下文重叠的只保留最早一条）
  if (props.fixedCategory)      params.dedupe_chat = true;
  if (platform.value)           params.platform    = platform.value;
  if (sentiment.value)          params.sentiment   = sentiment.value;
  if (category.value)           params.category    = category.value;
  if (lang.value)               params.content_lang = lang.value;
  if (recommended.value !== '')  params.recommended  = recommended.value;
  if (bugStatusFilter.value)     params.bug_status   = bugStatusFilter.value;
  if (searchQuery.value.trim())  params.q            = searchQuery.value.trim();
  store.loadComments(params);
}

function prevPage() { store.page--; loadWithCurrentFilters(); }
function nextPage() { store.page++; loadWithCurrentFilters(); }
</script>

<style scoped>
.page { max-width: 1500px; }
h2   { font-size: 22px; margin-bottom: 16px; }

/* ── Table ── */
table {
  width: 100%;
  border-collapse: collapse;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
}

/* ── Filter header row ── */
thead tr.filter-row th {
  background: var(--bg-hover);
  border-bottom: 2px solid var(--border);
  padding: 8px 10px 6px;
  vertical-align: top;
  white-space: nowrap;
}

.col-label {
  display: block;
  font-size: 11px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 4px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

thead select,
thead input {
  width: 100%;
  padding: 4px 6px;
  background: var(--bg-primary);
  border: 1px solid var(--border);
  border-radius: 4px;
  color: var(--text-primary);
  font-size: 12px;
  outline: none;
  box-sizing: border-box;
}

thead select:focus,
thead input:focus { border-color: var(--accent); }

.search-wrap { min-width: 200px; }
.th-content  { width: 35%; }
.th-platform { width: 110px; }
.th-sentiment{ width: 90px; }
.th-category { width: 90px; }
.th-lang     { width: 80px; }
.th-rating   { width: 100px; }
.th-date     { width: 100px; font-size: 11px; font-weight: 600; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.5px; vertical-align: middle; }
.th-link     { width: 50px;  font-size: 11px; font-weight: 600; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.5px; vertical-align: middle; }

/* ── Data rows ── */
td {
  padding: 9px 10px;
  font-size: 13px;
  color: var(--text-primary);
  border-bottom: 1px solid var(--border);
}

.data-row { cursor: pointer; transition: background 0.1s; }
.data-row:hover { background: var(--bg-hover); }
.data-row.expanded { background: var(--bg-hover); }

.expand-row td { padding: 0; border-bottom: 1px solid var(--border); }

.expand-body {
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  background: var(--bg-secondary);
}

.expand-section { display: flex; gap: 12px; }

.expand-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  min-width: 64px;
  padding-top: 1px;
}

.expand-content {
  font-size: 13px;
  color: var(--text-primary);
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}

/* ── Platform badges ── */
.platform-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  white-space: nowrap;
  font-weight: 500;
}
.platform-steam-store { background: rgba(30, 111, 214, 0.18); color: #4a9eff; }
.platform-steam-hub   { background: rgba(59, 165, 93, 0.18);  color: #4caf74; }
.platform-discord     { background: rgba(114, 137, 218, 0.2); color: #7289da; }
.platform-qq          { background: rgba(18, 183, 245, 0.18); color: #12b7f5; }
.platform-xiaoheihe   { background: rgba(255, 120, 30, 0.18); color: #ff781e; }
.platform-other       { background: rgba(107, 114, 128, 0.18); color: var(--text-secondary); }

/* ── Sentiment ── */
.sentiment { font-size: 12px; font-weight: 600; }
.sentiment.positive { color: var(--positive); }
.sentiment.negative { color: var(--negative); }
.sentiment.neutral  { color: var(--neutral); }

/* ── AI 状态角标 ── */
.ai-badge {
  display: inline-block;
  font-size: 11px;
  font-weight: 500;
  padding: 2px 6px;
  border-radius: 4px;
  white-space: nowrap;
}
.ai-pending { background: rgba(107, 114, 128, 0.18); color: var(--text-secondary); }
.ai-failed  { background: rgba(239, 68, 68, 0.15); color: #f87171; cursor: pointer; }
.ai-failed:hover { background: rgba(239, 68, 68, 0.25); }
.ai-skipped { background: rgba(107, 114, 128, 0.10); color: var(--text-muted); }

/* ── Rating ── */
.rating { font-size: 12px; white-space: nowrap; }
.rating.recommended     { color: var(--positive); }
.rating.not-recommended { color: var(--negative); }
.rating.none            { color: var(--text-muted); }

/* ── Content cell ── */
.content-cell {
  max-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ── Date ── */
.date-cell { color: var(--text-secondary); white-space: nowrap; }

a { font-size: 12px; color: var(--accent); }

.fixed-filter-label { font-size: 12px; color: var(--text-secondary); }

.translate-loading { color: var(--text-muted); font-style: italic; }
.translate-error   { color: var(--negative); }

/* ── BUG 处理状态 ── */
.th-bug-status { width: 100px; }

.bug-status-select {
  border: none;
  background: transparent;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  outline: none;
  padding: 2px 4px;
  border-radius: 4px;
  width: 100%;
}
.bug-status-select:hover { background: var(--bg-hover); }

.status-unprocessed { color: var(--text-muted); }
.status-accepted    { color: #e9a800; }
.status-completed   { color: #22c55e; }

/* 行背景色 */
.data-row.row-accepted  { background: rgba(234, 179, 8, 0.06); }
.data-row.row-completed { background: rgba(34, 197, 94, 0.07); }
.data-row.row-accepted:hover,
.data-row.row-accepted.expanded  { background: rgba(234, 179, 8, 0.12); }
.data-row.row-completed:hover,
.data-row.row-completed.expanded { background: rgba(34, 197, 94, 0.13); }

/* ── QQ 上下文 ── */
.qq-meta { display: flex; flex-direction: column; gap: 4px; }
.qq-meta-item { font-size: 13px; color: var(--text-secondary); }
.qq-ctx-msg {
  display: flex;
  gap: 10px;
  font-size: 12px;
  padding: 3px 0;
  border-bottom: 1px solid var(--border);
}
.qq-ctx-msg:last-child { border-bottom: none; }
.qq-ctx-time { color: var(--text-muted); white-space: nowrap; flex-shrink: 0; }
.qq-ctx-name { color: var(--accent); white-space: nowrap; flex-shrink: 0; font-weight: 500; }
.qq-ctx-text { color: var(--text-secondary); line-height: 1.5; }
.qq-ctx-current {
  background: rgba(234, 179, 8, 0.08);
  border-radius: 4px;
  margin: 1px -6px;
  padding: 3px 6px;
  border-bottom: none !important;
}
.qq-ctx-current + .qq-ctx-msg { border-top: 1px solid var(--border); }
.qq-ctx-name--highlight { color: #e9a800 !important; }
.qq-ctx-text--highlight  { color: #e9c46a !important; font-weight: 500; }

/* ── Empty row inside table ── */
.empty-row {
  text-align: center;
  padding: 48px 0;
  color: var(--text-muted);
  font-size: 14px;
}

/* ── Pagination ── */
.pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
  margin-top: 16px;
  color: var(--text-secondary);
  font-size: 13px;
}
.pagination button {
  padding: 6px 16px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  color: var(--text-primary);
  cursor: pointer;
}
.pagination button:disabled { opacity: 0.4; cursor: not-allowed; }

/* ── 采集到需求板 ── */
.expand-actions {
  display: flex;
  align-items: center;
  padding-top: 4px;
  border-top: 1px solid var(--border);
  margin-top: 2px;
}

/* ── 需策划处理 ── */
.decision-prompt { font-size: 12px; color: var(--text-muted); margin-right: 4px; }
.btn-adopt, .btn-reject, .btn-redo {
  padding: 5px 14px;
  border-radius: var(--radius);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s;
}
.btn-adopt {
  background: var(--accent); color: #fff; border: none; margin-right: 6px;
}
.btn-adopt:hover:not(:disabled) { opacity: 0.85; }
.btn-reject {
  background: var(--bg-card); border: 1px solid var(--border); color: var(--text-secondary);
}
.btn-reject:hover:not(:disabled) { border-color: var(--danger); color: var(--danger); }
.btn-adopt:disabled, .btn-reject:disabled, .btn-redo:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-redo {
  background: transparent; border: 1px solid var(--border); color: var(--text-muted);
  margin-left: 10px; padding: 3px 10px;
}
.btn-redo:hover:not(:disabled) { border-color: var(--accent); color: var(--accent); }

.decision-badge { font-size: 12px; font-weight: 500; }
.decision-badge.adopted  { color: var(--success, #22c55e); }
.decision-badge.rejected { color: var(--text-muted); }
</style>
