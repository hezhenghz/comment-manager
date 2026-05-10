import { defineStore } from 'pinia';
import api from '../api';

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: null as { id: string; username: string; display_name: string } | null,
  }),
  actions: {
    async login(username: string, password: string) {
      const { data } = await api.post('/auth/login', { username, password });
      localStorage.setItem('token', data.access_token);
      this.user = { id: '', username, display_name: data.display_name };
    },
    logout() {
      localStorage.removeItem('token');
      this.user = null;
    },
    async fetchMe() {
      try {
        const { data } = await api.get('/auth/me');
        this.user = data;
      } catch {
        this.logout();
      }
    },
  },
});
