# 系统设计

## 分支状态

下一阶段优化在 `dev` 分支开发，`main` 保留已完成的首版全栈原型。

## 分层

1. Vue3 展示层：八个业务页面、统一异步状态、Element Plus 和 ECharts。
2. FastAPI 接口层：保留旧接口并提供知识库、RAG、Agent、级联检测、IPJG、纠偏和报告 API。
3. 规则服务层：TF-IDF、RAS/GIS/DualRisk、反事实、TrustScore、Zero-Trust Claim Envelope。
4. 本地数据层：6 个 JSON 案例、运行时知识库和结构化报告。

## 核心闭环

`Evidence → Retrieval → Poison Detection → Counterfactual → Claim DAG → IPJG → Isolation → BFT Consensus → Regeneration`

## 风险分类

- `normal`：当前未达到风险阈值。
- `poison_suspect`：双条件风险高且不存在良性错误标签，进入反事实和隔离流程。
- `benign_error`：过时、歧义或普通事实错误，保留提示但不按恶意知识投毒处置。

该分类用于避免“所有错误信息都是攻击”的错误假设。MVP 的良性标签来自受控案例元数据，未来可使用
时效性模型、来源变更记录和人工审核替代。

## Zero-Trust Claim Envelope

每条 Claim 必须通过身份、角色权限、Evidence 存在性、父 Claim 存在性和签名状态检查。

## Claim DAG 与 IPJG

Claim DAG 展示 Agent、Claim 和 Evidence 的输出、引用与派生关系。IPJG 增加 Consensus 和 Action 层，
支持从最终动作反向追踪污染 Evidence。前端图谱显示有向边、边类型、风险配色和邻接高亮。

## Evidence-backed BFT

```text
Weight(claim) = TrustScore(evidence) × Support(claim, evidence) × (1 - BSS(agent))
```

## 可替换能力

MVP 使用确定性规则，后续可替换为 BERT/BGE、NLI 模型、GAT、Milvus、Neo4j 和约束式大模型生成，
同时保持现有 API 和数据模型兼容。

## 结果边界

所有指标来自本地小规模模拟案例和固定规则仿真，不是公开数据集成绩，也不能证明真实环境泛化能力。

