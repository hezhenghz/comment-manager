<template>
  <div class="chat-page">
    <!-- 页面头部 -->
    <div class="chat-header">
      <h2>群聊<span class="chat-desc">{{ gameName ? `· ${gameName}` : '' }}</span></h2>
    </div>

    <div v-if="!gameStore.selectedGameId" class="empty">请先在左上角选择游戏</div>
    <template v-else>
      <!-- 消息列表 -->
      <div class="msg-list" ref="listRef">
        <div v-if="loading" class="msg-empty">加载中…</div>
        <div v-else-if="!messages.length" class="msg-empty">暂无消息，来第一个发言吧 🎉</div>
        <template v-else>
          <div
            v-for="msg in messages"
            :key="msg.id"
            class="bubble-wrap"
            :class="msg.user_id === myUserId ? 'bubble-wrap--self' : 'bubble-wrap--other'"
          >
            <!-- 他人消息：名称在左上 -->
            <div v-if="msg.user_id !== myUserId" class="bubble-name">{{ msg.display_name }}</div>
            <div class="bubble" :class="msg.user_id === myUserId ? 'bubble--self' : 'bubble--other'">
              <span class="bubble-text">{{ msg.content }}</span>
              <span class="bubble-time">{{ formatTime(msg.created_at) }}</span>
            </div>
          </div>
        </template>
      </div>

      <!-- 输入框 -->
      <div class="input-area">
        <textarea
          ref="textareaRef"
          v-model="inputText"
          class="chat-input"
          placeholder="输入消息，Enter 发送，Shift+Enter 换行"
          rows="3"
          @keydown="onKeydown"
        />
        <button class="btn-send" :disabled="sending || !inputText.trim()" @click="sendMessage">
          {{ sending ? '发送中…' : '发送' }}
        </button>
      </div>
      <div v-if="sendError" class="send-error">{{ sendError }}</div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue';
import { useGameStore } from '../../stores/game';
import { useAuthStore } from '../../stores/auth';
import api from '../../api';

interface ChatMsg {
  id: string;
  game_id: string;
  user_id: string;
  display_name: string;
  content: string;
  created_at: string;
}

const gameStore = useGameStore();
const authStore = useAuthStore();

const messages   = ref<ChatMsg[]>([]);
const inputText  = ref('');
const loading    = ref(false);
const sending    = ref(false);
const sendError  = ref('');
const listRef    = ref<HTMLElement | null>(null);
const textareaRef = ref<HTMLTextAreaElement | null>(null);

// 最后一条消息的 created_at，用于增量轮询
const lastCreatedAt = ref<string | null>(null);
let pollTimer: ReturnType<typeof setTimeout> | null = null;

const myUserId = computed(() => authStore.user?.id ?? '');
const gameName = computed(() => {
  const id = gameStore.selectedGameId;
  if (!id) return '';
  return gameStore.games.find(g => g.id === id)?.name ?? '';
});

// ── 初始加载 & 轮询 ─────────────────────────────────────────────────

async function initialLoad() {
  const gameId = gameStore.selectedGameId;
  if (!gameId) return;
  loading.value = true;
  try {
    const { data } = await api.get<ChatMsg[]>('/chat/messages', {
      params: { game_id: gameId, limit: 50 },
    });
    messages.value = data;
    if (data.length) lastCreatedAt.value = data[data.length - 1].created_at;
  } catch {
    // 静默失败
  } finally {
    loading.value = false;
    await scrollToBottom();
  }
}

async function poll() {
  const gameId = gameStore.selectedGameId;
  if (!gameId) return;
  try {
    const params: Record<string, string | number> = { game_id: gameId, limit: 50 };
    if (lastCreatedAt.value) params.since = lastCreatedAt.value;
    const { data } = await api.get<ChatMsg[]>('/chat/messages', { params });
    if (data.length) {
      messages.value.push(...data);
      lastCreatedAt.value = data[data.length - 1].created_at;
      await scrollToBottom();
    }
  } catch {
    // 轮询失败静默
  } finally {
    schedulePoll();
  }
}

function schedulePoll() {
  clearTimer();
  pollTimer = setTimeout(poll, 3000);
}

function clearTimer() {
  if (pollTimer !== null) { clearTimeout(pollTimer); pollTimer = null; }
}

// ── 滚动 ─────────────────────────────────────────────────────────────

async function scrollToBottom() {
  await nextTick();
  if (listRef.value) {
    listRef.value.scrollTop = listRef.value.scrollHeight;
  }
}

// ── 发送 ─────────────────────────────────────────────────────────────

