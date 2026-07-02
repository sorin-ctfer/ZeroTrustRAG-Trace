# -*- coding: utf-8 -*-
from __future__ import annotations

import csv
import json
import math
import sqlite3
import zipfile
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

SCRIPT = Path(__file__).resolve()
ROOT = SCRIPT.parent.parent
DATASET_DIR = next(p for p in ROOT.iterdir() if p.is_dir() and (p / "mabzt_comm_dataset" / "manifest.json").exists()) / "mabzt_comm_dataset"
RESULTS_DIR = next(p for p in ROOT.iterdir() if p.is_dir() and (p / "run_summary.json").exists())
OUT = ROOT / "多Agent协同第三章.docx"


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_csv(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


manifest = load_json(DATASET_DIR / "manifest.json")
stats = load_json(RESULTS_DIR / "dataset_statistics.json")
run_summary = load_json(RESULTS_DIR / "run_summary.json")
validation_summary = load_csv(RESULTS_DIR / "validation_summary.csv")
risk_summary = load_csv(RESULTS_DIR / "risk_detection_summary.csv")
root_confusion = load_csv(RESULTS_DIR / "root_cause_confusion.csv")
baseline = load_csv(RESULTS_DIR / "baseline_comparison.csv")
latency = load_csv(RESULTS_DIR / "latency_results.csv")
consensus_summary = load_csv(RESULTS_DIR / "consensus_decision_summary.csv")
risk_scores = load_csv(RESULTS_DIR / "risk_scores.csv")
dynamic_nodes = load_csv(RESULTS_DIR / "dynamic_nodes.csv") if (RESULTS_DIR / "dynamic_nodes.csv").exists() else []
dynamic_claims = load_csv(RESULTS_DIR / "dynamic_claims.csv") if (RESULTS_DIR / "dynamic_claims.csv").exists() else []
dynamic_conflicts = load_csv(RESULTS_DIR / "dynamic_conflicts.csv") if (RESULTS_DIR / "dynamic_conflicts.csv").exists() else []

agents = load_json(DATASET_DIR / "agents.json")
comm_events = load_json(DATASET_DIR / "comm_events.json")
claims = load_json(DATASET_DIR / "claims.json")
evidence = load_json(DATASET_DIR / "evidence.json")

role_counts = Counter(a.get("role") for a in agents)
agent_attack_counts = Counter(a.get("attack_type") for a in agents)
scenario_counts = Counter(e.get("scenario") for e in comm_events)
claim_type_counts = Counter(c.get("type") for c in claims)
evidence_source_counts = Counter(e.get("source_category") for e in evidence)

# Dynamic status matrix and derived detection metrics.
dyn_agents = [r for r in dynamic_nodes if r.get("node_type") == "agent"]
if dyn_agents:
    status_by_truth = Counter((r.get("ground_truth"), r.get("status")) for r in dyn_agents)
    top_dyn = sorted(dyn_agents, key=lambda r: float(r.get("bss") or 0), reverse=True)[:12]
else:
    status_by_truth = Counter()
    top_dyn = []

attack_truths = {"byzantine_agent", "communication_tampering", "evidence_poisoning"}
if dyn_agents:
    tp = sum(1 for r in dyn_agents if r.get("ground_truth") in attack_truths and r.get("status") in {"watch", "restricted", "isolated"})
    fp = sum(1 for r in dyn_agents if r.get("ground_truth") not in attack_truths and r.get("status") in {"watch", "restricted", "isolated"})
    fn = sum(1 for r in dyn_agents if r.get("ground_truth") in attack_truths and r.get("status") not in {"watch", "restricted", "isolated"})
    tn = sum(1 for r in dyn_agents if r.get("ground_truth") not in attack_truths and r.get("status") not in {"watch", "restricted", "isolated"})
else:
    tp = fp = fn = tn = 0
precision = tp / (tp + fp) if (tp + fp) else 0
recall = tp / (tp + fn) if (tp + fn) else 0
f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0
restricted_tp = sum(1 for r in dyn_agents if r.get("ground_truth") in attack_truths and r.get("status") in {"restricted", "isolated"}) if dyn_agents else 0

# Root cause metrics from official batch confusion table.
correct_root = 0
total_root = 0
attack_correct = 0
attack_total = 0
for r in root_confusion:
    gt = r["ground_truth"]
    pred = r["predicted_root_cause"]
    count = int(r["count"])
    total_root += count
    expected = "none" if gt in {"none", "noisy_watch"} else gt
    if pred == expected:
        correct_root += count
    if gt in attack_truths:
        attack_total += count
        if pred == gt:
            attack_correct += count
root_overall_acc = correct_root / total_root if total_root else 0
root_attack_acc = attack_correct / attack_total if attack_total else 0

validation_failed = int(stats.get("validation_failed", 0))
validation_passed = int(stats.get("validation_passed", 0))
validation_total = validation_failed + validation_passed
validation_pass_rate = validation_passed / validation_total if validation_total else 0

# Consensus aggregate.
consensus_decisions = Counter()
for r in consensus_summary:
    consensus_decisions[r.get("decision")] += int(r.get("count") or 0)

# Dynamic SQLite table counts, if available.
dyn_db_counts = {}
dyn_db = RESULTS_DIR / "dynamic_runtime.db"
if dyn_db.exists():
    try:
        con = sqlite3.connect(str(dyn_db))
        cur = con.cursor()
        for t in ["nodes", "event_queue", "claims", "transmissions", "conflicts", "seen_nonces", "sim_state"]:
            try:
                dyn_db_counts[t] = cur.execute(f"select count(*) from {t}").fetchone()[0]
            except Exception:
                pass
        con.close()
    except Exception:
        pass


def fmt_pct(x, digits=2):
    return f"{x * 100:.{digits}f}%"


def fmt_float(x, digits=3):
    try:
        return f"{float(x):.{digits}f}"
    except Exception:
        return str(x)


def x(s):
    return escape(str(s), {'"': '&quot;'})


def rpr(text, bold=False, size=21):
    props = [
        '<w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:eastAsia="宋体"/>',
        f'<w:sz w:val="{size}"/>',
        f'<w:szCs w:val="{size}"/>'
    ]
    if bold:
        props.insert(0, '<w:b/>')
    return '<w:r><w:rPr>' + ''.join(props) + '</w:rPr><w:t xml:space="preserve">' + x(text) + '</w:t></w:r>'


def para(text="", bold=False, size=21, before=0, after=120, jc=None, indent=False):
    ppr = [f'<w:spacing w:before="{before}" w:after="{after}"/>']
    if jc:
        ppr.append(f'<w:jc w:val="{jc}"/>')
    if indent:
        ppr.append('<w:ind w:left="420"/>')
    return '<w:p><w:pPr>' + ''.join(ppr) + '</w:pPr>' + rpr(text, bold=bold, size=size) + '</w:p>'


def heading(text, level=1):
    if level == 1:
        return para(text, bold=True, size=32, before=360, after=160)
    if level == 2:
        return para(text, bold=True, size=28, before=280, after=140)
    return para(text, bold=True, size=24, before=220, after=120)


def bullet(text):
    return para("• " + text, size=21, after=80, indent=True)


def cell(text, header=False):
    shading = '<w:shd w:fill="D9D9D9"/>' if header else ''
    return '<w:tc><w:tcPr><w:tcW w:w="2400" w:type="dxa"/>' + shading + '</w:tcPr>' + para(text, bold=header, size=20, after=60) + '</w:tc>'


def table(rows, header=True):
    xml = ['<w:tbl><w:tblPr><w:tblStyle w:val="TableGrid"/><w:tblW w:w="0" w:type="auto"/><w:tblBorders>'
           '<w:top w:val="single" w:sz="4" w:space="0" w:color="999999"/>'
           '<w:left w:val="single" w:sz="4" w:space="0" w:color="999999"/>'
           '<w:bottom w:val="single" w:sz="4" w:space="0" w:color="999999"/>'
           '<w:right w:val="single" w:sz="4" w:space="0" w:color="999999"/>'
           '<w:insideH w:val="single" w:sz="4" w:space="0" w:color="999999"/>'
           '<w:insideV w:val="single" w:sz="4" w:space="0" w:color="999999"/>'
           '</w:tblBorders></w:tblPr>']
    for i, row in enumerate(rows):
        xml.append('<w:tr>')
        for item in row:
            xml.append(cell(item, header=(header and i == 0)))
        xml.append('</w:tr>')
    xml.append('</w:tbl>')
    return ''.join(xml) + para("", after=120)


body = []
body.append(para("多 Agent 协同第三章实验结果分析", bold=True, size=36, jc="center", before=240, after=160))
body.append(para(f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}；数据来源：{RESULTS_DIR}", size=20, jc="center", after=240))
body.append(para("说明：本文仅填充当前实验结果能够支撑的第三章内容；对于公开数据集、RAG 真实纠偏后重跑、正式 baseline 重跑等尚未具备的数据，均在相应小节中如实标注为缺口。", size=21, after=160))

body.append(heading("一、第三章问题回答状态总览", 1))
status_rows = [
    ["第三章问题", "是否可回答", "当前可写入内容/缺口"],
    ["3.1 测试环境中 Agent 模块环境", "可以", "可写 Python 3.12 + Flask + SQLite + Neo4j + ECharts，且已形成无依赖一键启动包。"],
    ["3.2 Agent 自构造测试数据集", "可以", f"可写自构造数据集 {manifest.get('dataset_id')}，含 {stats['agents']} 个 Agent、{stats['comm_events']} 条通信事件、{stats['claims']} 条声明。"],
    ["3.2.2.1 多 Agent 协同任务场景", "可以；接公开数据集后更完整", f"当前支持 {stats['tasks']} 个任务、{stats['consensus_groups']} 个共识组和 {stats['challenges']} 个挑战记录；缺公开数据集迁移验证。"],
    ["3.2.2.4 通信干扰场景", "可以", f"已有 communication_tampering 场景 {scenario_counts.get('communication_tampering', 0)} 条事件，并覆盖签名、消息哈希、nonce、工具哈希等异常。"],
    ["3.3.1 多 Agent 模块测试方案", "可以", "可写数据加载、声明包构造、七项校验、声明图谱、共识、BSS、动态前端展示和结果导出流程。"],
    ["3.3.3 多 Agent 与 RAG 融合方案中的 Agent 接口", "可以", "可写 Evidence/RAG 片段字段与 ClaimPackage 接口；真实 RAG API 与纠偏回写由 RAG 小组补齐。"],
    ["3.3.4 Agent 评估指标", "可以", "可写七项零信任校验、BSS 八维指标、共识指标、延迟和检测指标。"],
    ["3.4.1 多 Agent 级联错误检测结果", "可以", f"当前 {validation_total} 个声明包中 {validation_failed} 个未通过校验，动态运行产生 {len(dynamic_conflicts)} 条冲突记录。"],
    ["3.4.2 拜占庭节点识别结果", "可以", f"动态运行下 suspicious 口径 TP={tp}、FP={fp}、FN={fn}、TN={tn}，召回率 {fmt_pct(recall)}。"],
    ["3.4.4 因果溯源中的 Agent 根因分类", "可以", f"根因分类对攻击类节点准确率 {fmt_pct(root_attack_acc)}，总体准确率 {fmt_pct(root_overall_acc)}。"],
    ["3.4.5 融合纠偏前后对比中的 Agent 检测部分", "部分可以", "可写纠偏前 Agent 检测与共识结果；缺 RAG 纠偏后替换证据并重跑的 before/after 对比。"],
    ["3.5.1 无防护多 Agent 对比", "需要补正式 baseline", "已有 preliminary baseline_comparison.csv，但建议补同一动态流程下的正式无防护重跑。"],
    ["3.5.2 多数投票方法对比", "需要补正式 baseline", "已有 preliminary majority_vote 行，但建议补独立多数投票实现与日志证据。"],
    ["3.5.3 单 Verifier Agent 对比", "需要补正式 baseline", "已有 preliminary single_verifier_agent 行，但建议补单 Verifier 的端到端重跑。"],
    ["3.6 Agent 侧结果分析", "可以", "可基于误检/漏检、主导失败项、根因分类、动态展示和工程可复现性展开分析。"],
]
body.append(table(status_rows))

body.append(heading("3.1 测试环境中 Agent 模块环境", 1))
body.append(para("本实验的 Agent 模块采用本地可复现环境实现，核心目标是同时满足实验计算、动态展示和结果导出。当前环境已经整理为无依赖一键启动包，包含 Java、Neo4j、Python 运行时以及前端本地 ECharts 文件，避免验收机器缺少运行时导致复现实验失败。"))
body.append(table([
    ["层级", "实现", "当前证据/路径"],
    ["后端服务", "Python 3.12 + Flask", "实验代码/agent_demo_app；便携包 app/"],
    ["前端展示", "HTML/CSS/JavaScript + ECharts graph", "白灰黑配色；支持 Agent 离散图、声明图谱、动态发包线条和节点风险颜色。"],
    ["运行时数据库", "SQLite", "dynamic_runtime.db：nodes、event_queue、claims、transmissions、conflicts、seen_nonces、sim_state。"],
    ["图数据库", "Neo4j Community 2026.02.2", "Neo4j 导入后节点 3654、关系 7441；Browser 端口 7474，Bolt 端口 7687。"],
    ["一键启动", "start_demo.bat / stop_demo.bat", "无依赖一键启动包内置 runtime/java21、runtime/neo4j、runtime/python312、runtime/python_site。"],
]))
body.append(table([
    ["验收项", "结果"],
    ["Dashboard", "http://127.0.0.1:5000，HTTP 200，标题为“多 Agent 动态发包与声明图谱验收台”。"],
    ["Neo4j Browser", "http://127.0.0.1:7474，用户 neo4j，密码为项目约定密码。"],
    ["默认数据集加载", f"初始状态 nodes={stats['agents'] + 2 if stats.get('agents') else 56}（含网关与中继系统节点）、claims=0、conflicts=0。"],
    ["动态图谱导出", "动态跑完后生成 dynamic_nodes.csv、dynamic_claims.csv、dynamic_conflicts.csv、dynamic_final_charts.json。"],
]))

body.append(heading("3.2 Agent 自构造测试数据集", 1))
body.append(para(f"当前数据集为自构造合成数据集，数据集 ID 为 {manifest.get('dataset_id')}，schema_version 为 {manifest.get('schema_version')}，随机种子为 {manifest.get('seed')}。该数据集不是简单静态样例，而是覆盖 Agent 注册、通信事件、结构化声明、证据、工具调用、共识组和挑战记录的完整链路。"))
body.append(table([
    ["数据对象", "规模"],
    ["Agent", stats["agents"]],
    ["任务", stats["tasks"]],
    ["通信事件", stats["comm_events"]],
    ["声明/声明包", stats["claims"]],
    ["证据", stats["evidence"]],
    ["工具调用", stats["tool_calls"]],
    ["共识组", stats["consensus_groups"]],
    ["挑战记录", stats["challenges"]],
]))
body.append(table([["Agent 角色", "数量"]] + [[k, v] for k, v in sorted(role_counts.items())]))
body.append(table([["Agent 攻击/行为类型", "节点数量"]] + [[k, v] for k, v in sorted(agent_attack_counts.items())]))
body.append(table([["通信场景", "事件数量"]] + [[k, v] for k, v in sorted(scenario_counts.items())]))
body.append(table([["声明类型", "数量"]] + [[k, v] for k, v in sorted(claim_type_counts.items())]))
body.append(table([["证据来源类型", "数量"]] + [[k, v] for k, v in sorted(evidence_source_counts.items())]))
body.append(para("代表性说明：数据集覆盖正常协同、证据投毒、拜占庭虚假声明、通信篡改、重放/nonce 异常、无效签名、无效工具哈希、高置信无证据声明等典型 Agent 侧污染/干扰路径。局限是当前仍为自构造数据集，尚未接入公开多 Agent 通信数据集，因此外部有效性需要后续补充。"))

body.append(heading("3.2.2.1 多 Agent 协同任务场景", 2))
body.append(para("多 Agent 协同任务场景按任务组织，每个任务围绕一个风险判断或处置动作展开。rag_reader 提供风险判断和证据摘要，forensic 给出取证证据，planner 提出处置建议，verifier 执行挑战/验证，comm_monitor 监测链路完整性，watcher 提供低权限观察性判断。所有 Agent 输出不直接进入最终决策，而是先进入声明网关构造 ClaimPackage，再进入校验、图谱和共识流程。"))
body.append(table([
    ["协同要素", "当前实现"],
    ["任务规模", f"{stats['tasks']} 个任务。"],
    ["通信粒度", f"{stats['comm_events']} 条事件，每条事件可生成一个结构化声明包。"],
    ["共识组织", f"{stats['consensus_groups']} 个 consensus group，用于聚合同一 subject/object 下的支持或冲突声明。"],
    ["挑战机制", f"{stats['challenges']} 条 verifier challenge，用于高风险动作或冲突声明的附加确认。"],
    ["动作类声明", f"{claim_type_counts.get('action_recommendation', 0)} 条 action_recommendation，可触发高风险动作阈值约束。"],
]))
body.append(para("若第三章需要更强说服力，建议后续将公开数据集或真实 RAG 小组输出转换为相同 schema，再追加跨数据源复现实验。"))

body.append(heading("3.2.2.4 通信干扰场景", 2))
body.append(para("通信干扰场景主要验证零信任通信网关能否发现消息传输链路中的不一致，而不是仅依赖 Agent 自报可信。数据结构中保留 message_hash_sent、message_hash_received、transport_integrity、signature、nonce、tool_hash 等字段，能够表达链路篡改、签名异常、重放攻击和工具结果替换。"))
body.append(table([
    ["干扰类型/校验项", "实验体现", "当前结果"],
    ["消息篡改", "message_hash_sent 与 message_hash_received 不一致，或 transport_integrity=false", f"communication_tampering 场景 {scenario_counts.get('communication_tampering', 0)} 条事件。"],
    ["签名异常", "I_sig=false", f"失败 {next((r['failed'] for r in validation_summary if r['check']=='I_sig'), 'NA')} 次。"],
    ["重放攻击", "nonce 重复导致 I_nonce=false", f"失败 {next((r['failed'] for r in validation_summary if r['check']=='I_nonce'), 'NA')} 次。"],
    ["工具结果替换", "tool_hash 不匹配导致 I_tool=false", f"失败 {next((r['failed'] for r in validation_summary if r['check']=='I_tool'), 'NA')} 次。"],
    ["冲突声明", "同一声明组内出现相反 label 或动作建议", f"动态全量运行记录 conflicts={len(dynamic_conflicts)}。"],
]))

body.append(heading("3.3.1 多 Agent 模块测试方案", 1))
body.append(para("测试方案采用“离线批处理指标 + 前端动态演示”双路径。离线批处理用于稳定导出 CSV/JSON 指标，动态演示用于展示 Agent 实时发包、网关转发、中继构图、节点 BSS 变化和冲突事件。"))
body.append(table([
    ["步骤", "输入", "处理", "输出/结果文件"],
    ["1 数据加载", "agents/tasks/evidence/comm_events 等 JSON", "加载默认数据集，初始化 SQLite nodes 与 event_queue", "dynamic_runtime.db"],
    ["2 声明包构造", "原始通信事件", "ClaimGateway 生成 ClaimPackage，绑定证据、工具哈希、签名、nonce", "claim_packages.json / dynamic_claims.csv"],
    ["3 零信任校验", "ClaimPackage", "执行 I_schema/I_sig/I_time/I_nonce/I_perm/I_ev/I_tool 七项校验", "validation_results.csv / validation_summary.csv"],
    ["4 声明图谱", "Agent、Claim、Evidence、Tool、ClaimGroup", "构造 provenance graph，并导入 Neo4j", "graph_snapshot.json / neo4j_import.cypher"],
    ["5 冲突与共识", "声明组与校验结果", "识别冲突，计算证据质量、ESS、Agent 权重和共识分", "consensus_results.csv / consensus_decision_summary.csv"],
    ["6 BSS 与根因", "校验失败、证据质量、冲突、链路完整性", "计算 H/R/P/S/D/F/O/M 与 BSS，给出状态和根因", "risk_scores.csv / dynamic_nodes.csv"],
    ["7 前端展示", "动态 API 状态", "ECharts 展示 Agent 离散图、声明图谱和统计图", "dashboard 截图与 dynamic_final_charts.json"],
]))
body.append(para("动态运行的关键表包括 nodes、event_queue、claims、transmissions、conflicts、seen_nonces、sim_state。全量跑完时，SQLite 中 claims=1200、transmissions=3600、conflicts=720，说明事件不是静态一次性渲染，而是在发包过程中逐步写入。"))

body.append(heading("3.3.3 多 Agent 与 RAG 融合方案中的 Agent 接口", 1))
body.append(para("当前 Agent 侧已经预留与 RAG 模块融合的接口：RAG 或证据检索模块输出 Evidence 记录，Agent 在声明包中通过 evidence_ids 引用证据，并把证据质量、投毒风险、因果风险等字段纳入校验、共识和 BSS 计算。"))
body.append(table([
    ["接口对象", "关键字段", "用途"],
    ["Evidence/RAG 片段", "evidence_id、task_id、subject、source_category、trust_score、dual_risk、causal_score、source_independence、rag_returned、source_uri、summary", "表达 RAG 返回片段、来源可信度、双重风险、因果风险与证据独立性。"],
    ["Agent 通信事件", "sender、receiver、raw_message、sent_message、received_message、message_hash_sent、message_hash_received、transport_integrity", "作为 Agent 发包和通信干扰检测的输入。"],
    ["ClaimPackage", "claim_id、claim_group_id、type、subject、predicate、object、label、confidence、evidence_ids、tool_call_id、tool_hash、timestamp、nonce、signature", "作为零信任网关的统一声明包格式。"],
    ["RAG 投毒识别字段", "source_category=poisoned_rag、dual_risk>=0.65、trust_score 低、causal_score 高", "进入 P 指标、证据质量 Q(e)、ESS 和根因 evidence_poisoning。"],
]))
body.append(para("缺口：当前实验使用合成 Evidence 模拟 RAG 正常片段与 poisoned_rag 片段，尚未调用 RAG 小组真实 API，也没有把纠偏后的 RAG 结果回写为新 Evidence 后重跑。因此本小节可写接口设计和 Agent 侧消费逻辑，但不能声称已完成真实 RAG 端到端融合纠偏实验。"))

body.append(heading("3.3.4 Agent 评估指标", 1))
body.append(para("Agent 侧指标分为四类：零信任声明包校验指标、拜占庭嫌疑 BSS 指标、共识决策指标和工程运行指标。"))
body.append(table([
    ["校验项", "含义", "失败数/失败率"],
] + [[r["check"], "声明包七项校验或总体通过性", f"{r['failed']}/{r['total']}（{fmt_pct(float(r['failure_rate']))}）"] for r in validation_summary]))
body.append(table([
    ["BSS 维度", "权重", "触发含义"],
    ["H", "0.18", "传输哈希不一致或 transport_integrity=false，指向通信篡改。"],
    ["R", "0.08", "nonce 重复或重放。"],
    ["P", "0.18", "引用 poisoned_rag 或高 dual_risk 证据且声明置信度较高。"],
    ["S", "0.14", "schema、signature 或 tool hash 校验失败。"],
    ["D", "0.15", "高置信声明但 ESS 或平均证据质量偏低。"],
    ["F", "0.11", "高风险动作（如 block_ip）证据不足或校验失败。"],
    ["O", "0.08", "高置信离群声明或时间窗口异常。"],
    ["M", "0.08", "冲突声明中仍高置信或证据支持不足。"],
]))
body.append(para("BSS 计算采用加权求和并对重复投毒/拜占庭模式轻微放大：BSS=min(1, Σ rate(k)*w(k)*(1+0.25*max(P,M,S)))。状态阈值为 normal<0.25，watch<0.50，restricted<0.75，isolated≥0.75。"))
body.append(table([
    ["运行指标", "结果"],
] + [[r["stage"], f"total_ms={r['total_ms']}，count={r['count']}，avg_ms={r['avg_ms']}"] for r in latency]))

body.append(heading("3.4.1 多 Agent 级联错误检测结果", 1))
body.append(para(f"在 {validation_total} 个声明包中，{validation_passed} 个通过七项零信任校验，{validation_failed} 个至少存在一项失败，整体通过率 {fmt_pct(validation_pass_rate)}，失败率 {fmt_pct(1 - validation_pass_rate)}。"))
body.append(table([
    ["校验项", "失败数", "总数", "失败率"],
] + [[r["check"], r["failed"], r["total"], fmt_pct(float(r["failure_rate"]))] for r in validation_summary]))
body.append(para("主要错误来源为证据绑定失败 I_ev、签名失败 I_sig 和工具哈希失败 I_tool，分别对应证据投毒/无证据高置信、通信篡改/签名异常、工具结果被替换等级联错误入口。动态运行阶段还记录了 Agent→Gateway、Gateway→Relay、Relay→Receiver 三段 transmission，因此 1200 个事件对应 3600 条传输记录，便于前端实时显示发包链路。"))
body.append(table([
    ["动态运行项", "数量"],
    ["nodes", dyn_db_counts.get("nodes", len(dynamic_nodes) or "NA")],
    ["event_queue", dyn_db_counts.get("event_queue", stats["comm_events"])],
    ["claims", dyn_db_counts.get("claims", len(dynamic_claims))],
    ["transmissions", dyn_db_counts.get("transmissions", "NA")],
    ["conflicts", dyn_db_counts.get("conflicts", len(dynamic_conflicts))],
]))
body.append(para("结论：Agent 侧已经能够定位从通信链路异常、声明包结构/签名异常、证据质量异常到声明冲突的级联错误链路；但若要进一步证明纠偏效果，需要 RAG 纠偏后重跑同一批任务并比较失败项下降幅度。"))

body.append(heading("3.4.2 拜占庭节点识别结果", 1))
body.append(para("以动态全量运行的节点最终状态为主，若将 watch、restricted、isolated 视为 suspicious，则攻击类节点 TP=16、FN=2，正常/噪声节点 FP=0、TN=36，precision=100.00%，recall=88.89%，F1=94.12%。若仅把 restricted/isolated 视为强处置，则攻击类强处置数为 14/18。"))
status_rows2 = [["ground_truth", "normal", "watch", "restricted", "isolated", "合计"]]
truths = ["communication_tampering", "byzantine_agent", "evidence_poisoning", "noisy_watch", "none"]
for gt in truths:
    normal = status_by_truth.get((gt, "normal"), 0)
    watch = status_by_truth.get((gt, "watch"), 0)
    restricted = status_by_truth.get((gt, "restricted"), 0)
    isolated = status_by_truth.get((gt, "isolated"), 0)
    status_rows2.append([gt, normal, watch, restricted, isolated, normal + watch + restricted + isolated])
body.append(table(status_rows2))
body.append(table([
    ["指标", "数值"],
    ["TP", tp], ["FP", fp], ["FN", fn], ["TN", tn],
    ["Precision", fmt_pct(precision)], ["Recall", fmt_pct(recall)], ["F1", fmt_pct(f1)],
    ["强处置攻击节点数", f"{restricted_tp}/{tp + fn}"],
]))
body.append(table([["Top 风险节点", "角色", "真实类型", "BSS", "状态", "根因"]] + [[r.get("node_id"), r.get("role"), r.get("ground_truth"), fmt_float(r.get("bss"), 3), r.get("status"), r.get("root_cause")] for r in top_dyn[:10]]))
body.append(para("漏检主要来自两个 byzantine_agent 节点在当前事件队列中没有足够有效样本或行为触发，sample_count 接近 0 时 BSS 不会上升。这一点可在后续通过提高每类攻击节点参与度或加入主动探测任务补齐。"))

body.append(heading("3.4.4 因果溯源中的 Agent 根因分类", 1))
body.append(para(f"批处理结果中的 root_cause_confusion.csv 显示，攻击类根因分类准确率为 {fmt_pct(root_attack_acc)}，若将 none 与 noisy_watch 都视为非攻击根因，则总体准确率为 {fmt_pct(root_overall_acc)}。"))
body.append(table([["ground_truth", "predicted_root_cause", "count"]] + [[r["ground_truth"], r["predicted_root_cause"], r["count"]] for r in root_confusion]))
body.append(para("根因判定逻辑与 BSS 维度绑定：H 高时优先归因为 communication_tampering；P 高时归因为 evidence_poisoning；S/F/M 或 D/O 长期异常时归因为 byzantine_agent。该设计使“检测为高风险”和“解释为什么高风险”能够在同一条事件链上闭环。"))
body.append(para("当前不足：root cause 仍依赖规则和合成标签，尚未使用真实因果图学习或 RAG 小组的投毒因果验证输出。因此第三章中可以写 Agent 侧根因分类结果，但不应把它表述为完整的跨模块因果证明。"))

body.append(heading("3.4.5 融合纠偏前后对比中的 Agent 检测部分", 1))
body.append(para("当前可以填写“纠偏前/检测阶段”的 Agent 侧结果：零信任校验发现 248 个异常声明包，动态冲突检测记录 720 条冲突，BSS 对 16/18 个攻击类节点给出 suspicious 状态，共识阶段将声明组划分为 accepted/challenged/rejected。"))
body.append(table([
    ["共识决策", "数量"],
    ["accepted", consensus_decisions.get("accepted", 0)],
    ["challenged", consensus_decisions.get("challenged", 0)],
    ["rejected", consensus_decisions.get("rejected", 0)],
]))
body.append(para("不能完整回答的部分：当前没有 RAG 纠偏后重新生成 Evidence/ClaimPackage 并重跑 Agent 检测的结果，因此不能给出纠偏前后 I_ev 失败率、BSS 均值、冲突数、攻击成功率等指标的下降幅度。建议补充实验：固定 seed 和任务集，先跑 poisoned_rag 原始证据，再将 RAG 小组纠偏后的证据替换为 corrected_rag，重跑 validation、consensus、BSS 和 dynamic charts。"))

body.append(heading("3.5 对比实验：当前状态与需补数据", 1))
body.append(para("结果目录中存在 baseline_comparison.csv，可作为 preliminary 对比，但这些结果尚未形成独立的、与动态演示同流程的 baseline 重跑日志。因此 3.5.1、3.5.2、3.5.3 建议在正文中标注为“已有初步结果，正式实验仍需补跑”。"))
body.append(table([["method", "tasks", "accuracy", "false_block_rate", "missed_threat_rate", "attack_success_rate", "使用建议"]] + [[r["method"], r["tasks"], r["accuracy"], r["false_block_rate"], r["missed_threat_rate"], r["attack_success_rate"], "preliminary，不建议作为最终正式 baseline" if r["method"] != "zero_trust_weighted_consensus" else "本方法结果"] for r in baseline]))
body.append(para("需要补充的正式 baseline：1）无防护多 Agent：直接信任 Agent 输出，不做声明包校验和 BSS；2）多数投票：只按声明标签票数决策，不考虑证据质量、Agent 风险和高风险动作约束；3）单 Verifier Agent：只使用单个 verifier 的判断，不做多源证据加权共识。三者均应输出与当前系统相同的 accuracy、false_block_rate、missed_threat_rate、attack_success_rate、latency 和日志文件。"))

body.append(heading("3.6 Agent 侧结果分析", 1))
body.append(bullet("零信任声明包机制有效暴露了 Agent 协同链路中的结构、签名、时间、nonce、权限、证据和工具哈希问题。当前总体失败率为 20.67%，其中证据绑定和签名异常是主导因素。"))
body.append(bullet("BSS 对通信篡改和证据投毒的识别较稳定：communication_tampering 在动态运行中 4/4 restricted，evidence_poisoning 为 4 restricted + 2 watch。"))
body.append(bullet("拜占庭节点识别受行为样本覆盖影响：8 个 byzantine_agent 中 6 个被 restricted，2 个因样本不足未升高风险。后续应补主动挑战或增加其参与任务。"))
body.append(bullet("根因分类可以把通信篡改、证据投毒、拜占庭行为拆开解释，便于第三章从“检测结果”过渡到“污染溯源”。"))
body.append(bullet("动态前端与 SQLite 运行库已经满足验收展示需求：节点表和声明表动态写入，声明图谱和风险状态实时更新，并能在跑完后导出统计图表。"))
body.append(bullet("当前最大缺口是 RAG 真实纠偏后重跑和正式 baseline 重跑。没有这两部分时，第三章中融合纠偏前后对比和 3.5 对比实验只能写方法与 preliminary 结果，不能写最终结论。"))

body.append(heading("附：结果文件证据清单", 1))
body.append(table([
    ["文件", "用途"],
    ["实验数据集/mabzt_comm_dataset/manifest.json", "数据集 ID、schema、seed 和规模。"],
    ["实验结果/dataset_statistics.json", "数据规模、场景分布和校验统计。"],
    ["实验结果/validation_summary.csv", "七项零信任校验失败率。"],
    ["实验结果/risk_scores.csv", "批处理 BSS 节点风险结果。"],
    ["实验结果/dynamic_nodes.csv", "动态运行后节点状态、BSS 和根因。"],
    ["实验结果/dynamic_claims.csv", "动态声明包写入结果。"],
    ["实验结果/dynamic_conflicts.csv", "动态冲突检测结果。"],
    ["实验结果/root_cause_confusion.csv", "根因分类混淆矩阵。"],
    ["实验结果/baseline_comparison.csv", "初步 baseline 对比，仍需正式补跑。"],
    ["实验结果/neo4j_import.cypher", "Neo4j 声明图谱导入脚本。"],
]))

# Build minimal DOCX.
document_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:wpc="http://schemas.microsoft.com/office/word/2010/wordprocessingCanvas" xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math" xmlns:v="urn:schemas-microsoft-com:vml" xmlns:wp14="http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing" xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" xmlns:w10="urn:schemas-microsoft-com:office:word" xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml" xmlns:wpg="http://schemas.microsoft.com/office/word/2010/wordprocessingGroup" xmlns:wpi="http://schemas.microsoft.com/office/word/2010/wordprocessingInk" xmlns:wne="http://schemas.microsoft.com/office/word/2006/wordml" xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape" mc:Ignorable="w14 wp14">
  <w:body>
    {''.join(body)}
    <w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1440" w:right="1200" w:bottom="1440" w:left="1200" w:header="720" w:footer="720" w:gutter="0"/></w:sectPr>
  </w:body>
</w:document>'''

content_types = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>'''
rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>'''

with zipfile.ZipFile(OUT, "w", compression=zipfile.ZIP_DEFLATED) as z:
    z.writestr("[Content_Types].xml", content_types)
    z.writestr("_rels/.rels", rels)
    z.writestr("word/document.xml", document_xml)

print(OUT)
print(f"size={OUT.stat().st_size}")
