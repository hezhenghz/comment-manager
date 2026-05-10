import { defineStore } from 'pinia';
import api from '../api';

export const useCommentsStore = defineStore('comments', {
  state: () => ({
    items: [] as any[],
    total: 0,
    page: 1,
    pageSize: 20,
    loading: false,
    searchQuery: '',
  }),
  actions: {
    async search(q: string, page = 1) {
      this.loading = true;
      this.searchQuery = q;
      try {
        const { data } = await api.get('/search', { params: { q, page, page_size: this.pageSize } });
        this.items = data.items;
        this.total = data.total;
        this.page = data.page;
      } finally {
        this.loading = false;
      }
    },
    async loadComments(params: any = {}) {
      this.loading = true;
      try {
        const { data } = await api.get('/comments', { params: { ...params, page: this.page, page_size: this.pageSize } });
        this.items = data.items;
        this.total = data.total;
        this.page = data.page;
      } finally {
        this.loading = false;
      }
    },
  },
});
