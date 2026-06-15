# API

| Method | Path | Description |
|---|---|---|
| GET | `/api/health` | 健康检查 |
| GET | `/api/dashboard/stats` | 仪表盘统计 |
| POST | `/api/knowledge/upload` | 上传 txt/md |
| GET | `/api/knowledge/list` | Evidence 列表 |
| POST | `/api/knowledge/load-demo` | 加载样例 |
| POST | `/api/knowledge/clear` | 清空知识库 |
| POST | `/api/knowledge/add-poison` | 添加本地模拟投毒样本 |
| POST | `/api/rag/analyze` | 完整 RAG 投毒分析 |
| GET | `/api/rag/cases` | 演示案例 |
| GET | `/api/rag/cases/{case_id}` | 案例详情 |
| POST | `/api/agents/run-demo` | 六 Agent 演示 |
| GET | `/api/agents/claims` | Claim 列表 |
| GET | `/api/agents/graph` | Agent 图谱 |
| POST | `/api/detect/cascade` | 级联检测 |
| POST | `/api/detect/poison` | 知识投毒检测 |
| POST | `/api/trace/ipjg` | IPJG 溯源 |
| POST | `/api/correction/run` | 可信纠偏 |
| GET | `/api/report/{case_id}` | 风险报告 |

完整字段可通过启动后的 Swagger 查看。

