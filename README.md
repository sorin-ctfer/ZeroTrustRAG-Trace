# 智源净域

> 基于多 Agent 零信任协同与 RAG 知识投毒因果验证的信息污染溯源纠偏系统

> 当前开发分支：`dev`。下一阶段优化只提交到 `dev`，未合并到 `main`。

智源净域是一个可本地运行、可展示、可测试的全栈安全原型。基础闭环使用
TF-IDF、余弦相似度、启发式 NLI、NetworkX 和证据抽取；交互式增强模式默认直接调用百炼大模型，也可切换到本地 Ollama，模型不可用时自动回退到本地证据抽取。
系统已覆盖从外部可信知识导入、投毒样本注入、RAG 投毒检测、Agent 声明验证、级联错误识别、联合溯源到可信纠偏和报告导出的完整闭环。

## 系统架构

```text
Vue3 / Element Plus / ECharts
              │ Axios
              ▼
FastAPI API / Pydantic Models
              │
    ┌─────────┼─────────────┐
    ▼         ▼             ▼
RAG 检测   Agent 零信任   IPJG 联合图谱
    │         │             │
    └─────────┴──────┬──────┘
                     ▼
        隔离 / 回滚 / BFT 共识 / 可信重生成
                     │
                     ▼
              JSON 风险报告
```

## 核心功能

- 知识库上传、文档切分、Evidence/Chunk 管理和数据集驱动的投毒知识样本。
- TF-IDF Top-K 检索和 RAS、GIS、DualRisk 投毒检测。
- 原始、删除可疑、仅可疑、可信替代四路反事实及 CausalScore。
- Planner、Retriever、Threat Intel、Verifier、Decision、Execution 六 Agent。
- Zero-Trust Claim Envelope：身份、权限、Evidence、父 Claim、签名逐项验证。
- Claim Provenance DAG 与 Propagation Factor、False Consensus Rate、Drift Velocity、
  Influence Score、Byzantine Suspicion Score。
- Evidence、Claim、Consensus、Action 四层 IPJG 信息污染联合图谱。
- 高风险 Chunk 隔离、Agent 降权、Claim 回滚和 Evidence-backed BFT Consensus。
- TrustScore 前后对比、可信重生成和结构化 JSON 报告。
- 外部可信知识库、投毒样本库、交互式 session、RAG 检测模型训练评测和本地 Ollama / 百炼兜底增强问答。

## 已完成功能清单

### 本地规则仿真闭环

- 已完成系统仪表盘：以 AI 交互实验室为中心展示可信知识、训练数据、投毒知识、session 风险和检测模式。
- 已完成知识库管理：支持 `.txt` / `.md` 上传、手动添加投毒样本、加载内置样例、清空知识库和 Chunk 列表查看。
- 已完成 RAG 投毒检测：支持内置案例选择、Top-K 检索、RAS/GIS/DualRisk/CausalScore/TrustScore 计算、风险 Chunk 标记和良性错误区分。
- 已完成 Agent 零信任演示：模拟 Planner、Retriever、Threat Intel、Verifier、Decision、Execution 六类 Agent，生成 Claim Envelope 并校验身份、权限、Evidence、父 Claim 和签名。
- 已完成级联错误检测：输出 Claim Provenance DAG、Propagation Factor、False Consensus Rate、Drift Velocity、Influence Score 和 Byzantine Suspicion Score。
- 已完成联合溯源图谱：构建 Evidence、Claim、Consensus、Action 四层 IPJG 图谱，支持风险配色、边类型、拖拽、缩放、箭头和邻接高亮。
- 已完成可信纠偏：支持高风险 Chunk 隔离、Agent 降权、Claim 回滚、Evidence-backed BFT 共识和可信重生成。
- 已完成风险报告：按 AI 交互实验室 session 生成结构化 JSON 报告，支持页面查看、复制和下载。

### 交互式增强闭环

