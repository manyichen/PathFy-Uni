# 岗位工作环境画像导入契约

管理员可在“图谱管理 → 更新图谱 → 岗位工作环境画像导入”上传 UTF-8 CSV。任务只生成待复核变更集，确认前不会写入 Neo4j。

必需列：

- `target_type`：`job` 或 `job_title`；
- `target_id`：`Job.job_key` 或 `JobTitle.name`；
- `workstyle_interaction`、`workstyle_abstraction`、`workstyle_analytical`、`workstyle_structure`：0～100，可留空；
- 对应的 `workstyle_conf_interaction`、`workstyle_conf_abstraction`、`workstyle_conf_analytical`、`workstyle_conf_structure`：0～1；
- `workstyle_source`：稳定来源标识；
- `workstyle_scoring_version`：评分规则版本；
- `workstyle_evidence_json`：按内部轴组织的 JSON 对象。

证据示例：

```json
{
  "interaction_intensity": [
    {"text": "每周参与客户访谈与跨团队评审", "source": "job_description"}
  ],
  "structure_preference": [
    {"text": "按双周里程碑推进并完成合规检查", "source": "job_description"}
  ]
}
```

规则：每个填写数值的轴必须同时填写置信度，并在 JSON 中提供至少一条证据。缺少证据、目标不存在、重复目标或数值越界时，整个任务会在规划阶段失败。系统至少需要两个有证据轴且平均有效置信度达到阈值，才会在匹配页显示偏好适配分。
