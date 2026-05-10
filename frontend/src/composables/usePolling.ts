import { onMounted, onUnmounted } from 'vue';

export function usePolling(fn: () => void, intervalMs = 30000) {
  let timer: number | null = null;

  onMounted(() => {
    fn();
    timer = window.setInterval(fn, intervalMs);
  });

  onUnmounted(() => {
    if (timer) clearInterval(timer);
  });
}