- 已完成外部知识库页面：统一导入 txt、md、pdf、docx、JSONL clean_chunks 和内置可信制度样例，保存到 `backend/app/data/external_trusted_chunks.json`。
- 已完成投毒样本库页面：单独管理从训练数据集生成的投毒知识样本、攻击类型、目标错误答案、正确答案和启用状态，保存到 `backend/app/data/poison_samples.json`。
- 已完成 AI 交互实验室：支持选择公开数据集、导入可信 clean chunks、从 poison/benign_error 样本生成投毒知识、聊天式 RAG 问答、当前 session 投毒样本注入、投毒前后 Top-K 检索展示、风险检测、风险摘要和 session 报告生成。
- 已完成交互式可信纠偏页面：检测到高风险后跳转到 `/interactive-correction/{session_id}`，执行四路反事实、session 内隔离、重检索、可信重生成和 JSON 纠偏报告。
- 已完成 RAG 训练评测页面：支持导入 JSONL、下载并转换 SafeRAG/RGB 公开数据集、重置数据集、查看样本分布，使用 scikit-learn 训练 Logistic Regression 或 Random Forest 检测模型，并展示真实验证集 Precision、Recall、F1、AUC、PR-AUC 和混淆矩阵。
- 已完成训练模式融合：训练模型存在时交互式检测优先使用训练模型；没有模型时自动 fallback 到规则模式，并在风险摘要中展示当前检测模式。
- 已完成百炼 / 本地 Ollama 增强：默认 `LLM_PROVIDER=bailian` 直接调用百炼；需要本地推理时可切换到 `LLM_PROVIDER=ollama` 和 `deepseek-r1:8b` 快速模式；模型不可用时使用检索证据抽取兜底。

### 工程与测试

- 已完成 FastAPI 统一响应包装、CORS 配置、Swagger 文档和前端 Vite `/api` 代理。
- 已完成 Vue3 + TypeScript + Element Plus 多页面前端和 Axios API 封装。
- 已完成后端 pytest 覆盖：旧版 RAG 闭环、Web 平台接口、外部知识库、投毒样本库、交互式 RAG、检测到纠偏链路、训练评测和路由兼容行为。
- 已完成前端生产构建配置：`vue-tsc -b && vite build`。

## 技术栈

| 部分 | 技术 |
|---|---|
| 后端 | Python 3.10+、FastAPI、Pydantic v2、scikit-learn、NetworkX、LangChain Core、pypdf、python-docx |
| 前端 | Vue3、Vite、TypeScript、Element Plus、ECharts、Axios |
| 存储 | 本地 JSON |
| 测试 | pytest、路由 endpoint/Pydantic 兼容测试、vue-tsc、Vite build |

不包含 `torch`、`transformers`，不需要 GPU。

旧版内置案例、本地规则模式、外部知识库、投毒样本库和训练评测不需要 API Key；交互式问答默认使用百炼，切换到 Ollama 时可按本地模型性能调整超时、输出长度和上下文窗口。

## 目录结构

```text
RAGweblab/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── models/
│   │   ├── routers/
│   │   ├── services/
│   │   ├── data/
│   │   └── utils/
│   ├── tests/
│   ├── requirements.txt
│   └── README.md
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   ├── components/
│   │   ├── router/
│   │   └── views/
│   ├── package.json
│   └── README.md
├── docs/
│   ├── system_design.md
│   ├── api.md
│   └── demo_cases.md
├── experiments/
├── README.md
├── docker-compose.yml
└── .gitignore
```

## 后端启动

Linux / macOS：

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Windows PowerShell：

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

访问：

- API：<http://127.0.0.1:8000>
- Swagger：<http://127.0.0.1:8000/docs>
- 健康检查：<http://127.0.0.1:8000/api/health>

## 前端启动

```bash
cd frontend
npm install
npm run dev
```

访问 <http://127.0.0.1:5173>。Vite 会将 `/api` 代理到 `127.0.0.1:8000`。

生产构建：

```bash
npm run build
```

## 交互式 RAG 投毒检测闭环

本模式在原有本地规则仿真基础上，拆分为外部可信知识库、投毒样本库、AI 交互实验室、交互式可信纠偏和 RAG 训练评测五个页面。AI 交互实验室是主入口：用户选择公开数据集后，系统导入可信 clean chunks、导入训练样本，并从训练数据集中的 poison/benign_error 记录生成可选投毒知识。投毒样本只在用户选择后注入当前 session，不会污染全局可信知识库。

后端环境变量：

```text
DASHSCOPE_API_KEY
BAILIAN_ENABLED
BAILIAN_BASE_URL
BAILIAN_CHAT_MODEL
BAILIAN_EMBEDDING_MODEL
LLM_PROVIDER
OLLAMA_ENABLED
OLLAMA_BASE_URL
OLLAMA_CHAT_MODEL
OLLAMA_EMBEDDING_MODEL
RAG_TOP_K
```

