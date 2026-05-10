import { createRouter, createWebHistory } from 'vue-router';

const routes = [
  { path: '/login', component: () => import('../components/Login.vue'), meta: { public: true } },
  {
    path: '/',
    component: () => import('../components/layout/AppShell.vue'),
    children: [
      { path: '', redirect: '/dashboard' },
      { path: 'dashboard', component: () => import('../components/dashboard/Dashboard.vue') },
      { path: 'comments', component: () => import('../components/comments/CommentTable.vue') },
      { path: 'reports', component: () => import('../components/reports/ReportList.vue') },
      { path: 'alerts', component: () => import('../components/alerts/AlertRuleList.vue') },
      { path: 'games', component: () => import('../components/games/GameList.vue') },
      { path: 'settings', component: () => import('../components/settings/Settings.vue') },
    ],
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

router.beforeEach((to, _from, next) => {
  const token = localStorage.getItem('token');
  if (!to.meta.public && !token) {
    next('/login');
  } else if (to.path === '/login' && token) {
    next('/dashboard');
  } else {
    next();
  }
});

export default router;
