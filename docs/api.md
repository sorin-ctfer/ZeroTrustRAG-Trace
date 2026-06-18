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
| POST | `/api/external-knowledge/upload` | 上传 txt/md/pdf/docx 到外部可信知识库 |
| POST | `/api/external-knowledge/import-dataset-clean` | 导入 JSONL 中的 clean_chunks |
| POST | `/api/external-knowledge/load-demo` | 加载内置可信制度样例 |
| GET | `/api/external-knowledge/chunks` | 外部可信 Chunk 列表 |
| GET | `/api/external-knowledge/stats` | 外部知识库统计 |
| POST | `/api/external-knowledge/rebuild-index` | 重建本地检索索引 |
| POST | `/api/external-knowledge/clear` | 清空外部可信知识库 |
| POST | `/api/poison-samples/create` | 创建本地防御演示投毒样本 |
| POST | `/api/poison-samples/load-demo` | 加载内置 PoisonBench 样本 |
| GET | `/api/poison-samples/list` | 投毒样本列表 |
| POST | `/api/poison-samples/{sample_id}/enable` | 启用投毒样本 |
| POST | `/api/poison-samples/{sample_id}/disable` | 禁用投毒样本 |
| DELETE | `/api/poison-samples/{sample_id}` | 删除投毒样本 |
| POST | `/api/poison-samples/inject-to-session` | 将样本注入指定 session |
| POST | `/api/datasets/import` | 导入训练 JSONL 数据集 |
| GET | `/api/datasets/list` | 数据集列表 |
| GET | `/api/datasets/stats` | 数据集统计 |
| GET | `/api/datasets/samples` | 训练样本预览 |
| POST | `/api/datasets/reset` | 清空训练数据 |
| GET | `/api/datasets/public/sources` | 查看可接入的公开数据集源 |
| POST | `/api/datasets/public/download` | 下载公开数据集原始文件到本地运行目录 |
| POST | `/api/datasets/public/convert` | 转换公开数据集为项目 JSONL |
| POST | `/api/datasets/public/import-training` | 转换并导入训练集 |
| POST | `/api/datasets/public/import-clean-knowledge` | 将公开数据集 clean_chunks 导入外部可信知识库 |
| POST | `/api/training/rag-detector/train` | 训练 RAG 投毒检测模型 |
| GET | `/api/training/rag-detector/status` | 训练状态和当前检测模式 |
| GET | `/api/training/rag-detector/metrics` | 验证集真实指标 |
| POST | `/api/training/rag-detector/evaluate` | 评估 JSONL 数据集 |
| POST | `/api/training/rag-detector/predict` | 使用训练模型预测文本风险 |
| POST | `/api/interactive/session/create` | 创建交互式实验 session |
| GET | `/api/interactive/session/{session_id}` | 获取 session 详情 |
| POST | `/api/interactive/session/{session_id}/inject-poison` | 注入投毒样本到当前 session |
| GET | `/api/interactive/session/{session_id}/topk` | 获取投毒前后 Top-K |
| GET | `/api/interactive/session/{session_id}/risk-summary` | 获取实验状态栏摘要 |
| POST | `/api/interactive/rag/chat` | 交互式 RAG 问答 |
| POST | `/api/interactive/rag/chat-detect` | 交互式投毒检测 |
| GET | `/api/interactive/report/{session_id}` | 交互式检测报告 |
| GET | `/api/interactive/correction/{session_id}/detail` | 纠偏页面详情 |
| POST | `/api/interactive/correction/{session_id}/counterfactual` | 四路反事实验证 |
| POST | `/api/interactive/correction/{session_id}/quarantine` | session 内隔离高风险 Chunk |
| POST | `/api/interactive/correction/{session_id}/regenerate` | 可信重生成 |
| GET | `/api/interactive/correction/{session_id}/report` | 纠偏报告 |

## RAG 分析

`POST /api/rag/analyze`

请求字段：

- `case_id`：已有案例 ID，或留空后使用当前知识库。
- `query`：用户问题。
- `original_answer`：待检测的 RAG 原始回答。
- `top_k`：检索深度。

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
`/api/graph`、`/api/trust`、`/api/regenerate`、`/api/interactive/knowledge/*`、
`/api/interactive/correction/quarantine`、`/api/interactive/correction/regenerate` 未删除。

## 交互式闭环

可信知识统一写入 `external_trusted_chunks.json`；投毒样本写入 `poison_samples.json`，只有注入指定
session 后才参与问答；session 过程写入 `interactive_sessions.json`。

```json
POST /api/interactive/session/create
```

```json
POST /api/interactive/session/{session_id}/inject-poison
{"sample_id": "POISON-xxxx"}
```

```json
POST /api/interactive/rag/chat
{"session_id": "SESSION-xxxx", "stage": "before_poison", "question": "生产系统权限变更是否需要主管审批？"}
```

`stage=before_poison` 只检索外部可信知识；`stage=after_poison` 检索外部可信知识加当前 session 注入的
poison chunks；纠偏后检索外部可信知识和未隔离的低风险 session chunks。

## 训练评测

训练接口使用 scikit-learn，不依赖 torch/transformers。公开数据集接入当前支持 SafeRAG NCTD 和 RGB zh_fact：转换器只使用原始数据中的问题、可信证据、冲突证据、错误目标或正确答案字段，不合成模板化问题，不在代码中写死样本内容。指标来自验证集真实计算，不写死或伪造。
训练模型保存到 `backend/app/data/model_artifacts/`。没有模型时检测接口返回规则模式；模型存在时优先使用训练模型概率。

API Key 只从环境变量或 `backend/.env` 读取。所有投毒样本仅用于本地防御演示，不连接、不修改、不攻击任何真实在线系统。
