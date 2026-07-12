export default defineNuxtConfig({
  compatibilityDate: '2026-07-12',
  devtools: { enabled: false },
  ssr: false,
  modules: ['@nuxt/ui'],
  fonts: { provider: 'local' },
  css: ['~/assets/css/main.css'],
  runtimeConfig: {
    public: {
      apiBase: process.env.NUXT_PUBLIC_API_BASE ?? process.env.PUBLIC_API_BASE ?? ''
    }
  },
  app: {
    head: {
      htmlAttrs: { lang: 'zh-CN' },
      titleTemplate: '%s · PathFy',
      meta: [{ name: 'description', content: '基于 AI 的大学生职业规划智能体' }],
      link: [{ rel: 'icon', type: 'image/svg+xml', href: '/favicon.svg' }]
    }
  },
  vite: {
    server: {
      proxy: {
        '/api': {
          target: process.env.FLASK_BACKEND ?? 'http://127.0.0.1:5000',
          changeOrigin: true
        }
      }
    }
  },
  nitro: {
    prerender: {
      routes: ['/']
    }
  },
  typescript: { strict: true, typeCheck: true }
})
