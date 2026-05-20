<template>
  <div class="game-form">
    <!-- 输入行 -->
    <div class="input-row">
      <input
        v-model="name"
        type="text"
        placeholder="游戏名称（二选一）"
        :disabled="loading"
        @keyup.enter="submit"
      />
      <input
        v-model="steamAppId"
        type="text"
        placeholder="Steam App ID（二选一）"
        :disabled="loading"
        @keyup.enter="submit"
      />
      <button @click="submit" :disabled="loading || (!name && !steamAppId)">
        <span v-if="loading" class="spinner">⏳</span>
        <span v-else>ADD</span>
      </button>
    </div>

    <!-- Steam 搜索结果面板 -->
    <div v-if="results.length" class="results-panel">
      <div class="results-hint">
        在 Steam 找到以下游戏，点击选择；或
        <button class="link-btn" @click="skipLookup">直接添加「{{ pendingName }}」</button>
      </div>
      <div
        v-for="r in results"
        :key="r.app_id"
        class="result-item"
        @click="pickResult(r)"
      >
        <img v-if="r.icon_url" :src="r.icon_url" class="game-icon" />
        <div v-else class="game-icon-placeholder" />
        <div class="result-info">
          <span class="result-name">{{ r.name }}</span>
          <span class="result-id">App {{ r.app_id }}</span>
        </div>
      </div>
    </div>

    <!-- 没有搜索结果时提示直接添加 -->
    <div v-if="noResults" class="no-results">
      Steam 未找到「{{ pendingName }}」，
      <button class="link-btn" @click="skipLookup">直接添加</button>
    </div>

    <!-- 错误提示 -->
    <div v-if="error" class="error-msg">{{ error }}</div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import api from '../../api';

const emit = defineEmits<{ created: [] }>();

interface SteamResult {
  app_id: string;
  name: string;
  icon_url: string | null;
}

const name = ref('');
const steamAppId = ref('');
const iconUrl = ref('');
const loading = ref(false);
const results = ref<SteamResult[]>([]);
const noResults = ref(false);
const error = ref('');
const pendingName = ref(''); // 触发搜索时的名称，用于"直接添加"文案

async function submit() {
  error.value = '';
  results.value = [];
  noResults.value = false;

  if (!name.value && !steamAppId.value) {
    error.value = '游戏名称或 Steam App ID 至少填写一项';
    return;
  }

  // 情况 1：两者都填 → 直接创建
  if (name.value && steamAppId.value) {
    await doCreate(name.value, steamAppId.value, iconUrl.value);
    return;
  }

  // 情况 2：只有 App ID → 自动从 Steam 补名称
  if (steamAppId.value && !name.value) {
    loading.value = true;
    try {
      const { data } = await api.get('/games/steam-lookup', { params: { app_id: steamAppId.value } });
      if (data.length > 0) {
        name.value = data[0].name;
        iconUrl.value = data[0].icon_url || '';
      }
    } catch {
      // lookup 失败，以 App ID 作为名称兜底
    } finally {
      loading.value = false;
    }
    await doCreate(name.value || steamAppId.value, steamAppId.value, iconUrl.value);
    return;
  }

  // 情况 3：只有名称 → 搜索 Steam，让用户选择
  pendingName.value = name.value;
  loading.value = true;
  try {
    const { data } = await api.get('/games/steam-lookup', { params: { name: name.value } });
    if (data.length > 0) {
      results.value = data;
    } else {
      noResults.value = true;
    }
  } catch {
    // 搜索失败，直接创建
    await doCreate(name.value, '', '');
  } finally {
    loading.value = false;
  }
}

/** 用户从搜索结果中点击某一项 */
async function pickResult(r: SteamResult) {
  results.value = [];
  noResults.value = false;
  await doCreate(r.name, r.app_id, r.icon_url || '');
}

/** 用户忽略搜索结果，直接以输入名称创建 */
async function skipLookup() {
  const n = pendingName.value;
  results.value = [];
  noResults.value = false;
  await doCreate(n, '', '');
}

/** 实际调用创建接口 */
async function doCreate(gameName: string, appId: string, icon: string) {
  loading.value = true;
  error.value = '';
  try {
    await api.post('/games', {
      name: gameName || null,
      steam_app_id: appId || null,
      icon_url: icon || null,
    });
    emit('created');
    name.value = '';
    steamAppId.value = '';
    iconUrl.value = '';
    results.value = [];
    noResults.value = false;
  } catch (e: any) {
    if (e.response?.status === 409) {
      error.value = e.response.data.detail || '游戏已存在';
    } else {
      error.value = '添加失败，请重试';
    }
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped>
.game-form {
  margin-bottom: 20px;
}

.input-row {
  display: flex;
  gap: 10px;
}

input {
  padding: 8px 12px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  color: var(--text-primary);
  font-size: 13px;
  outline: none;
  flex: 1;
}
input:focus { border-color: var(--accent); }
input:disabled { opacity: 0.5; cursor: not-allowed; }

button {
  padding: 8px 20px;
  background: var(--accent);
  color: #fff;
  border: none;
  border-radius: var(--radius);
  cursor: pointer;
  font-size: 13px;
  white-space: nowrap;
}
button:hover:not(:disabled) { background: var(--accent-hover); }
button:disabled { opacity: 0.5; cursor: not-allowed; }

/* Steam 搜索结果面板 */
.results-panel {
  margin-top: 8px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
}

.results-hint {
  padding: 8px 12px;
  font-size: 12px;
  color: var(--text-secondary);
  border-bottom: 1px solid var(--border);
  background: var(--bg-hover);
}

.result-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  cursor: pointer;
  transition: background 0.15s;
}
.result-item:hover { background: var(--bg-hover); }

.game-icon {
  width: 48px;
  height: 22px;
  object-fit: cover;
  border-radius: 2px;
  flex-shrink: 0;
}
.game-icon-placeholder {
  width: 48px;
  height: 22px;
  background: var(--border);
  border-radius: 2px;
  flex-shrink: 0;
}

.result-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.result-name { font-size: 13px; color: var(--text-primary); }
.result-id   { font-size: 11px; color: var(--text-muted); }

/* 按钮式链接 */
.link-btn {
  padding: 0;
  background: none;
  color: var(--accent);
  font-size: inherit;
  text-decoration: underline;
  cursor: pointer;
}
.link-btn:hover { background: none; color: var(--accent-hover); }

.no-results {
  margin-top: 6px;
  font-size: 12px;
  color: var(--text-secondary);
}

.error-msg {
  margin-top: 6px;
  font-size: 12px;
  color: var(--danger);
}
</style>
