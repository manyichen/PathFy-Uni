export interface HeaderNavItem {
  label: string
  to: string
  icon: string
  active?: boolean
}

export const userHeaderNavigation: HeaderNavItem[] = [
  { label: '首页', to: '/', icon: 'i-lucide-house' },
  { label: '岗位探索', to: '/jobs', icon: 'i-lucide-briefcase-business' },
  { label: '能力画像', to: '/profile', icon: 'i-lucide-radar' },
  { label: '人岗匹配', to: '/match', icon: 'i-lucide-target' },
  { label: '职业图谱', to: '/graph', icon: 'i-lucide-network' },
  { label: '生涯报告', to: '/report', icon: 'i-lucide-file-text' },
  { label: '性格测试', to: '/personality', icon: 'i-lucide-brain' }
]

export const adminHeaderNavigation: HeaderNavItem[] = [
  { label: '图谱管理', to: '/graph-admin', icon: 'i-lucide-database' },
  { label: '系统设置', to: '/graph-admin/settings', icon: 'i-lucide-settings' }
]

export function isHeaderNavActive(path: string, target: string): boolean {
  if (target === '/') return path === '/'
  if (target === '/graph-admin') return path === target || (path.startsWith('/graph-admin/') && !path.startsWith('/graph-admin/settings'))
  return path === target || path.startsWith(`${target}/`)
}
