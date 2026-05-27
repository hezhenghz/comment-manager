<template>
  <div class="page">
    <div class="page-header">
      <h2>需求板<span class="page-desc">从评论、BUG、建议、话题采集的开发需求</span></h2>
    </div>

    <!-- 筛选栏 -->
    <div class="filter-bar">
      <button
        v-for="f in FILTERS"
        :key="f.value"
        class="filter-btn"
        :class="{ active: filterType === f.value }"
        @click="filterType = f.value"
      >{{ f.label }}</button>
    </div>

    <div v-if="loading" class="empty-board">加载中…</div>
    <div v-else-if="!cards.length" class="empty-board">
      暂无需求，前往评论/BUG/建议/话题页面点击"📌 采集到需求板"
    </div>

    <!-- 三栏看板 -->
    <div v-else class="board">
      <div
        v-for="col in COLUMNS"
        :key="col.status"
        class="board-col"
        :class="`col-${col.status}`"
      >
        <div class="col-header">
          <span class="col-title">{{ col.label }}</span>
          <span class="col-count">{{ grouped[col.status].length }}</span>
        </div>
        <div class="col-body">
          <div
            v-for="card in grouped[col.status]"
            :key="card.id"
            class="req-card"
            :class="`type-${card.source_type}`"
          >
            <!-- 卡头：来源徽章 + 删除 -->
            <div class="card-head">
              <div class="card-badges">
                <span class="badge" :class="`src-${card.source_type}`">
                  {{ SOURCE_LABEL[card.source_type] ?? card.source_type }}
                </span>
                <span v-if="card.source_snapshot?.platform" class="badge badge-platform">
                  {{ PLATFORM_LABEL[card.source_snapshot.platform] ?? card.source_snapshot.platform }}
                </span>
                <span v-if="card.source_snapshot?.category" class="badge" :class="`cat-${card.source_snapshot.category}`">
                  {{ CATEGORY_LABEL[card.source_snapshot.category] ?? card.source_snapshot.category }}
                </span>
              </div>
              <button class="btn-delete" title="删除" @click="deleteCard(card.id)">🗑</button>
            </div>

            <!-- 玩家原始内容（可折叠） -->
            <div class="card-section">
              <div class="section-toggle" @click="toggleOriginal(card.id)">
                <span class="toggle-icon">{{ expandedOriginal.has(card.id) ? '▼' : '▶' }}</span>
                <span class="section-label">玩家原始内容</span>
                <span v-if="card.source_snapshot?.author_name" class="author-hint">{{ card.source_snapshot.author_name }}</span>
              </div>
              <div v-if="expandedOriginal.has(card.id)" class="original-content">
                {{ card.source_snapshot?.content || card.source_snapshot?.summary || '—' }}
              </div>
            </div>

            <!-- 需求描述（可编辑） -->
            <div class="card-section">
              <div class="section-label req-label">需求描述</div>
              <textarea
                class="req-textarea"
                :value="card.requirement_text"
                :rows="4"
                placeholder="AI 生成中，稍后自动填充…"
                @blur="onTextBlur(card, ($event.target as HTMLTextAreaElement).value)"
                @keydown.meta.enter.prevent="onTextBlur(card, ($event.target as HTMLTextAreaElement).value)"
                @keydown.ctrl.enter.prevent="onTextBlur(card, ($event.target as HTMLTextAreaElement).value)"
              ></textarea>
              <span v-if="savedId === card.id" class="saved-hint">✓ 已保存</span>
            </div>

            <!-- 状态 + 时间 -->
            <div class="card-footer">
              <select
                class="status-select"
                :class="`status-${card.status}`"
                :value="card.status"
                @change="onStatusChange(card, ($event.target as HTMLSelectElement).value)"
              >
                <option v-for="s in COLUMNS" :key="s.status" :value="s.status">{{ s.label }}</option>
              </select>
              <span class="card-date">{{ formatDate(card.created_at) }}</span>
            </div>
          </div>

          <div v-if="!grouped[col.status].length" class="col-empty">暂无</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue';
import { useGameStore } from '../../stores/game';
import api from '../../api';

interface RequirementCard {
  id: string;
  game_id: string;
  source_type: string;
  source_id: string;
  source_snapshot: Record<string, any>;
  requirement_text: string;
  status: string;
  created_at: string;
  updated_at: string;
}

