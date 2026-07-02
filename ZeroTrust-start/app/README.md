# Multi-Agent Zero-Trust Claim Demo

本目录是 Agent 侧“多 Agent 零信任协同 + 声明包 + 声明图谱 + BSS 拜占庭识别”的可运行实验系统。

## 技术栈

- Backend: Python 3.12 + Flask + Flask-CORS
- Runtime DB: SQLite (`实验结果/runtime.db`)
- Graph DB: Neo4j Community，本机路径见 `../其他文件/Neo4j运行说明.md`
- Frontend: HTML/CSS/JavaScript + vis-network；离线时自动降级到内置 SVG 图谱渲染

## Quick start

```powershell
cd E:\daily\3-吴永贤\备课\最终版\最终实验\实验代码
.\run_demo.ps1
```

打开：<http://127.0.0.1:5000>

## 带 Neo4j 启动

```powershell
cd E:\daily\3-吴永贤\备课\最终版\最终实验\实验代码
.\run_demo.ps1 -StartNeo4j
```

若需要手动导入图谱：

```powershell
$env:NEO4J_USER="neo4j"
$env:NEO4J_PASSWORD="你的密码"
.\import_neo4j.ps1
```

## 单独复现实验

```powershell
.\.venv\Scripts\python.exe .\generate_dataset.py
.\.venv\Scripts\python.exe .\run_experiments.py
.\.venv\Scripts\python.exe -m unittest discover -s .\tests -v
```

## 关键输出

- `../实验数据集/mabzt_comm_dataset/`：54 Agent、120 任务、1200 通信事件、1200 Claim、480 Evidence。
- `../实验结果/claim_packages.json`：零信任声明包。
- `../实验结果/validation_results.csv`：七项校验明细。
- `../实验结果/graph_snapshot.json`：声明传播图谱。
- `../实验结果/neo4j_import.cypher`：Neo4j 导入脚本。
- `../实验结果/consensus_results.csv`：证据加权共识结果。
- `../实验结果/risk_scores.csv`：H/R/P/S/D/F/O/M 与 BSS。
- `../实验结果/agent_demo_report.md`：第三章可引用实验报告摘要。
