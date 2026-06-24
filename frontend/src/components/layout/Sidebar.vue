<template>
  <aside class="sidebar">
    <div class="brand">游戏评论聚合</div>
    <div class="game-selector">
      <select :value="gameStore.selectedGameId ?? ''" @change="onGameChange">
        <option v-for="g in gameStore.games" :key="g.id" :value="g.id">{{ g.name }}</option>
      </select>
    </div>
    <nav>
      <router-link to="/dashboard">仪表盘</router-link>
      <router-link to="/comments">评论<span v-if="counts.commentPending" class="nav-pending">待处理 {{ counts.commentPending }}</span><span v-if="counts.total" class="nav-count">／共 {{ counts.total }}</span></router-link>
      <router-link to="/bugs">BUG<span v-if="counts.bugPending" class="nav-pending">待处理 {{ counts.bugPending }}</span><span v-if="counts.bug" class="nav-count">／共 {{ counts.bug }}</span></router-link>
      <router-link to="/suggestions">建议<span v-if="counts.suggestionPending" class="nav-pending">待处理 {{ counts.suggestionPending }}</span><span v-if="counts.suggestion" class="nav-count">／共 {{ counts.suggestion }}</span></router-link>
      <router-link to="/topics">话题<span v-if="counts.topicPending" class="nav-pending">待处理 {{ counts.topicPending }}</span><span v-if="counts.topic" class="nav-count">／共 {{ counts.topic }}</span></router-link>
      <!-- 群聊入口暂时隐藏（功能保留，路由 /chat 仍可直接访问） -->
      <!-- <router-link to="/chat">群聊</router-link> -->
      <router-link to="/bugreports">BUG上报<span v-if="counts.bugreportPending" class="nav-pending">待处理 {{ counts.bugreportPending }}</span></router-link>
      <router-link to="/announcements">更新公告<span v-if="counts.announcement" class="nav-count">（{{ counts.announcement }}）</span></router-link>
      <router-link to="/lineup">阵容分析</router-link>
      <router-link to="/requirements">需求板</router-link>
      <router-link v-if="auth.user?.is_admin" to="/games">游戏管理</router-link>
    </nav>
    <div class="theme-switcher">
      <button
        v-for="t in themeStore.THEMES"
        :key="t.key"
        class="theme-dot"
        :class="{ active: themeStore.current === t.key }"
        :style="{ background: t.dot }"
        :title="t.name"
        @click="themeStore.setTheme(t.key)"
      />
    </div>
    <div class="user" @click="logout">
      <span class="user-name">{{ auth.user?.display_name || auth.user?.username }}</span>
      <span class="user-logout">退出登录</span>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from '../../stores/auth';
import { useGameStore } from '../../stores/game';
import { useThemeStore } from '../../stores/theme';
import api from '../../api';

const router = useRouter();
const auth = useAuthStore();
const gameStore = useGameStore();
const themeStore = useThemeStore();
const counts = ref({
  total: 0, bug: 0, suggestion: 0, topic: 0, announcement: 0,
  commentPending: 0, bugPending: 0, suggestionPending: 0, topicPending: 0, bugreportPending: 0,
});

onMounted(async () => {
  await gameStore.loadGames();
  if (!gameStore.selectedGameId && gameStore.games.length > 0) {
    gameStore.select(gameStore.games[0].id);
  }
  fetchCounts();
});

async function fetchCounts() {
  try {
    const params = gameStore.selectedGameId ? { game_id: gameStore.selectedGameId } : {};
    const [statsRes, annRes, bugRes] = await Promise.all([
      api.get('/dashboard/stats', { params }),
      api.get('/announcements/count', { params }).catch(() => ({ data: { count: 0 } })),
      api.get('/bugreports/stats').catch(() => ({ data: { pending: 0 } })),
    ]);
    const data = statsRes.data;
    counts.value = {
      total: data.total_comments,
      bug: data.bug_count,
      suggestion: data.suggestion_count,
      topic: data.topic_count ?? 0,
      announcement: annRes.data.count ?? 0,
      commentPending: data.comment_pending ?? 0,
      bugPending: data.bug_pending ?? 0,
      suggestionPending: data.suggestion_pending ?? 0,
      topicPending: data.topic_pending ?? 0,
      bugreportPending: bugRes.data.pending ?? 0,
    };
  } catch {}
}

watch(() => gameStore.selectedGameId, () => { fetchCounts(); });

function onGameChange(e: Event) {
  const val = (e.target as HTMLSelectElement).value;
  gameStore.select(val || null);
}

function logout() {
  auth.logout();
  router.push('/login');
}
</script>

<style scoped>
.sidebar {
  width: 220px;
  min-height: 100vh;
  background: var(--bg-secondary);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  padding: 16px 0;
  flex-shrink: 0;
}

.brand {
  font-size: 20px;
  font-weight: 700;
  padding: 8px 20px 16px;
  color: var(--accent);
  letter-spacing: 2px;
}

.game-selector {
  padding: 0 12px 16px;
  border-bottom: 1px solid var(--border);
}

.game-selector select {
  width: 100%;
  padding: 7px 10px;
  background: var(--bg-primary);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  color: var(--text-primary);
  font-size: 13px;
  outline: none;
  cursor: pointer;
}

.game-selector select:focus {
  border-color: var(--accent);
}

nav {
  display: flex;
  flex-direction: column;
  flex: 1;
  padding-top: 8px;
}

nav a {
  padding: 10px 20px;
  color: var(--text-secondary);
  font-size: 14px;
  transition: all 0.15s;
  border-left: 3px solid transparent;
}

nav a:hover,
nav a.router-link-active {
  color: var(--text-primary);
  background: var(--bg-hover);
  border-left-color: var(--accent);
}

.theme-switcher {
  display: flex;
  gap: 10px;
  align-items: center;
  padding: 14px 20px;
  border-top: 1px solid var(--border);
}

.theme-dot {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  border: none;
  padding: 0;
  cursor: pointer;
  outline: 2px solid transparent;
  outline-offset: 2px;
  transition: transform 0.15s, outline-color 0.15s;
}

.theme-dot:hover {
  transform: scale(1.15);
}

.theme-dot.active {
  outline-color: var(--text-primary);
  transform: scale(1.15);
}

.user {
  padding: 16px 20px;
  color: var(--text-muted);
  font-size: 13px;
  cursor: pointer;
  border-top: 1px solid var(--border);
  display: flex;
  align-items: center;
  gap: 8px;
}

.user-name {
  flex: 1;
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.user:hover .user-logout { color: var(--danger); }

.nav-count { color: var(--text-muted); font-size: 12px; }
.nav-pending {
  margin-left: 6px;
  font-size: 11px;
  color: var(--accent);
  font-weight: 600;
}
</style>
