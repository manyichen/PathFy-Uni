export default defineNuxtPlugin(() => {
  useAuth().hydrate()
})
