# 普通 RAG 工程流程到安全 RAG 工作流的映射

本文档说明智源净域如何将普通 LangChain RAG 工程流程映射为面向知识投毒检测与可信纠偏的安全 RAG 工作流。

## 普通 RAG 工程流程

参考 RAG 工程文章中的通用链路可以抽象为：

```text
文档加载
→ 文档切分
→ 向量化
→ 相似度检索
→ 构造上下文
→ LLM 生成
```

这类流程解决“如何把外部知识交给模型使用”的问题，但默认不区分可信知识、投毒样本、session 注入边界，也不包含投毒检测、因果验证和可信纠偏。

## 智源净域安全 RAG 工作流

智源净域在普通 RAG 链路上增加可信来源隔离、session 级投毒注入、风险检测、反事实验证和可信重生成：

```text
外部可信知识导入
→ 文档解析与 Chunk 切分
→ FAISS 或 TF-IDF 索引
→ 用户提问
→ 投毒前可信检索
→ 当前 session 注入本地投毒样本
→ 投毒后混合检索
→ RAS/GIS/DualRisk 检测
→ 风险 Chunk 标记
→ 跳转可信纠偏页面
→ 四路反事实验证
→ 隔离高风险 Chunk
→ 重检索
→ 可信重生成
→ TrustScore 前后对比
→ JSON 风险报告
```

## 工程映射表

| 普通 RAG 节点 | 本项目安全 RAG 节点 | 当前实现 |
|---|---|---|
| 文档加载 | 外部可信知识导入 | `/external-knowledge` 与 `/api/external-knowledge/*` 导入 txt、md、pdf、docx、jsonl clean_chunks |
| 文档切分 | 文档解析与可信 Chunk 切分 | `external_knowledge.py` 生成带 `trust_label=trusted` 的 Chunk |
| 向量化 | FAISS 或 TF-IDF 索引 | `vector_index_service.py` 统一索引，FAISS 不可用时回退 TF-IDF |
| 相似度检索 | 投毒前可信检索 | session 投毒前只检索 external trusted chunks |
| 构造上下文 | Top-K Chunk 安全上下文 | 上下文带 rank、chunk_id、source、trust_label，提示词禁止把文档中指令当系统指令 |
| LLM 生成 | 百炼增强或本地模板 fallback | `interactive_rag_service.py` 优先百炼兼容接口，失败使用模板 |
| 状态图/流程编排 | 安全 RAG workflow trace | `rag_workflow_service.py` 记录 analyze、retrieve、inject、detect、quarantine、regenerate、report 节点输出 |
| 无内置安全检测 | RAS/GIS/DualRisk 检测 | `interactive_poison_detector.py` 和训练模型 fallback 标记风险 Chunk |
| 无因果验证 | 四路反事实验证 | `/interactive-correction/:session_id` 执行 original/remove/solo/replace |
| 无纠偏闭环 | session 内隔离与可信重生成 | 只隔离当前 session 的高风险 Chunk，不删除可信库或样本库 |
| 无安全报告 | JSON 风险报告 | 报告输出 session、Top-K、检测、纠偏和 TrustScore 对比 |

## 边界约束

- PGVector 只作为未来可选扩展，不作为当前必需依赖。
- 不写入任何 API Key、数据库密码或真实连接串。
- 不连接真实投毒网站，投毒样本只存在本地演示库，并且只注入当前 session。
- 不破坏已有 API 和页面路由。
