import { defineStore } from 'pinia';
import api from '../api';

export interface DashboardStats {
  total_comments: number;
  today_new: number;
  bug_count: number;
  negative_ratio: number;
}

export const useDashboardStore = defineStore('dashboard', {
  state: () => ({
    stats: {} as DashboardStats,
    trends: [] as any[],
    categories: [] as any[],
    sources: [] as any[],
    wordcloud: [] as any[],
    games: [] as any[],
    selectedGameId: null as string | null,
  }),
  actions: {
    async loadGames() {
      const { data } = await api.get('/games');
      this.games = data;
    },
    async loadAll(gameId?: string | null) {
      const gid = gameId ?? this.selectedGameId;
      const params: any = {};
      if (gid) params.game_id = gid;
      const [stats, trends, categories, sources, wordcloud] = await Promise.all([
        api.get('/dashboard/stats', { params }),
        api.get('/dashboard/trends', { params }),
        api.get('/dashboard/categories', { params }),
        api.get('/dashboard/sources', { params }),
        api.get('/dashboard/wordcloud', { params }),
      ]);
      this.stats = stats.data;
      this.trends = trends.data;
      this.categories = categories.data;
      this.sources = sources.data;
      this.wordcloud = wordcloud.data;
    },
  },
});
