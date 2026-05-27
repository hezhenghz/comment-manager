import { createRouter, createWebHistory } from 'vue-router';
import { useAuthStore } from '../stores/auth';

const routes = [
  { path: '/login', component: () => import('../components/Login.vue'), meta: { public: true } },
  {
    path: '/',
    component: () => import('../components/layout/AppShell.vue'),
    children: [
      { path: '', redirect: '/dashboard' },
      { path: 'dashboard', component: () => import('../components/dashboard/Dashboard.vue') },
      { path: 'comments', component: () => import('../components/comments/CommentTable.vue') },
      { path: 'bugs', component: () => import('../components/comments/CommentTable.vue'), props: { fixedCategory: 'bug' } },
      { path: 'suggestions', component: () => import('../components/comments/CommentTable.vue'), props: { fixedCategory: 'suggestion' } },
      { path: 'games', component: () => import('../components/games/GameList.vue'), meta: { adminOnly: true } },
      { path: 'topics', component: () => import('../components/topics/TopicList.vue') },
      { path: 'requirements', component: () => import('../components/requirements/RequirementsBoard.vue') },
      { path: 'chat', component: () => import('../components/chat/GameChat.vue') },
    ],
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

router.beforeEach(async (to, _from, next) => {
  const token = localStorage.getItem('token');
  if (!to.meta.public && !token) {
    next('/login');
    return;
  }
  if (to.path === '/login' && token) {
    next('/dashboard');
    return;
  }
  if (to.meta.adminOnly) {
    const auth = useAuthStore();
    if (!auth.user) await auth.fetchMe();
    if (!auth.user?.is_admin) { next('/dashboard'); return; }
  }
  next();
});

export default router;