默认模型提供方为 `bailian`：设置 `LLM_PROVIDER=bailian`、`BAILIAN_ENABLED=true` 并配置 `DASHSCOPE_API_KEY` 后，AI 交互实验室会直接调用百炼。API Key 只从环境变量或本地 `backend/.env` 读取，禁止写入代码、README 和测试文件。

如需切回 Ollama，设置 `LLM_PROVIDER=ollama`、`OLLAMA_ENABLED=true`、`OLLAMA_CHAT_MODEL=deepseek-r1:8b`。10 秒内响应依赖本机 CPU/GPU 和模型是否已常驻内存；项目提供快速模式参数：`OLLAMA_CHAT_TIMEOUT=10`、`OLLAMA_NUM_PREDICT=256`、`OLLAMA_NUM_CTX=2048`、`OLLAMA_TEMPERATURE=0.1`、`OLLAMA_KEEP_ALIVE=30m`。这些参数会限制输出长度和上下文，适合演示“投毒前提问”，但不能保证所有硬件都在 10 秒内完成。

启动后端：

```bash
cd backend
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env

# 默认直接使用百炼；如需本地 Ollama，将 .env 中 LLM_PROVIDER 改为 ollama，并设置 OLLAMA_ENABLED=true
python -m uvicorn app.main:app --reload --port 8000
```

启动前端：

```bash
cd frontend
npm install
npm run dev
```

演示流程：

1. 进入“AI 交互实验室”，在“数据集实验准备”中选择 SafeRAG 或 RGB，点击“准备当前实验数据”。
2. 系统会下载/转换所选公开数据集，导入训练数据，导入可信 clean chunks，并从数据集 poison/benign_error 记录生成可选投毒知识。
3. 选择一条数据集投毒知识；实验室会把该样本的 `target_query` 带入问题框，用户也可以改成自己的问题。
4. 点击“投毒前提问”，系统只基于可信知识检索并调用百炼；如果切换到 Ollama，则调用本地 `deepseek-r1:8b` 等模型。
5. 点击“注入样本并投毒后提问”，系统只向当前 session 注入所选投毒 Chunk，再执行混合检索和回答。
6. 点击“执行投毒检测”，展示 RAS、GIS、DualRisk、TrustScore、风险 Chunk 和检测模式。
7. 检测到高风险后点击“进入可信纠偏”，跳转到 `/interactive-correction/{session_id}`。
8. 在纠偏页面查看 original、remove、solo、replace 四路反事实，隔离风险 Chunk 并可信重生成。
9. 进入“结构化风险报告”，选择同一个 AI 交互实验室 session，生成、复制或下载 JSON 报告。

数据文件：

- `backend/app/data/external_trusted_chunks.json`：外部可信知识库。
- `backend/app/data/poison_samples.json`：从训练数据集生成或手动创建的本地防御投毒知识样本库。
- `backend/app/data/interactive_sessions.json`：每次实验 session、注入 Chunk、问答、检测和纠偏结果。
- `backend/app/data/rag_training_datasets.json`：训练评测导入的数据集。
- `backend/app/data/model_artifacts/`：训练后的检测模型和状态文件。
- `data/public_datasets/raw/`：公开数据集原始下载文件，默认不提交到 Git。
- `data/public_datasets/converted/`：转换后的项目 JSONL，默认不提交到 Git。

所有投毒内容仅用于本地防御演示，不连接、不修改、不攻击任何真实在线系统。公开数据集转换不合成模板化问题，不在代码中写死样本内容；AI 交互实验室、风险报告和仪表盘都读取运行时数据集、session 和检测结果。

## 公开数据集与接入建议

有公开数据集可以用于本项目，但需要区分三类：真正面向 RAG 安全攻击的基准、面向 RAG 幻觉/冲突检测的基准，以及可作为“干净知识库”的通用检索语料。当前系统的 `/rag-training` 已支持 JSONL 导入，因此优先把外部数据转换为 `query + clean_chunks + poison_chunks + benign_error_chunks` 的本地防御评测格式。

