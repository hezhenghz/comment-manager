<template>
  <div class="app-shell">
    <Sidebar />
    <main class="main-content">
      <router-view />
    </main>
  </div>
</template>

<script setup lang="ts">
import Sidebar from './Sidebar.vue';
</script>

<style scoped>
.app-shell {
  display: flex;
  min-height: 100vh;
}

.main-content {
  flex: 1;
  padding: 24px 32px;
  overflow-y: auto;
  max-height: 100vh;
}
</style>
