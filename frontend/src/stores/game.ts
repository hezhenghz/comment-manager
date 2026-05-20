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
      this.games = data;
    },
    select(id: string | null) {
      this.selectedGameId = id;
    },
  },
});
