import { fileURLToPath } from 'node:url'

export default defineNuxtConfig({
  extends: [fileURLToPath(new URL('../../', import.meta.url))],
  ssr: true,
  routeRules: {
    '/': { prerender: true },
    '/login': { prerender: true },
    '/register': { prerender: true },
    '/account/**': { ssr: false },
    '/profile/**': { ssr: false },
    '/personality/**': { ssr: false },
    '/jobs/**': { ssr: false },
    '/match/**': { ssr: false },
    '/report/**': { ssr: false },
    '/graph/**': { ssr: false },
    '/graph-admin/**': { ssr: false }
  },
  nitro: {
    prerender: {
      crawlLinks: false,
      routes: ['/', '/login', '/register']
    }
  }
})
