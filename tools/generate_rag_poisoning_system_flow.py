#!/usr/bin/env python3
"""Generate a black-white Visio-style module flowchart for the RAG poisoning system."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import FancyArrowPatch, Rectangle


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "docs" / "implementation_assets"
OUT_PATH = OUT_DIR / "rag_poisoning_system_flow_bw.png"


def configure_font() -> None:
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


def add_box(ax, xy, text: str, width: float = 2.25, height: float = 0.72) -> None:
    x, y = xy
    rect = Rectangle((x, y), width, height, linewidth=1.6, edgecolor="black", facecolor="white")
    ax.add_patch(rect)
    ax.text(x + width / 2, y + height / 2, text, ha="center", va="center", fontsize=10)


def add_arrow(ax, start, end) -> None:
    arrow = FancyArrowPatch(
        start,
        end,
        arrowstyle="-|>",
        mutation_scale=12,
        linewidth=1.4,
        color="black",
        shrinkA=4,
        shrinkB=4,
    )
    ax.add_patch(arrow)


def main() -> None:
    configure_font()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(12.5, 6.3), dpi=200)
    ax.set_xlim(0, 12.5)
    ax.set_ylim(0, 6.3)
    ax.axis("off")
    fig.patch.set_facecolor("white")

    boxes = {
        "input": ((0.4, 4.85), "用户查询 q\n企业知识库 D"),
        "evidence": ((3.0, 4.85), "Document / Chunk\nEvidence 建模"),
        "retrieval": ((5.6, 4.85), "Top-K 检索\n候选 Evidence"),
        "detect": ((8.2, 4.85), "RAS / GIS\nDualRisk 检测"),
        "cf": ((8.2, 3.35), "四路反事实\nCausalScore"),
        "graph": ((5.6, 3.35), "投毒传播图谱\n路径溯源"),
        "isolate": ((3.0, 3.35), "Chunk 隔离\n相似副本排除"),
        "rerank": ((0.4, 3.35), "风险感知\n重检索"),
        "trust": ((3.0, 1.85), "声明证据矩阵\nTrustScore"),
        "regen": ((5.6, 1.85), "可信重生成\n引用绑定"),
        "report": ((8.2, 1.85), "结构化风险报告\n处置建议"),
    }

    for xy, text in boxes.values():
        add_box(ax, xy, text)

    add_arrow(ax, (2.65, 5.21), (3.0, 5.21))
    add_arrow(ax, (5.25, 5.21), (5.6, 5.21))
    add_arrow(ax, (7.85, 5.21), (8.2, 5.21))
    add_arrow(ax, (9.33, 4.85), (9.33, 4.07))
    add_arrow(ax, (8.2, 3.71), (7.85, 3.71))
    add_arrow(ax, (5.6, 3.71), (5.25, 3.71))
    add_arrow(ax, (3.0, 3.71), (2.65, 3.71))
    add_arrow(ax, (1.53, 3.35), (3.0, 2.45))
    add_arrow(ax, (5.25, 2.21), (5.6, 2.21))
    add_arrow(ax, (7.85, 2.21), (8.2, 2.21))

    # Feedback loop from report back to isolation/retrieval, drawn as a Visio-style elbow.
    ax.plot([9.33, 9.33, 1.53, 1.53], [1.85, 0.85, 0.85, 3.35], color="black", linewidth=1.2)
    add_arrow(ax, (1.53, 0.85), (1.53, 3.35))
    ax.text(5.5, 0.55, "闭环复核：若 TrustScore 未达标，则返回隔离与重检索阶段", ha="center", fontsize=9)

    ax.text(
        6.25,
        6.0,
        "融合 RAG 知识投毒因果验证的信息污染溯源纠偏系统模块流程图",
        ha="center",
        va="center",
        fontsize=13,
        fontweight="bold",
    )

    fig.savefig(OUT_PATH, bbox_inches="tight", pad_inches=0.15)
    plt.close(fig)
    print(OUT_PATH)


if __name__ == "__main__":
    main()
