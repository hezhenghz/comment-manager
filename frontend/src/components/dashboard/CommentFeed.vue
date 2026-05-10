<template>
  <div class="chart-card feed">
    <h3>Latest Comments</h3>
    <TransitionGroup name="feed" tag="div" class="feed-list">
      <div v-for="c in comments" :key="c.id" class="feed-item">
        <span class="feed-platform-badge">{{ c.platform }}</span>
        <span class="feed-sentiment-badge" :class="c.sentiment || 'neutral'">{{ c.sentiment || 'neutral' }}</span>
        <span class="feed-text">{{ c.content.slice(0, 120) }}{{ c.content.length > 120 ? '...' : '' }}</span>
        <span class="feed-time">{{ formatTime(c.published_at) }}</span>
      </div>
    </TransitionGroup>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted } from 'vue';
import api from '../../api';

const props = defineProps<{ gameId: string | null }>();

const comments = ref<any[]>([]);

let timer: number;

function formatTime(t: string | null) {
  if (!t) return '';
  return new Date(t).toLocaleString();
}

async function fetchLatest() {
  try {
    const params: any = { page: 1, page_size: 20 };
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
  background: var(--accent);
  color: #fff;
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 10px;
  white-space: nowrap;
  flex-shrink: 0;
}

.feed-sentiment-badge {
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 10px;
  flex-shrink: 0;
}
.feed-sentiment-badge.positive { background: rgba(34,197,94,0.2); color: var(--positive); }
.feed-sentiment-badge.negative { background: rgba(239,68,68,0.2); color: var(--negative); }
.feed-sentiment-badge.neutral { background: rgba(107,114,128,0.2); color: var(--neutral); }

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
