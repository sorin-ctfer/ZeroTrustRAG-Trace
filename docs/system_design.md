# 系统设计

## 分层

1. Vue3 展示层：八个业务页面、Element Plus 表格表单、ECharts 图谱。
2. FastAPI 接口层：知识库、RAG、Agent、级联检测、IPJG、纠偏和报告 API。
3. 规则服务层：TF-IDF、RAS/GIS/DualRisk、反事实、TrustScore、Zero-Trust Claim Envelope。
4. 本地数据层：JSON 案例、运行时知识库和结构化报告。

## 核心闭环

`Evidence → Retrieval → Poison Detection → Counterfactual → Claim DAG → IPJG → Isolation → BFT Consensus → Regeneration`

## Zero-Trust Claim Envelope

每条 Claim 必须通过身份、角色权限、Evidence 存在性、父 Claim 存在性和签名状态检查。

## Evidence-backed BFT

```text
Weight(claim) = TrustScore(evidence) × Support(claim, evidence) × (1 - BSS(agent))
```

MVP 使用确定性规则，后续可替换为 BERT/NLI、GAT、Milvus、Neo4j 和约束式大模型生成。