const gameStore = useGameStore();
const cards = ref<RequirementCard[]>([]);
const loading = ref(false);
const filterType = ref('');
const expandedOriginal = ref<Set<string>>(new Set());
const savedId = ref<string | null>(null);

const COLUMNS = [
  { status: 'todo',        label: '未开始' },
  { status: 'in_progress', label: '进行中' },
  { status: 'done',        label: '已完成' },
];

const FILTERS = [
  { value: '',           label: '全部' },
  { value: 'comment',    label: '评论' },
  { value: 'bug',        label: 'BUG' },
  { value: 'suggestion', label: '建议' },
  { value: 'topic',      label: '话题' },
];

const SOURCE_LABEL: Record<string, string> = {
  comment:    '评论',
  bug:        'BUG',
  suggestion: '建议',
  topic:      '话题',
};

const PLATFORM_LABEL: Record<string, string> = {
  steam_store: 'Steam评价',
  steam_hub:   'Steam论坛',
  discord:     'Discord',
  qq:          'QQ群',
  xiaoheihe:   '小黑盒',
};

const CATEGORY_LABEL: Record<string, string> = {
  bug:        'Bug',
  suggestion: '建议',
  complaint:  '投诉',
  praise:     '好评',
  other:      '其他',
};

const grouped = computed(() => {
  const filtered = filterType.value
    ? cards.value.filter(c => c.source_type === filterType.value)
    : cards.value;
  return {
    todo:        filtered.filter(c => c.status === 'todo'),
    in_progress: filtered.filter(c => c.status === 'in_progress'),
    done:        filtered.filter(c => c.status === 'done'),
  };
});

async function load() {
  const gameId = gameStore.selectedGameId;
  if (!gameId) { cards.value = []; return; }
  loading.value = true;
  try {
    const { data } = await api.get('/requirements', { params: { game_id: gameId } });
    cards.value = data;
  } catch {
    cards.value = [];
  } finally {
    loading.value = false;
  }
}

function toggleOriginal(cardId: string) {
  const next = new Set(expandedOriginal.value);
  if (next.has(cardId)) next.delete(cardId);
  else next.add(cardId);
  expandedOriginal.value = next;
}

async function onTextBlur(card: RequirementCard, newText: string) {
  if (newText === card.requirement_text) return;
  card.requirement_text = newText;
  try {
    await api.patch(`/requirements/${card.id}`, { requirement_text: newText });
    savedId.value = card.id;
    setTimeout(() => { if (savedId.value === card.id) savedId.value = null; }, 2000);
  } catch {}
}

async function onStatusChange(card: RequirementCard, newStatus: string) {
  const prev = card.status;
  card.status = newStatus;  // 乐观更新
  try {
    await api.patch(`/requirements/${card.id}`, { status: newStatus });
  } catch {
    card.status = prev;     // 回滚
  }
}

async function deleteCard(cardId: string) {
  if (!confirm('确认删除这张需求卡？')) return;
  try {
    await api.delete(`/requirements/${cardId}`);
    cards.value = cards.value.filter(c => c.id !== cardId);
  } catch {}
}

function formatDate(t: string): string {
  if (!t) return '';
  const iso = t.endsWith('Z') || t.includes('+') ? t : t + 'Z';
  return new Date(iso).toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' });
}

onMounted(() => load());
watch(() => gameStore.selectedGameId, () => { filterType.value = ''; load(); });
</script>

<style scoped>
.page { max-width: 1400px; }

.page-header {
  display: flex;
  align-items: center;
  margin-bottom: 16px;
}
h2 {
  font-size: 22px;
  margin: 0;
  display: flex;
  align-items: baseline;
  gap: 10px;
}
.page-desc {
  font-size: 13px;
  color: var(--text-muted);
  font-weight: 400;
}

/* 筛选栏 */
.filter-bar {
  display: flex;
  gap: 8px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}
