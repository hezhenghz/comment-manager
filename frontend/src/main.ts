import { createApp } from 'vue';
import { createPinia } from 'pinia';
import App from './App.vue';
import router from './router';
import './styles/variables.css';
import { useThemeStore } from './stores/theme';

const app = createApp(App);
app.use(createPinia());
app.use(router);
useThemeStore().init();
app.mount('#app');
