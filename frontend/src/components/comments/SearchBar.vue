<template>
  <div class="search-bar">
    <input
      v-model="query"
      type="text"
      placeholder="Search comments (supports cross-language semantic search)..."
      @keyup.enter="emitSearch"
    />
    <button @click="emitSearch">Search</button>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';

const emit = defineEmits<{ search: [q: string] }>();
const query = ref('');

function emitSearch() {
  if (query.value.trim()) {
    emit('search', query.value.trim());
  }
}
</script>

<style scoped>
.search-bar {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}

input {
  flex: 1;
  padding: 10px 14px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  color: var(--text-primary);
  font-size: 14px;
  outline: none;
}

input:focus { border-color: var(--accent); }

button {
  padding: 10px 20px;
  background: var(--accent);
  color: #fff;
  border: none;
  border-radius: var(--radius);
  cursor: pointer;
  font-size: 14px;
}

button:hover { background: var(--accent-hover); }
</style>
