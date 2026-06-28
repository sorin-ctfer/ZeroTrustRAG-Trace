#!/usr/bin/env python3
"""Generate a local demo visualization for RAG knowledge poisoning impact."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import FancyArrowPatch, Rectangle


ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "backend" / "app" / "data" / "reports" / "case_enterprise_policy_approval.json"
OUT_DIR = ROOT / "docs" / "implementation_assets"
OUT_PATH = OUT_DIR / "rag_poisoning_case_comparison.png"


def configure_font() -> None:
    """Use an available CJK font when possible."""
    font_files = [
        Path("/mnt/c/Windows/Fonts/msyh.ttc"),
        Path("/mnt/c/Windows/Fonts/simhei.ttf"),
        Path("/mnt/c/Windows/Fonts/simsun.ttc"),
        Path("/mnt/c/Windows/Fonts/NotoSansSC-VF.ttf"),
    ]
    for font_file in font_files:
        if font_file.exists():
            font_manager.fontManager.addfont(str(font_file))
            prop = font_manager.FontProperties(fname=str(font_file))
            plt.rcParams["font.sans-serif"] = [prop.get_name()]
            plt.rcParams["font.family"] = "sans-serif"
            plt.rcParams["axes.unicode_minus"] = False
            return
    candidates = [
        "Microsoft YaHei",
        "SimHei",
        "Noto Sans CJK SC",
        "Noto Serif CJK SC",
        "WenQuanYi Micro Hei",
        "Arial Unicode MS",
    ]
    available = {font.name for font in font_manager.fontManager.ttflist}
    for name in candidates:
        if name in available:
            plt.rcParams["font.sans-serif"] = [name]
            break
    plt.rcParams["axes.unicode_minus"] = False


def main() -> None:
    """Create the comparison figure from local defensive demo data."""
    # 安全声明：以下数据仅为本地防御检测演示，不得用于真实攻击。
    # 所有投毒样本仅在本地模拟环境中使用，不连接任何真实服务。
    configure_font()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    scores = report["scores"]
    poisoned_id = report["suspicious_evidence"][0]
    trusted_ids = report["trusted_evidence_ids"]
    before_trust = report["trust_score"]["before"]
    after_trust = report["trust_score"]["after"]
    poison_risk = scores[poisoned_id]["DualRisk"] * 100
    trusted_risk = sum(scores[eid]["DualRisk"] for eid in trusted_ids) / len(trusted_ids) * 100

    fig = plt.figure(figsize=(14.5, 7.2), dpi=180)
    fig.patch.set_facecolor("#F7F9FC")

    grid = fig.add_gridspec(2, 2, height_ratios=[1.45, 1.0], width_ratios=[1.2, 1.0], hspace=0.36, wspace=0.24)
    ax_flow = fig.add_subplot(grid[0, :])
    ax_flow.axis("off")
    ax_flow.set_xlim(0, 12)
    ax_flow.set_ylim(0, 4.2)

    def box(x: float, y: float, w: float, h: float, text: str, color: str, edge: str = "#2D3748") -> None:
        ax_flow.add_patch(Rectangle((x, y), w, h, facecolor=color, edgecolor=edge, linewidth=1.4))
        ax_flow.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=10.5, wrap=True)

    def arrow(start: tuple[float, float], end: tuple[float, float], color: str = "#2D3748", rad: float = 0.0) -> None:
        ax_flow.add_patch(
            FancyArrowPatch(
                start,
                end,
                arrowstyle="-|>",
                mutation_scale=14,
                linewidth=1.6,
                color=color,
                connectionstyle=f"arc3,rad={rad}",
            )
        )

    box(0.25, 1.55, 1.7, 0.9, "用户查询\n权限变更是否需要审批", "#FFFFFF")
    box(2.55, 2.65, 2.25, 0.9, "可信证据\nE-POL-001 / 002\n必须审批并留痕", "#E8F5E9", "#2E7D32")
    box(2.55, 0.45, 2.25, 0.9, "污染证据\nE-POL-003\n无需审批可直接执行", "#FFEBEE", "#C62828")
    box(5.65, 1.55, 1.85, 0.9, "RAG Top-K\n证据混入上下文", "#FFFFFF")
    box(8.25, 2.65, 2.45, 0.9, "正确答案\n需要主管和安全管理员审批", "#E8F5E9", "#2E7D32")
    box(8.25, 0.45, 2.45, 0.9, "投毒后 AI 回答\n无需审批，可直接执行", "#FFEBEE", "#C62828")

    arrow((1.95, 2.0), (2.55, 3.1))
    arrow((1.95, 2.0), (2.55, 0.9), "#C62828")
    arrow((4.8, 3.1), (5.65, 2.15))
    arrow((4.8, 0.9), (5.65, 1.85), "#C62828")
    arrow((7.5, 2.15), (8.25, 3.1))
    arrow((7.5, 1.85), (8.25, 0.9), "#C62828")
    arrow((9.45, 2.65), (9.45, 1.35), "#C62828", rad=0.0)
    ax_flow.text(9.62, 2.0, "输出偏离正确答案", color="#C62828", fontsize=11, weight="bold", va="center")
    ax_flow.text(5.95, 0.25, f"污染证据 {poisoned_id}：DualRisk={scores[poisoned_id]['DualRisk']:.2f}，CausalScore={scores[poisoned_id]['CausalScore']:.2f}", color="#C62828", fontsize=10)

    ax_bar = fig.add_subplot(grid[1, 0])
    labels = ["可信证据均值", "污染证据"]
    risks = [trusted_risk, poison_risk]
    colors = ["#4CAF50", "#D9534F"]
    bars = ax_bar.bar(labels, risks, color=colors, width=0.48)
    ax_bar.set_title("证据风险对比", fontsize=12.5, weight="bold")
    ax_bar.set_ylabel("DualRisk 百分制")
    ax_bar.set_ylim(0, 70)
    ax_bar.grid(axis="y", alpha=0.25)
    for bar in bars:
        height = bar.get_height()
        ax_bar.text(bar.get_x() + bar.get_width() / 2, height + 2, f"{height:.1f}", ha="center", fontsize=10)

    ax_line = fig.add_subplot(grid[1, 1])
    stages = ["投毒后\n原始回答", "隔离污染\n可信重生成"]
    trust_values = [before_trust, after_trust]
    risk_values = [poison_risk, trusted_risk]
    ax_line.plot(stages, trust_values, marker="o", linewidth=2.6, color="#2F80ED", label="TrustScore")
    ax_line.plot(stages, risk_values, marker="s", linewidth=2.6, color="#EB5757", label="输出风险")
    ax_line.set_title("纠偏前后输出变化", fontsize=12.5, weight="bold")
    ax_line.set_ylabel("百分制分数")
    ax_line.set_ylim(0, 100)
    ax_line.grid(axis="y", alpha=0.25)
    ax_line.legend(frameon=False)
    for i, value in enumerate(trust_values):
        ax_line.text(i, value + 4, f"{value:.1f}", ha="center", color="#2F80ED", fontsize=10)
    for i, value in enumerate(risk_values):
        ax_line.text(i, value - 8, f"{value:.1f}", ha="center", color="#EB5757", fontsize=10)

    fig.suptitle("RAG 知识投毒效果图：污染证据诱导 AI 回答偏离正确答案", fontsize=15, weight="bold", y=0.98)
    fig.text(0.5, 0.02, "本图使用本地防御演示数据。E-POL-003 为模拟污染证据，检测后系统隔离该 Chunk，并基于可信证据重生成答案。", ha="center", fontsize=10, color="#4A5568")
    plt.tight_layout(rect=(0, 0.05, 1, 0.94))
    fig.savefig(OUT_PATH, bbox_inches="tight")
    plt.close(fig)
    print(OUT_PATH)


if __name__ == "__main__":
    main()