| 数据集或基准 | 适合用途 | 与本项目的关系 |
|---|---|---|
| SafeRAG | RAG 安全评测，包含 silver noise、inter-context conflict、soft ad、white DoS 等攻击任务 | 最贴近“RAG 安全/投毒/干扰”主题，适合扩展 `poison_chunks`、`benign_error_chunks` 和多类型风险标签 |
| PoisonedRAG | RAG 知识库注入/知识污染攻击研究 | 适合作为论文依据和攻击建模参考；可按其“目标问题 + 目标错误答案 + 少量恶意文本注入”的设定构造本地防御样本 |
| RGB | 中英双语 RAG 鲁棒性评测，覆盖噪声鲁棒、拒答、信息整合、反事实鲁棒 | 适合构造“噪声文档、错误文档、证据不足”样本，用于验证误报控制和可信纠偏 |
| RAGTruth | RAG 场景下的人工标注幻觉语料，包含约 18k 生成回答和词级标注 | 不是投毒数据集，但适合训练“回答是否被证据支持”的检测模块，可映射到 Claim 校验和可信重生成 |
| RAGBench | 约 100k RAG 评测样本，覆盖多个行业语料和可解释标签 | 适合作为通用 RAG 质量评测和可信证据覆盖评测，不直接等价于投毒 |
| BEIR | 18 个公开信息检索数据集组成的异构检索基准 | 适合作为大规模 `clean_chunks` 和检索基线，不含投毒标签，需要额外合成冲突或投毒样本 |

推荐接入顺序：

1. 先用 SafeRAG 和 RGB 扩展安全评测集，覆盖“噪声、冲突、广告诱导、拒答失败、反事实错误”等场景。
2. 再用 RAGTruth/RAGBench 做“证据支持度、幻觉、答案可信度”评测，补强 Claim 验证和重生成质量。
3. 最后用 BEIR、Natural Questions、MS MARCO 等通用检索语料扩充可信知识库，观察 TF-IDF/向量检索在更大语料上的稳定性。

字段约定：

- `query`：数据集原始问题或用户真实问题。
- `clean_chunks`：可信证据，导入后标签为 `trusted`。
- `poison_chunks`：公开数据集或本地防御数据中的干扰/冲突/投毒证据，导入后标签为 `poison`；每条可以包含 `content`、`attack_type`、`target_wrong_answer`、`correct_answer`。
- `benign_error_chunks`：过时、歧义、普通事实错误等非恶意样本，导入后标签为 `benign_error`，用于测试误报控制。
- `correct_answer`、`target_wrong_answer`：只在原始数据集提供时保留；转换器不为缺失字段编造答案。

命令行下载、转换并训练：

```bash
backend/.venv/bin/python backend/scripts/ingest_public_datasets.py --reset-training --limit 120 --train --model-type logistic_regression
```

参考链接：

- SafeRAG: <https://arxiv.org/abs/2501.18636>，代码：<https://github.com/IAAR-Shanghai/SafeRAG>
- PoisonedRAG: <https://arxiv.org/abs/2402.07867>
- RGB: <https://arxiv.org/abs/2309.01431>，代码和数据：<https://github.com/chen700564/RGB>
- RAGTruth: <https://arxiv.org/abs/2401.00396>
- RAGBench: <https://arxiv.org/abs/2407.11005>，数据：<https://huggingface.co/datasets/rungalileo/ragbench>
- BEIR: <https://arxiv.org/abs/2104.08663>，代码：<https://github.com/UKPLab/beir>

## 参考 LangChain RAG 工程实现的系统改造

系统吸收普通 RAG 工程中的“文档加载、文档切分、索引检索、上下文构造、LLM 生成、状态编排”思想，但落地为安全 RAG 工作流，而不是普通问答 Demo。

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

当前实现保持阿里云百炼兼容接口 + LangChain + FAISS/TF-IDF fallback 的技术路线。PGVector 可作为后续部署扩展，但不是必需依赖；项目不复制参考文章中的 OpenAI 模型名、API Key、数据库连接串或密码。

详细映射见 [docs/rag_workflow_reference_mapping.md](docs/rag_workflow_reference_mapping.md)，参考融合边界见 [docs/reference_integration_notes.md](docs/reference_integration_notes.md)。

## Docker Compose

```bash
docker compose up
```

后端和前端分别监听 `8000` 和 `5173`。

## 页面路由