.filter-btn {
  padding: 5px 14px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 20px;
  color: var(--text-secondary);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s;
}
.filter-btn:hover { border-color: var(--accent); color: var(--accent); }
.filter-btn.active { background: var(--accent); border-color: var(--accent); color: #fff; }

.empty-board {
  text-align: center;
  padding: 64px;
  color: var(--text-muted);
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  font-size: 14px;
}

/* 看板布局 */
.board {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  align-items: start;
}

.board-col {
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
}

.col-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  border-bottom: 2px solid var(--border);
}
.col-todo    .col-header { border-bottom-color: var(--text-muted); }
.col-in_progress .col-header { border-bottom-color: #e9a800; }
.col-done    .col-header { border-bottom-color: #22c55e; }

.col-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}
.col-count {
  font-size: 12px;
  color: var(--text-muted);
  background: var(--bg-hover);
  padding: 1px 7px;
  border-radius: 10px;
}

.col-body {
  padding: 10px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-height: 80px;
}
.col-empty { font-size: 12px; color: var(--text-muted); text-align: center; padding: 16px 0; }

/* 需求卡（便利贴） */
.req-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  border-left: 3px solid var(--border);
  transition: border-color 0.15s;
}
.req-card:hover { border-left-color: var(--accent); }
.type-bug        { border-left-color: rgba(239,68,68,0.5); }
.type-suggestion { border-left-color: rgba(99,102,241,0.5); }
.type-topic      { border-left-color: rgba(34,197,94,0.4); }
.type-comment    { border-left-color: rgba(156,163,175,0.5); }

/* 卡头 */
.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.card-badges {
  display: flex;
  gap: 5px;
  flex-wrap: wrap;
}
.badge {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 3px;
  white-space: nowrap;
}
.src-comment    { background: rgba(156,163,175,0.15); color: var(--text-secondary); }
.src-bug        { background: rgba(239,68,68,0.12);   color: var(--danger,#ef4444); }
.src-suggestion { background: rgba(99,102,241,0.12);  color: var(--accent); }
.src-topic      { background: rgba(34,197,94,0.12);   color: var(--success,#22c55e); }
.badge-platform { background: var(--bg-hover); color: var(--text-muted); }
.cat-bug        { background: rgba(239,68,68,0.12);   color: var(--danger,#ef4444); }
.cat-suggestion { background: rgba(99,102,241,0.12);  color: var(--accent); }
.cat-complaint  { background: rgba(245,158,11,0.12);  color: var(--warning,#f59e0b); }
.cat-praise     { background: rgba(34,197,94,0.12);   color: var(--success,#22c55e); }
.cat-other      { background: var(--bg-hover);         color: var(--text-muted); }

.btn-delete {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 13px;
  opacity: 0.4;
  padding: 2px 4px;
  border-radius: 3px;
  transition: opacity 0.15s;
}
.btn-delete:hover { opacity: 1; }

/* 分区 */
.card-section { display: flex; flex-direction: column; gap: 5px; }

.section-toggle {
  display: flex;
  align-items: center;
  gap: 5px;
  cursor: pointer;
  user-select: none;
}
.toggle-icon  { font-size: 9px; color: var(--text-muted); }
.section-label { font-size: 11px; font-weight: 600; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.5px; }
.req-label    { margin-bottom: 2px; }
.author-hint  { font-size: 11px; color: var(--text-muted); }

.original-content {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 120px;
  overflow-y: auto;
  background: var(--bg-secondary);
  padding: 6px 8px;
  border-radius: 4px;
}

.req-textarea {
  width: 100%;
  box-sizing: border-box;
  padding: 7px 8px;
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 4px;
  color: var(--text-primary);
  font-size: 12px;
  line-height: 1.5;
  resize: vertical;
  font-family: inherit;
  outline: none;
  transition: border-color 0.15s;
}
.req-textarea:focus { border-color: var(--accent); }

.saved-hint {
  font-size: 11px;
  color: var(--success, #22c55e);
  align-self: flex-end;
}

/* 卡底部 */
.card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.status-select {
  font-size: 12px;
  font-weight: 600;
  padding: 3px 6px;
  border-radius: 4px;
  border: 1px solid var(--border);
  background: var(--bg-secondary);
  cursor: pointer;
  outline: none;
}
.status-todo        { color: var(--text-muted); }
.status-in_progress { color: #e9a800; }
.status-done        { color: #22c55e; }
.card-date { font-size: 11px; color: var(--text-muted); }

/* 响应式：窄屏转为单列 */
@media (max-width: 900px) {
  .board { grid-template-columns: 1fr; }
}
</style>
