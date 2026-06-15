# API

后端默认地址为 `http://127.0.0.1:8000`，Swagger 位于 `/docs`。已有旧版接口继续保留，
下表为 Web 原型使用的接口。

| Method | Path | Description |
|---|---|---|
| GET | `/api/health` | 健康检查和版本 |
| GET | `/api/dashboard/stats` | Evidence、Chunk、Agent、Claim 和 TrustScore 统计 |
| POST | `/api/knowledge/upload` | Multipart 上传 UTF-8 txt/md 并切分 Chunk |
| GET | `/api/knowledge/list` | Evidence 列表 |
| POST | `/api/knowledge/load-demo` | 加载全部内置案例 Evidence |
| POST | `/api/knowledge/clear` | 清空运行时知识库 |
| POST | `/api/knowledge/add-poison` | 添加本地模拟投毒样本 |
| POST | `/api/rag/analyze` | Top-K、RAS/GIS/DualRisk、反事实和 TrustScore |
| GET | `/api/rag/cases` | 演示案例摘要 |
| GET | `/api/rag/cases/{case_id}` | 案例详情 |
| POST | `/api/agents/run-demo` | 六 Agent 和 Zero-Trust Claim Envelope |
| GET | `/api/agents/claims` | 最近一次 Claim 列表 |
| GET | `/api/agents/graph` | 最近一次 Agent/Claim/Evidence 图谱 |
| POST | `/api/detect/cascade` | 级联错误与 Byzantine 指标 |
| POST | `/api/detect/poison` | 兼容式知识投毒检测入口 |
| POST | `/api/trace/ipjg` | 四层 IPJG 联合溯源 |
| POST | `/api/correction/run` | 隔离、降权、回滚、BFT 共识和可信重生成 |
| GET | `/api/report/{case_id}` | 获取或自动生成结构化风险报告 |

## RAG 分析

```json
POST /api/rag/analyze
{
  "case_id": "case_vulnerability_status_poisoning",
  "query": "CVE-2026-41001 是否已经修复？",
  "original_answer": "漏洞已经修复，无需升级。",
  "top_k": 5
}
```

返回中的 `risk_category` 为 `normal`、`poison_suspect` 或 `benign_error`；
`benign_error_evidence` 用于展示普通过时信息，不进入恶意投毒隔离集合。

## Agent 与级联检测

```json
POST /api/agents/run-demo
{"case_id": "case_threat_intel_false_consensus"}
```

```json
POST /api/detect/cascade
{"case_id": "case_threat_intel_false_consensus"}
```

级联结果包含 Propagation Factor、False Consensus Rate、Drift Velocity、Influence Score 和 BSS。

## 纠偏与报告

```json
POST /api/correction/run
{"case_id": "case_security_certification_poisoning"}
```

```text
GET /api/report/case_security_certification_poisoning
```

完整模型和错误响应以 Swagger 为准。旧版 `/api/search`、`/api/detect`、`/api/counterfactual`、
`/api/graph`、`/api/trust` 和 `/api/regenerate` 未删除。