| 路由 | 功能 |
|---|---|
| `/dashboard` | AI 交互实验室态势、数据集、session 风险与检测模式 |
| `/external-knowledge` | 外部可信知识导入、Chunk 管理、索引重建 |
| `/rag-training` | JSONL/公开数据集导入、检测模型训练和真实指标 |
| `/poison-samples` | 数据集投毒知识创建、启停、删除和管理 |
| `/knowledge` | 上传、切分、样例加载、投毒样本管理 |
| `/rag-detection` | RAS/GIS/DualRisk/CausalScore/TrustScore |
| `/interactive-rag-lab` | 数据集准备、Ollama/百炼问答、session 投毒注入、检测和报告 |
| `/interactive-correction/:session_id` | 围绕 AI 实验室 session 的反事实验证、隔离、重检索和可信重生成 |
| `/agent-trust` | 六 Agent 与 Zero-Trust Claim Envelope |
| `/cascade-detection` | 级联错误指标和 Claim DAG |
| `/trace-graph` | 四层 IPJG 联合溯源图谱 |
| `/correction` | 隔离、降权、回滚、BFT 和可信重生成 |
| `/reports` | AI 交互实验室 session JSON 报告复制和下载 |

所有页面均包含加载状态和接口错误提示。图谱支持缩放、拖拽、箭头、边类型、风险配色与邻接高亮；
纠偏页面使用图表对比前后 TrustScore。

## 演示流程

1. 启动前后端，进入“AI 交互实验室”。
2. 选择公开数据集并点击“准备当前实验数据”。
3. 选择数据集投毒知识，执行“投毒前提问”。
4. 执行“注入样本并投毒后提问”，观察 Top-K 和回答变化。
5. 执行“投毒检测”，查看 RAS、GIS、DualRisk 和 TrustScore。
6. 进入“可信纠偏”，完成反事实、隔离和可信重生成。
7. 进入“结构化风险报告”，选择同一 session 生成并下载 JSON。
8. 回到“系统仪表盘”，查看 session 风险和数据集状态。

无需登录，不包含账号和密码。

## 内置案例

1. **企业制度知识投毒**：伪造“权限变更无需审批”文档。
2. **安全情报错误共识**：多个 Agent 复用同一错误 Evidence，将正常 IP 误标为 C2。
3. **Prompt Infection**：RAG 文档包含“忽略规则、关闭防护”等间接提示注入文本。
4. **漏洞状态投毒**：伪造“漏洞已经修复、无需升级或打补丁”的处置结论。
5. **安全认证投毒**：伪造产品已经取得 EAL4+ 最高等级认证。
6. **良性错误负样本**：历史通知中的旧版本信息已过时，但没有恶意诱导或伪造行为。

良性错误会标记为 `benign_error`，保留风险提示但不会进入恶意投毒隔离集合，用于展示误报控制。

所有域名、IP、文档、Agent 和结论均为本地模拟数据。

## API 简介

主要接口：

```text
GET  /api/health
GET  /api/dashboard/stats
POST /api/knowledge/upload
GET  /api/knowledge/list
POST /api/knowledge/load-demo
POST /api/knowledge/clear
POST /api/rag/analyze
GET  /api/rag/cases
GET  /api/rag/cases/{case_id}
POST /api/agents/run-demo
GET  /api/agents/claims
GET  /api/agents/graph
POST /api/detect/cascade
POST /api/detect/poison
POST /api/trace/ipjg
POST /api/correction/run
GET  /api/report/{case_id}
POST /api/external-knowledge/upload
POST /api/external-knowledge/import-dataset-clean
POST /api/external-knowledge/load-demo
GET  /api/external-knowledge/chunks
GET  /api/external-knowledge/stats
POST /api/external-knowledge/rebuild-index
POST /api/external-knowledge/clear
POST /api/poison-samples/create
POST /api/poison-samples/load-demo
POST /api/poison-samples/load-from-training
GET  /api/poison-samples/list
POST /api/poison-samples/{sample_id}/enable
POST /api/poison-samples/{sample_id}/disable
DELETE /api/poison-samples/{sample_id}
POST /api/poison-samples/inject-to-session
POST /api/datasets/import
POST /api/datasets/load-demo
GET  /api/datasets/list
GET  /api/datasets/stats
GET  /api/datasets/samples
POST /api/datasets/reset
POST /api/training/rag-detector/train
GET  /api/training/rag-detector/status
GET  /api/training/rag-detector/metrics
POST /api/training/rag-detector/evaluate
POST /api/training/rag-detector/predict
GET  /api/datasets/public/sources
POST /api/datasets/public/download
POST /api/datasets/public/convert
POST /api/datasets/public/import-training
POST /api/datasets/public/import-clean-knowledge
POST /api/interactive/session/create
GET  /api/interactive/sessions
GET  /api/interactive/session/{session_id}
POST /api/interactive/session/{session_id}/inject-poison
GET  /api/interactive/session/{session_id}/topk
GET  /api/interactive/session/{session_id}/risk-summary
POST /api/interactive/knowledge/trusted
POST /api/interactive/knowledge/poison
GET  /api/interactive/knowledge/chunks
POST /api/interactive/knowledge/reset
POST /api/interactive/rag/chat
POST /api/interactive/rag/chat-detect
POST /api/interactive/correction/quarantine
POST /api/interactive/correction/regenerate
GET  /api/interactive/report/{session_id}
GET  /api/interactive/correction/{session_id}/detail
POST /api/interactive/correction/{session_id}/counterfactual
POST /api/interactive/correction/{session_id}/quarantine
POST /api/interactive/correction/{session_id}/regenerate
GET  /api/interactive/correction/{session_id}/report
```

