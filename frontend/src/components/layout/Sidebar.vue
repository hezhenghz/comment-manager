<template>
  <aside class="sidebar">
    <div class="brand">CM</div>
    <nav>
      <router-link to="/dashboard">Dashboard</router-link>
      <router-link to="/comments">Comments</router-link>
      <router-link to="/reports">Reports</router-link>
      <router-link to="/alerts">Alerts</router-link>
      <router-link to="/games">Games</router-link>
      <router-link to="/settings">Settings</router-link>
    </nav>
    <div class="user" @click="logout">Logout</div>
  </aside>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router';
import { useAuthStore } from '../../stores/auth';

const router = useRouter();
const auth = useAuthStore();

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
  padding: 8px 20px 24px;
  color: var(--accent);
  letter-spacing: 2px;
}

nav {
  display: flex;
  flex-direction: column;
  flex: 1;
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
}

.user:hover { color: var(--danger); }
</style>
