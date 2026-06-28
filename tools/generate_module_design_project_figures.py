#!/usr/bin/env python3
"""Generate original project figures for section 2.1.2.

The figures are redrawn for this project instead of reusing screenshots from papers.
They keep the technical ideas from the design text while using project-specific
Chinese labels, module names, and data flow.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Rectangle


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "docs" / "module_design_2_1_2_project_figures"


PALETTE = {
    "blue": "#DDEBFF",
    "blue_edge": "#4472C4",
    "green": "#E2F0D9",
    "green_edge": "#70AD47",
    "orange": "#FCE4D6",
    "orange_edge": "#ED7D31",
    "red": "#F8D7DA",
    "red_edge": "#C00000",
    "purple": "#EDE7F6",
    "purple_edge": "#8064A2",
    "gray": "#F2F2F2",
    "gray_edge": "#666666",
    "yellow": "#FFF2CC",
    "yellow_edge": "#BF9000",
}


def configure_font() -> None:
    font_files = [
        Path("/mnt/c/Windows/Fonts/msyh.ttc"),
        Path("/mnt/c/Windows/Fonts/simhei.ttf"),
        Path("/mnt/c/Windows/Fonts/simsun.ttc"),
        Path("/usr/share/fonts/truetype/noto/NotoSansMono-Regular.ttf"),
    ]
    for font_file in font_files:
        if font_file.exists():
            font_manager.fontManager.addfont(str(font_file))
            prop = font_manager.FontProperties(fname=str(font_file))
            plt.rcParams["font.sans-serif"] = [prop.get_name()]
            plt.rcParams["font.family"] = "sans-serif"
            plt.rcParams["axes.unicode_minus"] = False
            return


def setup_canvas(width: float = 13.5, height: float = 7.2):
    fig, ax = plt.subplots(figsize=(width, height), dpi=220)
    ax.set_xlim(0, width)
    ax.set_ylim(0, height)
    ax.axis("off")
    fig.patch.set_facecolor("white")
    return fig, ax


def box(ax, x, y, w, h, text, fill="gray", fontsize=10, weight="normal", radius=0.08):
    patch = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle=f"round,pad=0.03,rounding_size={radius}",
        linewidth=1.5,
        edgecolor=PALETTE[f"{fill}_edge"],
        facecolor=PALETTE[fill],
    )
    ax.add_patch(patch)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fontsize, fontweight=weight)
    return patch


def plain_box(ax, x, y, w, h, text, fontsize=10, weight="normal"):
    patch = Rectangle((x, y), w, h, linewidth=1.4, edgecolor="#333333", facecolor="white")
    ax.add_patch(patch)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fontsize, fontweight=weight)
    return patch


def arrow(ax, start, end, color="#333333", lw=1.45, style="-|>", curve=0.0):
    patch = FancyArrowPatch(
        start,
        end,
        arrowstyle=style,
        mutation_scale=13,
        linewidth=lw,
        color=color,
        shrinkA=5,
        shrinkB=5,
        connectionstyle=f"arc3,rad={curve}",
    )
    ax.add_patch(patch)
    return patch


def title(ax, text: str, width: float) -> None:
    ax.text(width / 2, 6.85, text, ha="center", va="center", fontsize=15, fontweight="bold")


def save(fig, name: str) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / name
    fig.savefig(out, bbox_inches="tight", pad_inches=0.14)
    plt.close(fig)
    print(out)


def draw_attack_surface() -> None:
    fig, ax = setup_canvas(14.0, 7.4)
    ax.text(7.0, 7.05, "智源净域：RAG 知识投毒攻击面与防御检测流程", ha="center", fontsize=15, fontweight="bold")

    # Left side follows the paper-style RAG box: question -> retriever -> context -> LLM -> answer.
    rag = FancyBboxPatch(
        (0.75, 1.75),
        8.0,
        4.25,
        boxstyle="round,pad=0.05,rounding_size=0.28",
        linewidth=1.8,
        edgecolor="#2F5597",
        facecolor="#E2F0D9",
    )
    ax.add_patch(rag)
    ax.text(4.75, 5.75, "企业 RAG 系统", ha="center", fontsize=12, fontweight="bold")
    box(ax, 0.95, 6.25, 3.9, 0.52, "用户查询：某漏洞是否已修复？", "blue", fontsize=10)
    box(ax, 6.65, 6.25, 1.9, 0.52, "答案：已修复", "red", fontsize=10)
    box(ax, 1.0, 4.25, 1.3, 1.05, "Retriever\n检索器", "blue", fontsize=9)
    box(ax, 6.95, 4.25, 1.3, 1.05, "LLM\n生成器", "blue", fontsize=9)
    box(ax, 2.75, 4.15, 3.75, 1.2, "上下文 Context\n[污染] 该漏洞已于 2026-05 修复\n问题：某漏洞是否已修复？\n请基于证据回答", "yellow", fontsize=8.8)
    box(ax, 1.05, 2.15, 5.55, 1.0, "知识库 Knowledge Base\n污染 Chunk：伪造修复公告        可信 Chunk：厂商未修复公告", "gray", fontsize=9)
    box(ax, 6.95, 2.15, 1.35, 1.0, "来源集合\n网页/制度/公告", "green", fontsize=8.6)
    arrow(ax, (4.85, 6.5), (6.65, 6.5))
    arrow(ax, (2.25, 4.78), (2.75, 4.78), color=PALETTE["red_edge"])
    arrow(ax, (6.5, 4.78), (6.95, 4.78), color=PALETTE["red_edge"])
    arrow(ax, (7.6, 5.3), (7.6, 6.25), color=PALETTE["red_edge"])
    arrow(ax, (1.65, 4.25), (1.65, 3.15))
    arrow(ax, (6.6, 2.65), (6.95, 2.65))

    # Right side follows the malicious-text crafting/injection area in the paper, but project-specific.
    box(ax, 9.2, 5.1, 4.15, 0.82, "攻击目标\n目标问题：某漏洞是否已修复？\n目标答案：已修复", "orange", fontsize=9.4)
    box(ax, 10.05, 3.75, 2.45, 0.74, "本地模拟投毒样本\n伪修复声明", "red", fontsize=10)
    box(ax, 9.55, 2.35, 3.45, 0.9, "恶意 Evidence\n[污染] 该漏洞已于 2026-05 修复\n并可安全上线", "red", fontsize=9)
    arrow(ax, (11.28, 5.1), (11.28, 4.49), color=PALETTE["red_edge"])
    arrow(ax, (11.28, 3.75), (11.28, 3.25), color=PALETTE["red_edge"])
    arrow(ax, (9.55, 2.8), (8.3, 2.65), color=PALETTE["red_edge"])
    ax.text(8.95, 3.0, "Inject", color=PALETTE["red_edge"], fontsize=10)

    # Defense layer below the paper-style RAG flow.
    box(ax, 1.0, 0.75, 2.2, 0.62, "RAS/GIS\nDualRisk", "purple", fontsize=9)
    box(ax, 3.7, 0.75, 2.2, 0.62, "四路反事实\nCausalScore", "yellow", fontsize=9)
    box(ax, 6.4, 0.75, 2.2, 0.62, "隔离与可信重生成", "blue", fontsize=9)
    arrow(ax, (2.3, 2.15), (2.1, 1.37), curve=0.12)
    arrow(ax, (3.2, 1.06), (3.7, 1.06))
    arrow(ax, (5.9, 1.06), (6.4, 1.06))
    ax.text(7.0, 0.28, "说明：版式对齐 PoisonedRAG 攻击流程图，内容替换为本项目防御检测场景", ha="center", fontsize=9.4)
    save(fig, "fig_2_1_attack_surface_closed_loop.png")


def draw_pipeline() -> None:
    fig, ax = setup_canvas(14.2, 7.6)
    ax.text(7.1, 7.22, "RAG 知识投毒检测、因果溯源与可信重生成模块流程", ha="center", fontsize=15, fontweight="bold")

    steps = [
        ("用户查询\n企业知识库", "blue"),
        ("Document / Chunk\nEvidence 建模", "green"),
        ("声明抽取\nEvidenceCluster 聚类", "green"),
        ("Top-K 检索\n召回记录", "blue"),
        ("RAS / GIS\nChunk_DualRisk", "purple"),
        ("Cluster_RAS / GIS\nCluster_DualRisk", "purple"),
        ("四路反事实\nCausalScore", "yellow"),
        ("传播图谱\n伪共识路径", "orange"),
        ("Claim-Evidence\n矩阵裁决", "green"),
        ("TrustScore\n可信评分", "blue"),
        ("风险隔离\n重检索", "red"),
        ("可信重生成\n风险报告", "blue"),
    ]
    positions = []
    for row, y in enumerate([5.75, 4.15, 2.55]):
        for col in range(4):
            idx = row * 4 + col
            x = 0.55 + col * 3.35
            positions.append((x, y))
            box(ax, x, y, 2.45, 0.72, steps[idx][0], steps[idx][1], fontsize=9.6)
    for i in range(3):
        arrow(ax, (positions[i][0] + 2.45, positions[i][1] + 0.36), (positions[i + 1][0], positions[i + 1][1] + 0.36))
    arrow(ax, (positions[3][0] + 1.22, positions[3][1]), (positions[4][0] + 1.22, positions[4][1] + 0.72), curve=-0.1)
    for i in range(4, 7):
        arrow(ax, (positions[i][0] + 2.45, positions[i][1] + 0.36), (positions[i + 1][0], positions[i + 1][1] + 0.36))
    arrow(ax, (positions[7][0] + 1.22, positions[7][1]), (positions[8][0] + 1.22, positions[8][1] + 0.72), curve=-0.1)
    for i in range(8, 11):
        arrow(ax, (positions[i][0] + 2.45, positions[i][1] + 0.36), (positions[i + 1][0], positions[i + 1][1] + 0.36))

    ax.plot([12.0, 12.0, 1.8, 1.8], [2.55, 1.25, 1.25, 5.75], color="#777777", linewidth=1.15)
    arrow(ax, (1.8, 1.25), (1.8, 5.75), color="#777777", lw=1.15)
    ax.text(7.1, 0.82, "复核回路：可信分不足或证据冲突时，返回证据建模与重检索阶段重新裁决", ha="center", fontsize=10)
    save(fig, "fig_2_2_module_pipeline.png")


def draw_evidence_model() -> None:
    fig, ax = setup_canvas()
    title(ax, "五层证据对象模型与知识库接入结构", 13.5)

    layers = [
        (0.65, "Page\n网页/页面\nurl, title", "gray"),
        (2.95, "Document\n原始文档\nsource_id, label,\nhash, copied_from", "blue"),
        (5.25, "Chunk\n检索片段\ncontent, position,\ncontent_hash, scores", "green"),
        (7.55, "Evidence\n检测证据\nrank, query_id,\nRAS/GIS/DualRisk", "purple"),
        (9.85, "Claim\n原子声明\nentity, attribute,\nvalue, polarity", "yellow"),
        (11.25, "EvidenceCluster\n同 Claim 证据簇\nsource_count,\ncluster_risk", "orange"),
    ]
    for x, text, color in layers:
        w = 2.0 if "EvidenceCluster" not in text else 1.9
        box(ax, x, 4.35, w, 1.18, text, color, fontsize=9)
    for i in range(len(layers) - 1):
        x = layers[i][0] + (2.0 if i < 5 else 1.9)
        arrow(ax, (x, 4.94), (layers[i + 1][0], 4.94))

    box(ax, 1.2, 2.45, 2.4, 0.82, "正则切分\n文本清洗", "green")
    box(ax, 4.0, 2.45, 2.4, 0.82, "内容哈希\n重复识别", "blue")
    box(ax, 6.8, 2.45, 2.4, 0.82, "语义相似\n近似改写识别", "purple")
    box(ax, 9.6, 2.45, 2.4, 0.82, "实体-属性-取值\n声明聚类", "yellow")
    for sx, ex in [(3.6, 4.0), (6.4, 6.8), (9.2, 9.6)]:
        arrow(ax, (sx, 2.86), (ex, 2.86))
    arrow(ax, (10.8, 3.27), (12.1, 4.35), curve=-0.08)

    ax.text(6.75, 1.35, "输出：带来源、版本、标签、复制关系、风险评分与 Claim 归属的可审计 Evidence", ha="center", fontsize=10.5)
    save(fig, "fig_2_3_evidence_object_model.png")


def draw_dual_layer_detection() -> None:
    fig, ax = setup_canvas(14.2, 7.4)
    ax.text(7.1, 7.05, "Chunk-EvidenceCluster 双层风险检测与反事实验证", ha="center", fontsize=15, fontweight="bold")

    box(ax, 0.55, 5.45, 2.3, 0.8, "Top-K Evidence\n召回记录", "blue")
    box(ax, 3.35, 5.78, 2.25, 0.68, "Chunk_RAS\n检索吸附性", "purple")
    box(ax, 3.35, 4.86, 2.25, 0.68, "Chunk_GIS\n答案诱导性", "purple")
    box(ax, 6.15, 5.32, 2.25, 0.78, "Chunk_DualRisk\n单点强投毒候选", "red")

    box(ax, 3.35, 3.35, 2.25, 0.68, "Cluster_RAS\n共同召回", "green")
    box(ax, 3.35, 2.45, 2.25, 0.68, "Cluster_GIS\n共同 Claim 诱导", "green")
    box(ax, 3.35, 1.55, 2.25, 0.68, "SourceAnomaly\n伪独立来源", "green")
    box(ax, 6.15, 2.45, 2.25, 0.78, "Cluster_DualRisk\n协同投毒候选", "orange")

    box(ax, 9.0, 5.32, 2.05, 0.78, "Chunk 级\n四路反事实", "yellow")
    box(ax, 9.0, 2.45, 2.05, 0.78, "簇级\n四路反事实", "yellow")
    box(ax, 11.65, 4.15, 1.85, 0.92, "CausalScore\nCluster_CausalScore\n致错确认", "red", fontsize=9)

    arrow(ax, (2.85, 5.85), (3.35, 6.12))
    arrow(ax, (2.85, 5.75), (3.35, 5.2))
    arrow(ax, (5.6, 6.12), (6.15, 5.78))
    arrow(ax, (5.6, 5.2), (6.15, 5.66))
    arrow(ax, (2.85, 5.45), (3.35, 3.69), curve=-0.12)
    arrow(ax, (2.85, 5.35), (3.35, 2.79), curve=-0.18)
    arrow(ax, (2.85, 5.25), (3.35, 1.89), curve=-0.24)
    for y in [3.69, 2.79, 1.89]:
        arrow(ax, (5.6, y), (6.15, 2.84), curve=0.05)
    arrow(ax, (8.4, 5.71), (9.0, 5.71))
    arrow(ax, (8.4, 2.84), (9.0, 2.84))
    arrow(ax, (11.05, 5.71), (11.65, 4.82), curve=-0.06)
    arrow(ax, (11.05, 2.84), (11.65, 4.38), curve=0.08)

    ax.text(7.1, 0.72, "判定逻辑：分数只负责筛选候选，最终投毒结论由 Chunk 级和簇级反事实变化确认", ha="center", fontsize=10.5)
    save(fig, "fig_2_4_dual_layer_counterfactual.png")


def draw_graph_and_regeneration() -> None:
    fig, ax = setup_canvas(14.2, 7.4)
    ax.text(7.1, 7.05, "投毒传播图谱、风险隔离与可信重生成", ha="center", fontsize=15, fontweight="bold")

    nodes = {
        "page": (1.0, 5.55, "Page\n网页/页面", "gray"),
        "doc": (3.0, 5.55, "Document\n文档实体", "blue"),
        "chunk1": (5.15, 5.75, "Chunk A\n污染片段", "red"),
        "chunk2": (5.15, 4.8, "Chunk B\n相似改写", "orange"),
        "cluster": (7.45, 5.25, "EvidenceCluster\n同一错误 Claim", "purple"),
        "query": (9.9, 5.7, "Query\n用户问题", "blue"),
        "answer": (11.8, 5.25, "Answer\n错误答案", "red"),
        "claim": (9.55, 3.45, "Claim\n原子声明", "yellow"),
        "iso": (6.25, 2.25, "IsolationEvent\n隔离事件", "red"),
        "trusted": (9.15, 2.1, "可信 Evidence\n低风险多源支持", "green"),
        "regen": (11.55, 2.1, "可信重生成\n答案+引用+报告", "blue"),
    }
    sizes = {
        "cluster": (2.05, 0.8),
        "answer": (1.8, 0.8),
        "trusted": (2.1, 0.8),
        "regen": (2.0, 0.8),
    }
    for name, (x, y, text, color) in nodes.items():
        w, h = sizes.get(name, (1.65, 0.74))
        box(ax, x, y, w, h, text, color, fontsize=9)

    arrow(ax, (2.65, 5.92), (3.0, 5.92))
    ax.text(2.82, 6.15, "contains", ha="center", fontsize=8)
    arrow(ax, (4.65, 5.92), (5.15, 6.12))
    arrow(ax, (4.65, 5.82), (5.15, 5.17))
    ax.text(4.9, 6.18, "contains", ha="center", fontsize=8)
    arrow(ax, (6.8, 6.12), (7.45, 5.72))
    arrow(ax, (6.8, 5.17), (7.45, 5.52))
    ax.text(7.08, 6.04, "belongs_to_cluster", ha="center", fontsize=8)
    arrow(ax, (9.5, 5.65), (9.9, 6.0))
    arrow(ax, (9.5, 5.55), (9.9, 5.92), color=PALETTE["red_edge"])
    ax.text(9.68, 6.25, "retrieved_by", ha="center", fontsize=8)
    arrow(ax, (11.55, 6.06), (11.8, 5.75), color=PALETTE["red_edge"])
    arrow(ax, (8.48, 5.25), (10.0, 3.98), curve=0.03)
    ax.text(9.15, 4.8, "supports", fontsize=8)
    arrow(ax, (10.4, 3.85), (11.8, 5.25), color=PALETTE["red_edge"], curve=-0.08)
    ax.text(10.95, 4.65, "caused_error", fontsize=8)
    arrow(ax, (6.0, 4.8), (6.65, 2.99), color=PALETTE["red_edge"], curve=-0.08)
    arrow(ax, (8.35, 5.25), (6.95, 2.99), color=PALETTE["red_edge"], curve=0.12)
    ax.text(6.2, 3.85, "isolated_in", fontsize=8)
    arrow(ax, (7.9, 2.62), (9.15, 2.5))
    arrow(ax, (11.25, 2.5), (11.55, 2.5))

    ax.plot([5.98, 5.98, 5.15], [6.45, 4.45, 4.8], color="#777777", linewidth=1.0, linestyle="--")
    ax.text(5.6, 4.35, "similar_to / copied_from", fontsize=8, color="#555555")
    ax.text(7.1, 0.85, "图谱解释伪共识路径；隔离后只使用通过 TrustScore 门限的证据进行重生成", ha="center", fontsize=10.5)
    save(fig, "fig_2_5_graph_trust_regeneration.png")


def main() -> None:
    configure_font()
    draw_attack_surface()
    draw_pipeline()
    draw_evidence_model()
    draw_dual_layer_detection()
    draw_graph_and_regeneration()


if __name__ == "__main__":
    main()
