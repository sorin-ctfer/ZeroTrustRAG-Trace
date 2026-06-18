# 参考文章融合说明

## 可借鉴的工程点

- 文档加载：普通 RAG 通常先加载网页、文件或数据库内容。本项目对应为外部可信知识库导入，并限定为本地防御演示数据。
- 文档切分：参考 RecursiveCharacterTextSplitter 的思想，优先保留标题、段落和语义边界，过长内容再按句子和固定长度切分。
- 向量检索：参考相似度检索思想，本项目提供 FAISS 可选索引；FAISS 不可用或未安装时自动使用 TF-IDF fallback。
- 构造上下文：把 Top-K Chunk 拼接为带 rank、chunk_id、source、trust_label 的上下文，便于回答引用、检测和报告展示。
- 生成回答：交互式模式优先使用阿里云百炼兼容接口，未配置或调用失败时使用本地证据模板 fallback。
- 状态图或流程编排：参考 LangGraph 的状态节点思想，本项目用普通 Python workflow fallback 记录每个安全节点的输入、输出和 trace，不强制安装 LangGraph。

## 本项目没有照搬的部分

- 不照搬 OpenAI 模型名。
- 不照搬 PGVector 连接串、数据库用户名或数据库密码。
- 不强制切换 PGVector；PGVector 仅作为未来部署可选扩展。
- 不复制任何 API Key。
- 不连接真实投毒网站，不采集、不修改、不污染任何在线系统。
- 不把普通 RAG 示例代码直接复制进项目。

## 本项目的安全增强点

- 可信知识库和投毒样本库物理隔离。
- session 级投毒注入，不污染全局可信知识库。
- RAS/GIS/DualRisk 检测。
- 训练模型 fallback：有训练模型时优先训练模型模式，没有模型时使用规则模式。
- 四路反事实验证：original、remove、solo、replace。
- session 内隔离高风险 Chunk，不删除 `poison_samples.json` 或 `external_trusted_chunks.json`。
- 可信重生成与隔离后重检索。
- TrustScore 前后对比。
- JSON 风险报告。
