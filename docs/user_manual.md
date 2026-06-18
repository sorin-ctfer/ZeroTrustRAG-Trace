# 智源净域本地使用手册

## 1. 准备环境

后端：

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

前端：

```bash
cd frontend
npm install
npm run dev
```

访问：`http://127.0.0.1:5173`

## 2. 可选百炼配置

不配置 API Key 也可以完整演示，系统会使用本地证据模板 fallback。需要真实模型问答时，在 `backend/.env` 中配置：

```text
BAILIAN_ENABLED=true
DASHSCOPE_API_KEY=在本机填写，不要提交到仓库
BAILIAN_CHAT_MODEL=qwen-plus
BAILIAN_EMBEDDING_MODEL=text-embedding-v4
RAG_TOP_K=5
```

## 3. 上传文件

已准备好可上传样例：

- `docs/demo_upload_files/trusted_security_policy.md`：可信制度文档。
- `docs/demo_upload_files/trusted_clean_chunks.jsonl`：外部可信知识库 JSONL。
- `docs/demo_upload_files/rag_training_poisonbench_seed.jsonl`：RAG 训练评测 JSONL。

## 4. 演示流程

1. 打开“外部可信知识库”，上传 `trusted_security_policy.md`，或粘贴 `trusted_clean_chunks.jsonl` 并导入 clean_chunks。
2. 点击“重建 FAISS 索引”。如果 FAISS 不可用，系统会显示 TF-IDF fallback，不影响演示。
3. 打开“RAG 训练评测”，导入 `rag_training_poisonbench_seed.jsonl`，训练 Logistic Regression 或 Random Forest。
4. 打开“演示投毒样本库”，点击“加载内置 PoisonBench”，确认样本状态为启用。
5. 打开“AI 交互实验室”，点击“投毒前提问”，查看可信回答和投毒前 Top-K。
6. 选择一个本地演示投毒样本，点击“注入样本并投毒后提问”，查看投毒后 Top-K。
7. 点击“执行投毒检测”，查看 RAS、GIS、DualRisk、RiskScore 和风险原因。
8. 检测为 high risk 后点击“进入可信纠偏”。
9. 在“交互式可信纠偏”页面运行四路反事实、隔离高风险 Chunk、可信重生成并生成 JSON 报告。

## 5. 演示命令

健康检查：

```bash
curl http://127.0.0.1:8000/api/health
```

加载外部可信样例：

```bash
curl -X POST http://127.0.0.1:8000/api/external-knowledge/load-demo
```

查看外部知识库统计：

```bash
curl http://127.0.0.1:8000/api/external-knowledge/stats
```

加载投毒样本：

```bash
curl -X POST http://127.0.0.1:8000/api/poison-samples/load-demo
```

一键跑通交互式投毒检测链路：

```bash
cd backend
.venv/bin/python ../tools/demo_interactive_rag_flow.py
```

生成页面截图：

```bash
cd frontend
PLAYWRIGHT_BROWSERS_PATH=./.ms-playwright node scripts/capture_demo_screenshots.mjs
```

如果 Chromium 缺少系统库，先安装依赖：

```bash
npx playwright install-deps chromium
```

## 6. 截图

本地演示截图建议保存到：

- `docs/screenshots/external_knowledge.png`
- `docs/screenshots/interactive_rag_lab.png`
- `docs/screenshots/interactive_correction.png`

这些截图由本地运行前后端后生成，便于答辩材料直接引用。

当前环境记录：已安装 Playwright 开发依赖，但本机缺少 `libasound.so.2` 等 Chromium 运行库；由于当前用户没有 root 权限，无法自动安装系统依赖。具备 sudo 权限后运行 `PLAYWRIGHT_BROWSERS_PATH=./.ms-playwright npx playwright install chromium` 和 `npx playwright install-deps chromium`，再执行截图脚本即可生成三张截图。`.ms-playwright` 浏览器缓存已加入 `.gitignore`。