async function sendMessage() {
  const content = inputText.value.trim();
  if (!content || sending.value) return;
  const gameId = gameStore.selectedGameId;
  if (!gameId) return;

  sending.value = true;
  sendError.value = '';

  // 乐观更新：立即追加到本地（created_at 用当前时间占位）
  const optimistic: ChatMsg = {
    id: `optimistic-${Date.now()}`,
    game_id: gameId,
    user_id: myUserId.value,
    display_name: authStore.user?.display_name || authStore.user?.username || '我',
    content,
    created_at: new Date().toISOString(),
  };
  messages.value.push(optimistic);
  inputText.value = '';
  await scrollToBottom();

  try {
    const { data } = await api.post<ChatMsg>('/chat/messages', { content }, {
      params: { game_id: gameId },
    });
    // 用服务器返回替换乐观条目
    const idx = messages.value.findIndex(m => m.id === optimistic.id);
    if (idx !== -1) messages.value.splice(idx, 1, data);
    lastCreatedAt.value = data.created_at;
  } catch (e: any) {
    // 回滚乐观更新
    messages.value = messages.value.filter(m => m.id !== optimistic.id);
    sendError.value = e?.response?.data?.detail ?? '发送失败，请重试';
    inputText.value = content; // 恢复输入
  } finally {
    sending.value = false;
  }
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
}

// ── 时间格式化 ────────────────────────────────────────────────────────

function formatTime(t: string): string {
  const iso = t.endsWith('Z') || t.includes('+') ? t : t + 'Z';
  return new Date(iso).toLocaleString('zh-CN', {
    month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
  });
}

// ── 生命周期 ──────────────────────────────────────────────────────────

onMounted(() => {
  initialLoad().then(() => schedulePoll());
});

onUnmounted(() => clearTimer());

watch(() => gameStore.selectedGameId, () => {
  clearTimer();
  messages.value = [];
  lastCreatedAt.value = null;
  sendError.value = '';
  inputText.value = '';
  initialLoad().then(() => schedulePoll());
});
</script>

<style scoped>
.chat-page {
  max-width: 800px;
  display: flex;
  flex-direction: column;
  height: calc(100vh - 48px);   /* 减去 AppShell header 高度 */
}

.chat-header {
  flex-shrink: 0;
  margin-bottom: 12px;
}

h2 {
  font-size: 22px;
  margin: 0;
  display: flex;
  align-items: baseline;
  gap: 10px;
}

.chat-desc {
  font-size: 13px;
  color: var(--text-muted);
  font-weight: 400;
}

.empty {
  text-align: center;
  padding: 48px;
  color: var(--text-muted);
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  flex: 1;
}

/* ── 消息列表 ── */
.msg-list {
  flex: 1;
  overflow-y: auto;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 0;
}

.msg-empty {
  text-align: center;
  color: var(--text-muted);
  font-size: 13px;
  padding: 24px 0;
}

/* ── 气泡 ── */
.bubble-wrap {
  display: flex;
  flex-direction: column;
  max-width: 72%;
}

.bubble-wrap--self {
  align-self: flex-end;
  align-items: flex-end;
}

.bubble-wrap--other {
  align-self: flex-start;
  align-items: flex-start;
}

.bubble-name {
  font-size: 11px;
  color: var(--text-muted);
  margin-bottom: 3px;
  padding-left: 2px;
}

.bubble {
  display: inline-flex;
  align-items: flex-end;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 12px;
  max-width: 100%;
  word-break: break-all;
}

.bubble--self {
  background: var(--accent);
  color: #fff;
  border-bottom-right-radius: 4px;
  flex-direction: row-reverse;
}

.bubble--other {
  background: var(--bg-hover);
  color: var(--text-primary);
  border-bottom-left-radius: 4px;
}

.bubble-text {
  font-size: 14px;
  line-height: 1.5;
  white-space: pre-wrap;
}

.bubble-time {
  font-size: 10px;
  opacity: 0.65;
  white-space: nowrap;
  flex-shrink: 0;
}

/* ── 输入区域 ── */
.input-area {
  flex-shrink: 0;
  display: flex;
  gap: 10px;
  margin-top: 12px;
}

.chat-input {
  flex: 1;
  resize: none;
  padding: 10px 12px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  color: var(--text-primary);
  font-size: 14px;
  font-family: inherit;
  line-height: 1.5;
  outline: none;
  transition: border-color 0.15s;
}

.chat-input:focus { border-color: var(--accent); }

.btn-send {
  padding: 0 20px;
  background: var(--accent);
  border: none;
  border-radius: var(--radius);
  color: #fff;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: opacity 0.15s;
  align-self: stretch;
}

.btn-send:hover:not(:disabled) { opacity: 0.85; }
.btn-send:disabled { opacity: 0.45; cursor: not-allowed; }

.send-error {
  font-size: 12px;
  color: var(--danger);
  margin-top: 4px;
  flex-shrink: 0;
}
</style>
