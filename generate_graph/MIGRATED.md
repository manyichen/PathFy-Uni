# generate_graph 已迁移

ETL 功能已迁移至 `backend/app/domains/graph/`，作为 Flask 后端的业务域统一管理。

## 新 API 端点

| 功能 | 原脚本 | 新 API |
|------|--------|--------|
| 岗位导入 | `python script.py` | `POST /api/graph/import-jobs` |
| 晋升边生成 | `python openai_lmstudio_promotion_update.py` | `POST /api/graph/generate-promotions` |
| 图谱统计 | 手动查询 Neo4j | `GET /api/graph/stats` |
| 清空图谱 | `--clear-all` 参数 | `POST /api/graph/clear` |

## 主要变更

- **Neo4j 驱动**：py2neo → 官方 `neo4j` 驱动（与后端统一）
- **LLM 调用**：Gemini / Ollama → 统一为 OpenAI 兼容接口（可切换豆包 / DeepSeek 等）
- **认证**：需要 admin JWT Token（`GRAPH_ADMIN_USER_IDS` 配置管理员）
- **配置**：统一使用 `backend/.env`，新增 `GRAPH_LLM_*` 配置项
- **依赖**：不再需要 `google-genai`、`ollama`、`py2neo`

## 原脚本保留

本目录中的原始脚本和 `.env.example` 保留供参考，不再主动维护。
如需继续使用原脚本，请确保安装 orig-requirements.txt 中的依赖。
