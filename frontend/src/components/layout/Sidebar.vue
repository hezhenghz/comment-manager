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
      <router-link to="/comments">评论<span v-if="counts.total" class="nav-count">（{{ counts.total }}）</span></router-link>
      <router-link to="/bugs">BUG<span v-if="counts.bug" class="nav-count">（{{ counts.bug }}）</span></router-link>
      <router-link to="/suggestions">建议<span v-if="counts.suggestion" class="nav-count">（{{ counts.suggestion }}）</span></router-link>
      <router-link to="/topics">话题<span v-if="counts.topic" class="nav-count">（{{ counts.topic }}）</span></router-link>
      <router-link to="/requirements">需求板</router-link>
      <router-link to="/chat">群聊</router-link>
      <router-link v-if="auth.user?.is_admin" to="/games">游戏管理</router-link>
    </nav>
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
import api from '../../api';

const router = useRouter();
const auth = useAuthStore();
const gameStore = useGameStore();
const counts = ref({ total: 0, bug: 0, suggestion: 0, topic: 0 });

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
    const { data } = await api.get('/dashboard/stats', { params });
    counts.value = { total: data.total_comments, bug: data.bug_count, suggestion: data.suggestion_count, topic: data.topic_count ?? 0 };
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
</style>
