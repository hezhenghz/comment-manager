import { defineStore } from 'pinia';
import api from '../api';

export const useGameStore = defineStore('game', {
  state: () => ({
    games: [] as any[],
    selectedGameId: null as string | null,
  }),
  actions: {
    async loadGames() {
      const { data } = await api.get('/games');
      this.games = data;  // 后端已按「默认游戏置顶」排序
      // 存在默认游戏时强制选中它；否则保持当前选择（由调用方兜底选第一个）
      const def = data.find((g: any) => g.is_default);
      if (def) {
        this.selectedGameId = def.id;
      }
    },
    select(id: string | null) {
      this.selectedGameId = id;
    },
  },
});
