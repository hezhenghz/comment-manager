// 物品品质 → 颜色映射（仿游戏内品质配色）
// rank: 1普通 2精良 3上乘 4传说 5绝世；0/未知回退灰色
const QUALITY_COLORS: Record<number, string> = {
  1: '#8BC34A', // 普通 绿
  2: '#03A9F4', // 精良 蓝
  3: '#9C27B0', // 上乘 紫
  4: '#FF9800', // 传说 橙
  5: '#E53935', // 绝世 红
};

export function qualityColor(rank: number | undefined): string {
  return QUALITY_COLORS[rank ?? 0] ?? '#9ca3af';
}
