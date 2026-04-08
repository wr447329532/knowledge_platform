import { createRouter, createWebHashHistory } from 'vue-router'

const routes = [
  { path: '/login', name: 'Login', component: () => import('../views/Login.vue'), meta: { public: true } },
  { path: '/', name: 'Home', component: () => import('../views/Home.vue') },
  { path: '/preview', name: 'Preview', component: () => import('../views/Preview.vue') },
  { path: '/admin', name: 'Admin', component: () => import('../views/Admin.vue') },
  { path: '/account', name: 'Account', component: () => import('../views/Account.vue') },
]

const router = createRouter({ history: createWebHashHistory(), routes })

router.beforeEach((to, _from, next) => {
  // 同时支持「记住登录」（localStorage）和「仅本次会话」（sessionStorage）
  const token =
    (typeof window !== 'undefined' && window.sessionStorage.getItem('token')) ||
    (typeof window !== 'undefined' && window.localStorage.getItem('token'))

  // 已登录仍打开登录页（含浏览器返回）：直接进首页，不堆叠历史
  if (to.path === '/login' && token) {
    return next({ path: '/', replace: true })
  }
  if (to.meta.public || token) return next()
  next({ path: '/login' })
})

export default router
