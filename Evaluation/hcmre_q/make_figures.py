"""Figures for the HCMRE-Q benchmark section of the proposal.

  python make_figures.py --results results --data data --fig ../../Documentation/figures
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

SURFACE, INK, INK2, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#e1e0d9", "#c3c2b7"
BLUE, ORANGE, GRAY = "#2a78d6", "#eb6834", "#b9b8b1"
SEQ = ["#f0efec", "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]

NAMES = {
    "random": "Ngẫu nhiên",
    "pg_fts": "PostgreSQL FTS (ts_rank_cd)",
    "prod_nodl": "Hệ thống hiện tại, nhánh không-DL",
    "prod_nodl_graph": "Hệ thống hiện tại, không-DL + Neo4j",
    "bm25_noaccent": "BM25 (bỏ dấu)",
    "bm25": "BM25 (giữ dấu)",
    "bm25_rule": "BM25 + ranker luật của hệ thống",
    "dense": "Dense Qwen3-Embedding (DL)",
    "prod_dl": "Hệ thống đầy đủ (DL)",
    "prod_dl_graph": "Hệ thống đầy đủ + Neo4j (DL)",
    "rrf_bm25_dense": "RRF(BM25, Dense) (DL)",
}
PRODUCTION = {"pg_fts", "prod_nodl", "prod_nodl_graph", "prod_dl", "prod_dl_graph"}


def style(ax, grid="x"):
    ax.set_facecolor(SURFACE)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(AXIS)
    ax.tick_params(colors=INK2, labelsize=9, length=0)
    if grid:
        ax.grid(axis=grid, color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)


def title(fig, ax, t, sub, path):
    ax.set_title(t, loc="left", fontsize=12, color=INK, fontweight="bold", pad=22)
    ax.text(0, 1.02, sub, transform=ax.transAxes, fontsize=9, color=INK2, va="bottom")
    fig.tight_layout()
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)


def main(a):
    res, data, fig_dir = Path(a.results), Path(a.data), Path(a.fig)
    fig_dir.mkdir(parents=True, exist_ok=True)
    s = json.load(open(res / "summary.json", encoding="utf-8"))
    test = pd.DataFrame(s["test"]).T
    ci = s["test_ndcg_ci95"]

    # --- baselines (test nDCG@10 with bootstrap CI)
    order = test["ndcg@10"].sort_values().index.tolist()
    fig, ax = plt.subplots(figsize=(8, 0.42 * len(order) + 1.4), dpi=160)
    fig.patch.set_facecolor(SURFACE)
    y = np.arange(len(order))
    colors = [ORANGE if k in PRODUCTION else (GRAY if k == "random" else BLUE) for k in order]
    ax.barh(y, test.loc[order, "ndcg@10"], height=0.55, color=colors)
    for yi, k in zip(y, order):
        lo, hi = ci[k]
        ax.hlines(yi, lo, hi, color=INK2, linewidth=1)
        ax.text(hi + 0.005, yi, f"{test.loc[k, 'ndcg@10']:.3f}".replace(".", ","), va="center", fontsize=8.5, color=INK)
    ax.set_yticks(y)
    ax.set_yticklabels([NAMES.get(k, k) for k in order], fontsize=9)
    ax.set_xlabel("nDCG@10 trên tập test (120 truy vấn); vạch đen = khoảng tin cậy bootstrap 95%", fontsize=9, color=INK2)
    style(ax)
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color=ORANGE, label="Đường xử lý của hệ thống hiện tại"),
                       Patch(color=BLUE, label="Baseline bổ sung")], frameon=False, fontsize=8, loc="lower right")
    dl_note = "" if s.get("dense_available") else " (chưa gồm hệ thống DL)"
    title(fig, ax, "Nhánh không-DL của hệ thống hiện tại đạt nDCG@10 dưới 0,1",
          "Benchmark HCMRE-Q, tập test, nhãn phân cấp 0/1/2" + dl_note, fig_dir / "fig_baselines_test.png")

    # --- parser slot accuracy heatmap (slot x style)
    m = pd.DataFrame(s["parser_slot_accuracy"]["by_slot_style"]).T
    counts = pd.DataFrame(s["parser_slot_accuracy"]["by_slot"]).T["count"]
    slot_vi = {"type": "Loại BĐS", "location": "Vị trí", "price": "Giá", "bedrooms": "Phòng ngủ", "area": "Diện tích",
               "amenity": "Tiện ích + khoảng cách", "aspect": "Đặc điểm mô tả", "legal": "Pháp lý",
               "furnishing": "Nội thất", "landmark": "Địa danh"}
    rows = ["type", "location", "price", "bedrooms", "area", "legal", "furnishing", "amenity", "aspect", "landmark"]
    m = m.loc[[r for r in rows if r in m.index], ["S1", "S2", "S3", "S4"]]
    fig, ax = plt.subplots(figsize=(7.2, 5.0), dpi=160)
    fig.patch.set_facecolor(SURFACE)
    cmap = matplotlib.colors.LinearSegmentedColormap.from_list("seq", SEQ)
    ax.imshow(m.values.astype(float), cmap=cmap, vmin=0, vmax=1, aspect="auto")
    for i in range(m.shape[0]):
        for j in range(m.shape[1]):
            v = m.values[i, j]
            if pd.isna(v):
                continue
            ax.text(j, i, f"{100 * v:.0f}%", ha="center", va="center", fontsize=9,
                    color="white" if v > 0.6 else INK)
    ax.set_xticks(range(4))
    ax.set_xticklabels(["S1 chuẩn", "S2 không dấu", "S3 viết tắt", "S4 hội thoại"], fontsize=9)
    ax.set_yticks(range(m.shape[0]))
    ax.set_yticklabels([f"{slot_vi[r]} (n={int(counts[r])})" for r in m.index], fontsize=9)
    ax.tick_params(colors=INK2, length=0)
    for sp in ax.spines.values():
        sp.set_visible(False)
    full = s["parser_slot_accuracy"]["query_fully_parsed"]
    title(fig, ax, "Parser luật trích đúng ràng buộc rất không đều",
          f"% ràng buộc RuleBasedQueryParser trích đúng (600 truy vấn); đúng toàn bộ: {100 * full:.1f}%".replace(".", ","),
          fig_dir / "fig_parser_slots.png")

    # --- exact-match count per query
    q = [json.loads(line) for line in open(data / "queries.jsonl", encoding="utf-8")]
    ne = np.array([x["n_exact"] for x in q])
    fig, ax = plt.subplots(figsize=(8, 3.4), dpi=160)
    fig.patch.set_facecolor(SURFACE)
    ax.hist(ne, bins=np.arange(0.5, 51.5, 2), color=BLUE, rwidth=0.85)
    ax.axvline(np.median(ne), color=INK, linewidth=1)
    ax.text(np.median(ne) + 0.6, ax.get_ylim()[1] * 0.9, f"trung vị = {np.median(ne):.0f}", fontsize=8.5, color=INK)
    ax.set_xlabel("Số tin 'khớp hoàn toàn' (nhãn 2) mỗi truy vấn", fontsize=9, color=INK2)
    ax.set_ylabel("Số truy vấn", fontsize=9, color=INK2)
    style(ax, "y")
    title(fig, ax, "Mỗi truy vấn có ít đáp án đúng trên 3.037 tin",
          "600 truy vấn HCMRE-Q; truy vấn có > 50 đáp án bị loại khi sinh để giữ độ phân biệt", fig_dir / "fig_benchmark_nexact.png")
    print("figures written to", fig_dir)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default="results")
    ap.add_argument("--data", default="data")
    ap.add_argument("--fig", default="../../Documentation/figures")
    main(ap.parse_args())
