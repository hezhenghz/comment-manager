<template>
  <div class="chart-card feed">
    <h3>最新评论</h3>
    <TransitionGroup name="feed" tag="div" class="feed-list">
      <div v-for="c in comments" :key="c.id" class="feed-item">
        <span class="feed-platform-badge" :class="platformClass(c.platform)">{{ platformLabel(c.platform) }}</span>
        <span class="feed-sentiment-badge" :class="c.sentiment || 'neutral'">{{ sentimentLabel(c.sentiment) }}</span>
        <span class="feed-text">{{ c.content.slice(0, 120) }}{{ c.content.length > 120 ? '...' : '' }}</span>
        <span class="feed-time">{{ formatTime(c.published_at) }}</span>
      </div>
    </TransitionGroup>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted } from 'vue';
import api from '../../api';

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
function platformLabel(p: string) { return PLATFORM_MAP[p] ?? p; }
function platformClass(p: string) { return PLATFORM_CLASS[p] ?? 'platform-other'; }
function sentimentLabel(s: string | null) { return SENTIMENT_MAP[s ?? ''] ?? '中性'; }

const props = defineProps<{ gameId: string | null }>();

const comments = ref<any[]>([]);

let timer: number;

function formatTime(t: string | null) {
  if (!t) return '';
  return new Date(t).toLocaleString();
}

async function fetchLatest() {
  try {
    const params: any = { page: 1, page_size: 20, exclude_platform: 'qq,discord' };
    if (props.gameId) params.game_id = props.gameId;
    const { data } = await api.get('/comments', { params });
    comments.value = data.items;
  } catch {}
}

onMounted(() => {
  fetchLatest();
  timer = window.setInterval(fetchLatest, 30000);
});

onUnmounted(() => clearInterval(timer));

watch(() => props.gameId, () => fetchLatest());
</script>

<style scoped>
.chart-card.feed {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 20px;
}

h3 {
  font-size: 14px;
  color: var(--text-secondary);
  margin-bottom: 12px;
}

.feed-list {
  max-height: 400px;
  overflow-y: auto;
}

.feed-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
  border-bottom: 1px solid var(--border);
  font-size: 13px;
}

.feed-platform-badge {
  display: inline-block;
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 10px;
  white-space: nowrap;
  flex-shrink: 0;
  font-weight: 500;
}
.platform-steam-store { background: rgba(30, 111, 214, 0.18); color: #4a9eff; }
.platform-steam-hub   { background: rgba(59, 165, 93, 0.18);  color: #4caf74; }
.platform-discord     { background: rgba(114, 137, 218, 0.2); color: #7289da; }
.platform-qq          { background: rgba(18, 183, 245, 0.18); color: #12b7f5; }
.platform-xiaoheihe   { background: rgba(255, 120, 30, 0.18); color: #ff781e; }
.platform-other       { background: rgba(107, 114, 128, 0.18); color: var(--text-secondary); }

.feed-sentiment-badge {
  font-size: 12px;
  font-weight: 600;
  flex-shrink: 0;
}
.feed-sentiment-badge.positive { color: var(--positive); }
.feed-sentiment-badge.negative { color: var(--negative); }
.feed-sentiment-badge.neutral  { color: var(--neutral); }

.feed-text {
  flex: 1;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.feed-time {
  color: var(--text-muted);
  font-size: 11px;
  flex-shrink: 0;
}

/* TransitionGroup animations */
.feed-enter-active { transition: all 0.4s ease; }
.feed-enter-from { opacity: 0; transform: translateY(-20px); }
</style>
