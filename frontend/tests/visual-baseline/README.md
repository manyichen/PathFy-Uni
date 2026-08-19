# 前端视觉基线

该目录保存 Iteration 0 的五个核心页面在三档视口下的全页截图：

- `desktop-1440`：1440 × 900
- `tablet-768`：768 × 1024
- `mobile-390`：390 × 844

重新采集：

```powershell
cd frontend
pnpm test:visual-baseline
```

截图使用固定 Mock 数据、浅色主题、中文区域设置和禁用动画，以降低非业务差异。当前阶段只作为人工回归参考，不纳入普通 `pnpm test:e2e` 和 CI 像素级阻断；后续确认视觉规范稳定后，再引入差异阈值。