详细说明见 [docs/api.md](docs/api.md) 和 Swagger。

## 测试

后端：

```bash
cd backend
pytest
```

测试覆盖旧版 RAG 闭环、6 类 Web 案例、良性错误误报控制、外部知识库、投毒样本库、交互式 session、检测到纠偏和训练评测，以及以下路由兼容行为：
`/api/rag/analyze`、`/api/agents/run-demo`、`/api/detect/cascade`、`/api/trace/ipjg`、
`/api/correction/run`、`/api/report/{case_id}`、`/api/interactive/*`。

前端：

```bash
cd frontend
npm run build
```

旧版 RAG 闭环测试和新增 Web/API 兼容测试均位于 `backend/tests/`。

## 核心公式

```text
DualRisk = 0.7 × sqrt(RAS × GIS) + 0.3 × (RAS + GIS) / 2

CausalScore = 0.4 × E_remove + 0.3 × E_solo + 0.3 × E_replace

Weight(claim) =
  TrustScore(evidence) × Support(claim, evidence) × (1 - BSS(agent))
```

TrustScore 综合来源质量、证据覆盖、来源独立性、时效性、检索稳定性、投毒风险、图谱风险、
因果风险和矛盾率。

## 常见问题

### 前端无法访问后端

确认后端运行在 `8000` 端口。开发模式使用 Vite 代理；若单独部署，可设置：

```bash
VITE_API_BASE=http://127.0.0.1:8000/api npm run dev
```

### 上传文件失败

旧版“知识库管理”仅支持 UTF-8 的 `.txt` 和 `.md`。交互式“外部知识库”支持 `.txt`、`.md`、`.pdf`、`.docx`、`.jsonl`。
请确认已经安装 `python-multipart`、`pypdf` 和 `python-docx`。

### 是否必须调用真实 LLM

不是必须。系统默认可离线完成规则检测、训练评测、图谱溯源和可信纠偏；交互式问答当前默认直接调用百炼，也可以切换到本地 Ollama 或本地证据抽取兜底。
检索、NLI、图谱和重生成接口均可替换，后续可升级为 BERT/BGE、NLI 模型、Milvus、Neo4j、GAT 和约束式大模型生成。

### 实验数字是否是公开基准成绩

不是。当前结果来自导入的数据集、交互实验 session 和本地检测模型，只用于验证原型闭环，不代表公开排行榜成绩。

### 如何部署到其他环境

见 [docs/deployment.md](docs/deployment.md)，其中包含本地、Docker Compose、环境变量和故障排查说明。

## GitHub 提交

目标仓库：

```text
git@github.com:weikelai/RAGweblab.git
```

当前开发提交目标为 `dev`：

```bash
git add .
git commit -m "feat: extend dev prototype with cases tests and UI polish"
git push -u origin dev
```

未经评审不要直接合并或推送到 `main`。

## 安全声明

- 本系统仅用于防御研究、教学展示和作品赛答辩。
- 不连接或测试真实在线系统。
- 不包含真实投毒投放、攻击传播或凭证窃取工具。
- 禁止将模拟投毒内容用于污染真实 AI 搜索、知识库或 RAG 服务。
