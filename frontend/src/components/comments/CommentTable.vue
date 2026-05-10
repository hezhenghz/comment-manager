<template>
  <div class="page">
    <h2>Comments</h2>
    <SearchBar @search="onSearch" />
    <div class="filters">
      <select v-model="sentiment" @change="load">
        <option value="">All Sentiments</option>
        <option value="positive">Positive</option>
        <option value="negative">Negative</option>
        <option value="neutral">Neutral</option>
      </select>
      <select v-model="category" @change="load">
        <option value="">All Categories</option>
        <option value="bug">Bug</option>
        <option value="suggestion">Suggestion</option>
        <option value="complaint">Complaint</option>
        <option value="praise">Praise</option>
        <option value="other">Other</option>
      </select>
      <select v-model="platform" @change="load">
        <option value="">All Platforms</option>
        <option value="steam_store">Steam Store</option>
        <option value="steam_hub">Steam Hub</option>
      </select>
    </div>
    <table v-if="store.items.length">
      <thead>
        <tr>
          <th>Platform</th>
          <th>Content</th>
          <th>Sentiment</th>
          <th>Category</th>
          <th>Lang</th>
          <th>Published</th>
          <th>Link</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="c in store.items" :key="c.id">
          <td><span class="badge">{{ c.platform }}</span></td>
          <td class="content-cell">{{ c.content.slice(0, 150) }}{{ c.content.length > 150 ? '...' : '' }}</td>
          <td><span class="sentiment" :class="c.sentiment || 'neutral'">{{ c.sentiment || '-' }}</span></td>
          <td>{{ c.category || '-' }}</td>
          <td>{{ c.content_lang || '-' }}</td>
          <td>{{ c.published_at ? new Date(c.published_at).toLocaleDateString() : '-' }}</td>
          <td><a v-if="c.source_url" :href="c.source_url" target="_blank">Open</a></td>
        </tr>
      </tbody>
    </table>
    <div v-else class="empty">No comments found.</div>
    <div class="pagination" v-if="store.total > store.pageSize">
      <button :disabled="store.page <= 1" @click="prevPage">Prev</button>
      <span>{{ store.page }} / {{ Math.ceil(store.total / store.pageSize) }}</span>
      <button :disabled="store.page >= Math.ceil(store.total / store.pageSize)" @click="nextPage">Next</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useCommentsStore } from '../../stores/comments';
import SearchBar from './SearchBar.vue';

const store = useCommentsStore();
const sentiment = ref('');
const category = ref('');
const platform = ref('');

onMounted(() => load());

function load() {
  const params: any = {};
  if (sentiment.value) params.sentiment = sentiment.value;
  if (category.value) params.category = category.value;
  if (platform.value) params.platform = platform.value;
  store.loadComments(params);
}

function onSearch(q: string) {
  store.search(q);
}

function prevPage() { store.page--; load(); }
function nextPage() { store.page++; load(); }
</script>

<style scoped>
.page {
  max-width: 1400px;
}

h2 {
  font-size: 22px;
  margin-bottom: 20px;
}

.filters {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}

select {
  padding: 8px 12px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  color: var(--text-primary);
  font-size: 13px;
  outline: none;
}

table {
  width: 100%;
  border-collapse: collapse;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
}

th, td {
  padding: 10px 14px;
  text-align: left;
  font-size: 13px;
  border-bottom: 1px solid var(--border);
}

th {
  background: var(--bg-hover);
  color: var(--text-secondary);
  font-weight: 600;
}

td {
  color: var(--text-primary);
}

.badge {
  background: var(--accent);
  color: #fff;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  white-space: nowrap;
}

.sentiment { font-size: 12px; font-weight: 600; }
.sentiment.positive { color: var(--positive); }
.sentiment.negative { color: var(--negative); }
.sentiment.neutral { color: var(--neutral); }

.content-cell { max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

a { font-size: 12px; color: var(--accent); }

.empty {
  text-align: center;
  padding: 48px;
  color: var(--text-muted);
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
}

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

.pagination button:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
</style>
