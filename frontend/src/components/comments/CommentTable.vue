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
              <option value="qq">QQ群</option>
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
          <!-- 分类 -->
          <th class="th-category">
            <span class="col-label">分类</span>
            <select v-if="!fixedCategory" v-model="category" @change="onFilterChange">
              <option value="">全部</option>
              <option value="bug">Bug</option>
              <option value="suggestion">建议</option>
              <option value="complaint">投诉</option>
              <option value="praise">好评</option>
              <option value="other">其他</option>
            </select>
            <span v-else class="fixed-filter-label">{{ fixedCategory === 'bug' ? 'Bug' : '建议' }}</span>
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
          <!-- 打分 -->
          <th class="th-rating">
            <span class="col-label">打分</span>
            <select v-model="recommended" @change="onFilterChange">
              <option value="">全部</option>
              <option value="true">推荐</option>
              <option value="false">不推荐</option>
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
          <td colspan="8" class="empty-row">暂无符合条件的评论</td>
        </tr>
        <template v-for="c in store.items" :key="c.id">
          <tr class="data-row" :class="{ expanded: expandedId === c.id }" @click="toggleExpand(c)">
            <td>
              <span class="platform-badge" :class="platformClass(c.platform)">
                {{ platformLabel(c.platform) }}
              </span>
            </td>
            <td class="content-cell">
              {{ c.content.slice(0, 150) }}{{ c.content.length > 150 ? '…' : '' }}
            </td>
            <td>
              <span class="sentiment" :class="c.sentiment || 'neutral'">
                {{ sentimentLabel(c.sentiment) }}
              </span>
            </td>
            <td>{{ categoryLabel(c.category) }}</td>
            <td>{{ langLabel(c.content_lang) }}</td>
            <td>
              <!-- 小黑盒：thumbs_up 存的是 1-5 星级 -->
              <span v-if="c.platform === 'xiaoheihe' && c.thumbs_up != null" class="rating"
                :class="c.thumbs_up >= 4 ? 'recommended' : c.thumbs_up <= 2 ? 'not-recommended' : 'none'">
                ⭐ {{ c.thumbs_up }}
              </span>
              <!-- Steam：thumbs_up = 1(推荐) 或 0(不推荐) -->
              <span v-else-if="c.thumbs_up === 1" class="rating recommended">👍 推荐</span>
              <span v-else-if="c.thumbs_up === 0" class="rating not-recommended">👎 不推荐</span>
              <span v-else class="rating none">—</span>
            </td>
            <td class="date-cell">{{ c.published_at ? new Date(c.published_at).toLocaleDateString('zh-CN') : '—' }}</td>
            <td><a v-if="c.source_url" :href="c.source_url" target="_blank" @click.stop>查看</a></td>
          </tr>
          <tr v-if="expandedId === c.id" class="expand-row">
            <td colspan="8">
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

const props = defineProps<{ fixedCategory?: string }>();

const store = useCommentsStore();
const gameStore = useGameStore();

const platform   = ref('');
const sentiment  = ref('');
const category   = ref(props.fixedCategory ?? '');
const lang       = ref('');
const recommended = ref('');
const searchQuery = ref('');
const expandedId  = ref<string | null>(null);

function needsTranslation(lang: string | null): boolean {
  return !!lang && lang !== 'zh-cn' && lang !== 'zh-tw';
}

function toggleExpand(c: any) {
  expandedId.value = expandedId.value === c.id ? null : c.id;
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
onMounted(() => load());

watch(() => props.fixedCategory, (val) => {
  category.value = val ?? '';
  load();
});

watch(() => gameStore.selectedGameId, () => {
  searchQuery.value = '';
  store.page = 1;
  loadWithCurrentFilters();
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
  if (platform.value)           params.platform    = platform.value;
  if (sentiment.value)          params.sentiment   = sentiment.value;
  if (category.value)           params.category    = category.value;
  if (lang.value)               params.content_lang = lang.value;
  if (recommended.value !== '') params.recommended = recommended.value;
  if (searchQuery.value.trim()) params.q           = searchQuery.value.trim();
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
</style>
