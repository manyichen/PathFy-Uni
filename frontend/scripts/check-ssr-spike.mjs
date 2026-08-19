import { readFile } from 'node:fs/promises'
import { join, resolve } from 'node:path'

const root = resolve(import.meta.dirname, '..')
const publicDir = join(root, 'experiments', 'ssr-spike', '.output', 'public')
const expectations = [
  ['index.html', '职业规划智能体'],
  [join('login', 'index.html'), '登录'],
  [join('register', 'index.html'), '注册']
]

for (const [file, expected] of expectations) {
  const html = await readFile(join(publicDir, file), 'utf8')
  if (!html.includes(expected)) throw new Error(`${file} does not contain server-rendered text: ${expected}`)
  if (file === 'index.html' && /zrender|echarts/i.test(html)) throw new Error('SSR homepage unexpectedly contains ECharts')
}

console.log('SSR/SSG spike: PASS (home, login and register contain meaningful HTML; homepage excludes ECharts)')
