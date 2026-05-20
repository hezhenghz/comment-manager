<template>
  <div class="chart-card feed" id="bug-feed">
    <h3>🐛 Bug 反馈</h3>
    <div v-if="!bugs.length" class="empty">暂无 Bug 反馈</div>
    <div v-else class="feed-list">
      <div v-for="c in bugs" :key="c.id" class="feed-item">
        <span class="feed-platform-badge" :class="platformClass(c.platform)">
          {{ platformLabel(c.platform) }}
        </span>
        <span class="feed-text">{{ c.content.slice(0, 140) }}{{ c.content.length > 140 ? '…' : '' }}</span>
        <span class="feed-time">{{ formatTime(c.published_at) }}</span>
        <a v-if="c.source_url" :href="c.source_url" target="_blank" class="feed-link">查看原文</a>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue';
import api from '../../api';

const props = defineProps<{ gameId: string | null }>();

const bugs = ref<any[]>([]);

const PLATFORM_MAP: Record<string, string> = {
  steam_store: 'Steam评价', steam_hub: 'Steam论坛',
  discord: 'Discord', qq: 'QQ群', xiaoheihe: '小黑盒',
};
const PLATFORM_CLASS: Record<string, string> = {
  steam_store: 'p-steam-store', steam_hub: 'p-steam-hub',
  discord: 'p-discord', qq: 'p-qq', xiaoheihe: 'p-xiaoheihe',
};

function platformLabel(p: string) { return PLATFORM_MAP[p] ?? p; }
function platformClass(p: string) { return PLATFORM_CLASS[p] ?? 'p-other'; }
function formatTime(t: string | null) {
  if (!t) return '';
  return new Date(t).toLocaleDateString('zh-CN');
}

async function fetchBugs() {
  try {
    const params: any = { page: 1, page_size: 20, category: 'bug' };
    if (props.gameId) params.game_id = props.gameId;
    const { data } = await api.get('/comments', { params });
    bugs.value = data.items;
  } catch {}
}

onMounted(fetchBugs);
watch(() => props.gameId, fetchBugs);
</script>

<style scoped>
.chart-card.feed {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 20px;
  margin-top: 20px;
}

h3 {
  font-size: 14px;
  color: var(--text-secondary);
  margin-bottom: 12px;
}

.empty {
  color: var(--text-muted);
  font-size: 13px;
  padding: 16px 0;
}

.feed-list { max-height: 400px; overflow-y: auto; }

.feed-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
  border-bottom: 1px solid var(--border);
  font-size: 13px;
}

.feed-platform-badge {
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 10px;
  white-space: nowrap;
  flex-shrink: 0;
  font-weight: 500;
}
.p-steam-store { background: rgba(30,111,214,0.18); color: #4a9eff; }
.p-steam-hub   { background: rgba(59,165,93,0.18);  color: #4caf74; }
.p-discord     { background: rgba(114,137,218,0.2); color: #7289da; }
.p-qq          { background: rgba(18,183,245,0.18); color: #12b7f5; }
.p-xiaoheihe   { background: rgba(255,120,30,0.18); color: #ff781e; }
.p-other       { background: rgba(107,114,128,0.18); color: var(--text-secondary); }

.feed-text {
  flex: 1;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.feed-time { color: var(--text-muted); font-size: 11px; flex-shrink: 0; }

.feed-link { font-size: 11px; color: var(--accent); flex-shrink: 0; }
</style>
