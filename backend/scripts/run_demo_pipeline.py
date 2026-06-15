#!/usr/bin/env python3
"""
命令行一键运行 Demo 流水线。

用法:
    cd zyjd_system/backend
    python -m scripts.run_demo_pipeline
    python -m scripts.run_demo_pipeline --case case_enterprise_rag_poisoning
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# 确保可以导入 app 包
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.case_loader import load_all_cases, list_case_ids
from app.services.pipeline import run_pipeline


def print_separator(char: str = "=", width: int = 70) -> None:
    print(char * width)


def print_section(title: str) -> None:
    print()
    print_separator("-")
    print(f"  {title}")
    print_separator("-")


def run_demo(case_id: str | None = None) -> None:
    """运行 Demo 并打印关键结果。"""
    if case_id:
        case_ids = [case_id]
    else:
        case_ids = list_case_ids()

    if not case_ids:
        print("❌ 未找到任何案例数据。请检查 data/demo_cases/ 目录。")
        return

    print_separator()
    print("  智源净域 — 知识投毒检测、因果溯源与可信重生成系统")
    print("  MVP Demo (规则引擎，无需 GPU)")
    print_separator()

    for cid in case_ids:
        print(f"\n{'#' * 70}")
        print(f"  案例ID: {cid}")
        print(f"{'#' * 70}")

        result = run_pipeline(cid)
        if result is None:
            print(f"❌ 案例 {cid} 不存在或执行失败")
            continue

        case = result.case_info
        if case:
            print_section("1. 案例信息")
            print(f"  标题:   {case.title}")
            print(f"  场景:   {case.scenario_type}")
            print(f"  问题:   {case.question}")
            print(f"  正确答案: {case.true_answer[:60]}...")
            print(f"  攻击目标: {case.target_wrong_answer[:60]}...")

        print_section("2. 检索结果 (Top-K)")
        for ev in result.original_topk_evidence:
            poisoned = "🔴 投毒" if ev.is_poisoned else "🟢 正常"
            print(f"  [{ev.retrieval_rank}] {ev.evidence_id} {poisoned} "
                  f"score={ev.retrieval_score:.4f} "
                  f"{ev.content[:40]}...")

        print_section("3. 双条件检测结果 (RAS / GIS / DualRisk)")
        for d in result.detection_results:
            bar_ras = "█" * int(d.ras * 20)
            bar_gis = "█" * int(d.gis * 20)
            bar_dr = "█" * int(d.dual_risk * 20)
            print(f"  {d.evidence_id}:")
            print(f"    RAS={d.ras:.4f} {bar_ras}")
            print(f"    GIS={d.gis:.4f} {bar_gis}")
            print(f"    DualRisk={d.dual_risk:.4f} {bar_dr}  [{d.risk_level}]")
            if d.reasons:
                for r in d.reasons:
                    print(f"      ⚠ {r}")

        print_section("4. 四路反事实验证 + 因果分")
        for cf in result.counterfactual_results:
            print(f"  可疑证据: {cf.suspicious_evidence_id}")
            print(f"    pO={cf.pO:.2f}  pR={cf.pR:.2f}  pS={cf.pS:.2f}  pT={cf.pT:.2f}")
            print(f"    E_remove={cf.E_remove:.2f}  E_solo={cf.E_solo:.2f}  "
                  f"E_replace={cf.E_replace:.2f}")
            print(f"    ➤ CausalScore = {cf.causal_score:.4f}")

        print_section("5. 投毒传播图谱")
        if result.graph_trace:
            gt = result.graph_trace
            print(f"  节点数: {len(gt.nodes)}")
            print(f"  边数:   {len(gt.edges)}")
            print(f"  可疑路径数: {len(gt.suspicious_paths)}")
            for i, path in enumerate(gt.suspicious_paths[:3]):
                print(f"    路径{i+1}: {' → '.join(path)}")

        print_section("6. TrustScore")
        if result.trust_score_before:
            tsb = result.trust_score_before
            print(f"  检测前 TrustScore: {tsb.trust_score:.1f} [{tsb.trust_level}]")
            print(f"    SQ={tsb.source_quality:.2f}  EC={tsb.evidence_coverage:.2f}  "
                  f"SI={tsb.source_independence:.2f}")
            print(f"    PR={tsb.poison_risk:.2f}  GR={tsb.graph_risk:.2f}  "
                  f"CR={tsb.causal_risk:.2f}  CT={tsb.contradiction_rate:.2f}")
        if result.trust_score_after:
            tsa = result.trust_score_after
            print(f"  重生成后 TrustScore: {tsa.trust_score:.1f} [{tsa.trust_level}]")

        print_section("7. 风险处置")
        print(f"  隔离证据: {result.isolated_evidences or '无'}")
        print(f"  可信证据: {[ev.evidence_id for ev in result.trusted_topk_evidence]}")

        print_section("8. 可信重生成")
        print(f"  原始答案: {case.original_answer[:80]}..." if case and case.original_answer else "")
        print(f"  重生成答案: {result.regenerated_answer[:80]}...")

        print_section("9. 风险报告")
        if result.risk_report:
            rr = result.risk_report
            print(f"  风险等级: {rr.risk_level}")
            print(f"  受影响声明: {rr.affected_claims[:3]}")
            print(f"  因果发现: {rr.causal_findings[:2]}")
            for rec in rr.recommendations:
                print(f"  💡 {rec}")

        print()

    # 汇总
    print_separator()
    print("  ✅ Demo 运行完毕")
    print_separator()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="智源净域 Demo 流水线")
    parser.add_argument("--case", type=str, default=None, help="指定案例 ID")
    args = parser.parse_args()
    run_demo(args.case)
