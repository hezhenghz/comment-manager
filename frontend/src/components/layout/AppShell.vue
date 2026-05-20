<template>
  <div class="app-shell">
    <Sidebar />
    <main class="main-content">
      <router-view />
    </main>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue';
import Sidebar from './Sidebar.vue';
import { useAuthStore } from '../../stores/auth';

const auth = useAuthStore();

onMounted(async () => {
  if (!auth.user && localStorage.getItem('token')) {
    await auth.fetchMe();
  }
});
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
