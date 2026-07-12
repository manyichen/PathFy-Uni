# Git 历史隐私净化运行手册

本操作不在普通功能分支中执行。只有当前清理分支合并、团队确认停写并完成远端镜像备份后，才由仓库管理员执行。

## 前置条件

1. 通知所有协作者暂停 push，并记录远端默认分支 commit。
2. 创建带日期的 mirror clone，验证备份包含所有分支和标签。
3. 安装并记录 `git-filter-repo` 版本。
4. 将待删除路径清单交叉复核，尤其确认没有仍需保留的策展 CSV。

## 历史删除范围

- `backend/app/static/uploads/`
- `datasets/snapshots/neo4j_graph_full.json`
- `datasets/20260226105856_457.xls`
- `tools/job_eval/job_eval_results_*.jsonl`
- `tools/job_eval/IMG_20260110_143640.jpg`

对通配文件先生成历史中精确路径清单，再把路径逐项传给 `git filter-repo --invert-paths`。不要直接复制未经审查的宽泛 glob。

## 验证与发布

1. 用 `git log --all -- <path>` 验证目标路径无历史记录。
2. 用 `git rev-list --objects --all` 检查实名文件名和大对象不再可达。
3. 运行 `git fsck --full`，比较清理前后的对象体积。
4. 在镜像备份仍可恢复的前提下，强制更新受影响的远端分支和标签。
5. 要求所有协作者重新克隆；不要把旧分支 merge 回新历史。

若任何验证失败，停止发布并从只读 mirror 备份恢复。备份的访问权限应与敏感数据级别一致，确认无保留义务后再安全销毁。
