import { defineStore } from 'pinia';

export interface ThemeItem {
  key: string;
  name: string;
  dot: string;
}

export const THEMES: ThemeItem[] = [
  { key: 'classic', name: '经典黑紫蓝', dot: '#6366f1' },
  { key: 'steam', name: 'Steam', dot: '#66c0f4' },
  { key: 'zhihu', name: '知乎蓝', dot: '#0084ff' },
  { key: 'douban', name: '豆瓣绿', dot: '#2e8b57' },
];

const STORAGE_KEY = 'theme';

function applyTheme(key: string) {
  if (key === 'classic') {
    delete document.documentElement.dataset.theme;
  } else {
    document.documentElement.dataset.theme = key;
  }
}

export const useThemeStore = defineStore('theme', {
  state: () => ({
    THEMES,
    current: localStorage.getItem(STORAGE_KEY) || 'classic',
  }),
  actions: {
    setTheme(key: string) {
      this.current = key;
      localStorage.setItem(STORAGE_KEY, key);
      applyTheme(key);
    },
    init() {
      applyTheme(this.current);
    },
  },
});
