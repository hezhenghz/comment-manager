import { defineStore } from 'pinia';
import api from '../api';

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: null as { id: string; username: string; display_name: string; is_admin: boolean } | null,
  }),
  actions: {
    async login(username: string, password: string) {
      const { data } = await api.post('/auth/login', { username, password });
      localStorage.setItem('token', data.access_token);
      // is_admin 需等 fetchMe 后才知道，登录后立即调用
      this.user = { id: '', username, display_name: data.display_name, is_admin: false };
      await this.fetchMe();
    },
    logout() {
      localStorage.removeItem('token');
      this.user = null;
    },
    async fetchMe() {
      try {
        const { data } = await api.get('/auth/me');
        this.user = { id: data.id, username: data.username, display_name: data.display_name, is_admin: data.is_admin ?? false };
      } catch {
        this.logout();
      }
    },
  },
});
