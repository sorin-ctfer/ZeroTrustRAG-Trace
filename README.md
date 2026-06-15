# 智源净域

> 基于多 Agent 零信任协同与 RAG 知识投毒因果验证的信息污染溯源纠偏系统

智源净域是一个可本地运行、可展示、可测试的全栈安全原型。系统不调用真实大模型 API，而是使用
TF-IDF、余弦相似度、启发式 NLI、NetworkX 和模板生成，演示从知识投毒检测、Agent 声明验证、
级联错误识别、联合溯源到可信纠偏的完整闭环。

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

- 知识库上传、文档切分、Evidence/Chunk 管理和本地模拟投毒样本。
- TF-IDF Top-K 检索和 RAS、GIS、DualRisk 投毒检测。
- 原始、删除可疑、仅可疑、可信替代四路反事实及 CausalScore。
- Planner、Retriever、Threat Intel、Verifier、Decision、Execution 六 Agent。
- Zero-Trust Claim Envelope：身份、权限、Evidence、父 Claim、签名逐项验证。
- Claim Provenance DAG 与 Propagation Factor、False Consensus Rate、Drift Velocity、
  Influence Score、Byzantine Suspicion Score。
- Evidence、Claim、Consensus、Action 四层 IPJG 信息污染联合图谱。
- 高风险 Chunk 隔离、Agent 降权、Claim 回滚和 Evidence-backed BFT Consensus。
- TrustScore 前后对比、可信重生成和结构化 JSON 报告。

## 技术栈

| 部分 | 技术 |
|---|---|
| 后端 | Python 3.10+、FastAPI、Pydantic v2、scikit-learn、NetworkX |
| 前端 | Vue3、Vite、TypeScript、Element Plus、ECharts、Axios |
| 存储 | 本地 JSON |
| 测试 | pytest、FastAPI TestClient、vue-tsc、Vite build |

不包含 `torch`、`transformers`，不需要 GPU、API Key 或网络模型服务。

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

## Docker Compose

```bash
docker compose up
```

后端和前端分别监听 `8000` 和 `5173`。

## 页面路由

| 路由 | 功能 |
|---|---|
| `/dashboard` | 统计卡片与核心能力 |
| `/knowledge` | 上传、切分、样例加载、投毒样本管理 |
| `/rag-detection` | RAS/GIS/DualRisk/CausalScore/TrustScore |
| `/agent-trust` | 六 Agent 与 Zero-Trust Claim Envelope |
| `/cascade-detection` | 级联错误指标和 Claim DAG |
| `/trace-graph` | 四层 IPJG 联合溯源图谱 |
| `/correction` | 隔离、降权、回滚、BFT 和可信重生成 |
| `/reports` | JSON 报告复制和下载 |

## 演示流程

1. 启动前后端，进入“知识库管理”，点击“加载内置样例”。
2. 进入“RAG 投毒检测”，选择案例并执行分析。
3. 查看 Top-K 的 RAS、GIS、DualRisk 和 CausalScore。
4. 进入“Agent 零信任”，运行六 Agent 演示并检查 Claim 封装。
5. 在“级联错误检测”查看伪多数、传播和 Byzantine 可疑度。
6. 在“联合溯源图谱”从最终 Action 反向定位污染 Evidence。
7. 在“可信纠偏”一键隔离、降权、回滚和重新形成共识。
8. 在“风险报告”生成并下载结构化 JSON。

无需登录，不包含账号和密码。

## 内置案例

1. **企业制度知识投毒**：伪造“权限变更无需审批”文档。
2. **安全情报错误共识**：多个 Agent 复用同一错误 Evidence，将正常 IP 误标为 C2。
3. **Prompt Infection**：RAG 文档包含“忽略规则、关闭防护”等间接提示注入文本。

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
```

详细说明见 [docs/api.md](docs/api.md) 和 Swagger。

## 测试

后端：

```bash
cd backend
pytest
```

前端：

```bash
cd frontend
npm run build
```

旧版 RAG 闭环测试和新增 Web/API 集成测试均位于 `backend/tests/`。

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

仅支持 UTF-8 的 `.txt` 和 `.md`。请确认已经安装 `python-multipart`。

### 为什么不调用真实 LLM

作品赛 MVP 优先保证本地可复现和可测试。检索、NLI、图谱和重生成接口均可替换，后续可升级为
BERT/BGE、NLI 模型、Milvus、Neo4j、GAT 和约束式大模型生成。

### 实验数字是否是公开基准成绩

不是。当前结果来自内置小规模案例和固定规则仿真，只用于验证原型闭环。

## GitHub 提交

目标仓库：

```text
git@github.com:weikelai/RAGweblab.git
```

标准提交命令：

```bash
git add .
git commit -m "feat: implement RAGweblab full-stack prototype"
git branch -M main
git remote add origin git@github.com:weikelai/RAGweblab.git
git push -u origin main
```

## 安全声明

- 本系统仅用于防御研究、教学展示和作品赛答辩。
- 不连接或测试真实在线系统。
- 不包含真实投毒投放、攻击传播或凭证窃取工具。
- 禁止将模拟投毒内容用于污染真实 AI 搜索、知识库或 RAG 服务。
