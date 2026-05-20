import { defineStore } from 'pinia';
import api from '../api';

export interface DashboardStats {
  total_comments: number;
  today_new: number;
  bug_count: number;
  today_bug_count: number;
  suggestion_count: number;
  today_suggestion_count: number;
  negative_review_rate: number | null;
}

export const useDashboardStore = defineStore('dashboard', {
  state: () => ({
    stats: { total_comments: 0, today_new: 0, bug_count: 0, today_bug_count: 0, suggestion_count: 0, today_suggestion_count: 0, negative_review_rate: null } as DashboardStats,
    categories: [] as any[],
    sources: [] as any[],
  }),
  actions: {
    async loadAll(gameId?: string | null) {
      const params: any = {};
      if (gameId) params.game_id = gameId;

      const [stats, categories, sources] = await Promise.allSettled([
        api.get('/dashboard/stats', { params }),
        api.get('/dashboard/categories', { params }),
        api.get('/dashboard/sources', { params }),
      ]);

      if (stats.status      === 'fulfilled') this.stats      = stats.value.data;
      if (categories.status === 'fulfilled') this.categories = categories.value.data;
      if (sources.status    === 'fulfilled') this.sources    = sources.value.data;
    },
  },
});
