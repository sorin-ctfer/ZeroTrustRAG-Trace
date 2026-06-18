# RAG 工程参考融合开发审计记录

审计日期：2026-06-16

## 参考资料读取情况

- 博客园文章 `AI大模型应用开发入门-LangChain开发RAG增强检索生成` 可访问，核心流程包含文档加载、RecursiveCharacterTextSplitter 切分、向量库相似度检索、上下文拼接、LLM 生成、LangGraph 状态编排和 checkpoint。
- 知乎链接当前无法直接读取，本地备份 `docs/references/zhihu_rag_reference.md` 不存在。
- 本次融合只吸收工程思想，不照搬文章代码、OpenAI 模型名、API Key、PGVector 连接串或数据库密码。

## 当前已存在页面

- `/external-knowledge`：外部可信知识库导入、Chunk 列表、统计和索引重建。
- `/poison-samples`：本地防御演示投毒样本创建、启停、删除和内置样例加载。
- `/interactive-rag-lab`：AI 交互实验室，支持投毒前问答、session 投毒注入、投毒后问答、Top-K 展示和检测。
- `/interactive-correction/:session_id`：交互式可信纠偏页面，支持四路反事实、session 内隔离、可信重生成和报告展示。
- `/rag-training`：RAG 检测模型训练评测页面，支持数据集导入、内置 PoisonBench、训练指标和预测。

## 当前已存在后端接口

- `/api/external-knowledge/*`：可信文档上传、JSONL clean_chunks 导入、内置样例加载、Chunk 列表、统计、索引重建和清空。
- `/api/poison-samples/*`：投毒样本创建、内置样例加载、列表、启停、删除和注入 session。
- `/api/interactive/session/*`：session 创建、读取、注入样本、Top-K 和风险摘要。
- `/api/interactive/rag/chat`：交互式 RAG 问答。
- `/api/interactive/rag/chat-detect`：投毒检测。
- `/api/interactive/correction/*`：纠偏详情、四路反事实、隔离、可信重生成和报告。
- `/api/training/rag-detector/*`：训练、状态、指标、评估和预测。
- `/api/datasets/*`：数据集导入、内置样例加载、列表、统计、样本和重置。

## 当前已存在服务文件

- `backend/app/services/external_knowledge.py`：存在。负责文档解析、切分、可信 Chunk 存储、TF-IDF 索引和检索。
- `backend/app/services/poison_samples.py`：存在。项目中实际文件名不是 `poison_samples_service.py`，负责本地投毒样本库。
- `backend/app/services/vector_index_service.py`：不存在。当前检索逻辑分散在 `external_knowledge.py` 和 `interactive_rag_service.py`。
- `backend/app/services/rag_workflow_service.py`：不存在。当前工作流由 `interactive_rag_service.py`、`interactive_poison_detector.py` 和 `interactive_correction_service.py` 分段承载。
- `backend/app/services/interactive_rag_service.py`：存在。负责 session 创建、投毒样本注入、投毒前后检索、百炼问答和本地模板 fallback。
- `backend/app/services/rag_detector_training.py`：存在。项目中实际文件名不是 `rag_detector_training_service.py`，负责数据集导入、训练、预测和训练模型 fallback。
- `backend/app/services/rag_experiment_runner.py`：不存在。当前实验运行逻辑主要在 `experiments/run_report_experiments.py`。

## 已吸收的 RAG 工程思想

- 文档加载：外部知识库支持 txt、md、pdf、docx、jsonl clean_chunks，旧版知识库支持 txt/md。
- 文档切分：`external_knowledge.py` 已按段落、中文标点和固定长度做本地切分。
- 向量化或 TF-IDF 检索：当前使用 scikit-learn TF-IDF 与余弦相似度；尚未抽象为统一索引服务。
- Top-K 检索：交互式问答和外部知识库检索均返回排序后的 Top-K。
- 构造上下文：`interactive_rag_service.py` 将 Top-K Chunk 拼接为带 rank、chunk_id、source 的检索上下文。
- LLM 生成：优先调用阿里云百炼兼容接口，失败时使用本地证据模板 fallback。
- 状态流程：已有 session 状态文件记录投毒前回答、投毒后回答、Top-K、检测、纠偏和隔离 Chunk。
- 检测与纠偏闭环：已有 RAS/GIS/DualRisk 检测、训练模型 fallback、四路反事实、session 内隔离、重检索、可信重生成和 JSON 报告。

## 当前缺口

- 缺少独立 `vector_index_service.py`，FAISS/TF-IDF fallback、临时 session 索引、检索模式和 fallback 状态尚未统一输出。
- 缺少独立 `rag_workflow_service.py`，安全 RAG 工作流节点、输入输出、trace 和报告结构尚未集中编排。
- `external_knowledge.py` 的切分默认值仍偏旧，需更贴近 RecursiveCharacterTextSplitter 思想：默认 `chunk_size=500`、`chunk_overlap=80`，优先标题和段落，过长段落再句子或固定长度切分。
- AI 交互实验室页面仍包含直接“一键纠偏”操作，不符合“实验室只检测并跳转纠偏页”的分层要求。
- AI 交互实验室右侧检索面板、聊天气泡、引用折叠卡片、风险 timeline 和 session 状态卡片还需要增强。
- 纠偏页面需要明确在没有 `detection_result` 时提示“请先在 AI 交互实验室执行投毒检测。”。
- README 和 docs 需要补充“普通 RAG 工程流程如何映射为安全 RAG 工作流”的说明，并明确 PGVector 只是可选扩展。
- 测试缺少 `test_vector_index_service.py`、`test_rag_workflow_service.py` 和 `test_reference_integration_docs.py`，需要补齐文档、fallback、session 隔离和页面分层相关断言。
