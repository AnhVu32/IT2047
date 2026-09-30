"""Sinh trang HTML tự-chứa visualize Knowledge Graph + thống kê + eval.

    cd gen_user_data && python visualize_graph.py   ->  graph_viz.html

Vì KG đầy đủ có 7k+ node / 33k+ edge (quá dày để vẽ), trang gồm:
  1. Sơ đồ SCHEMA (meta-graph): các loại node & quan hệ — SVG tĩnh.
  2. SUBGRAPH mẫu: vài user + interaction + listing + location/amenity, layout
     bằng networkx spring_layout (seed), bake toạ độ vào SVG (không cần JS).
  3. Biểu đồ thống kê: phân bố loại node / loại edge (bar chart SVG).
  4. Bảng + bar chart kết quả eval.

Màu theo bảng palette đã validate (dataviz skill), có secondary encoding
(kích thước node + nhãn + legend) nên định danh không chỉ dựa vào màu.
"""
from __future__ import annotations

import json
import os
from collections import Counter, defaultdict

import networkx as nx

from schemas import Interaction, Listing, UserProfile

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "data")
OUT = os.path.join(HERE, "graph_viz.html")

# Palette (light, dark) theo references/palette.md — đã chạy validator.
NODE_COLORS = {
    "User": ("#2a78d6", "#3987e5"),
    "Listing": ("#eb6834", "#d95926"),
    "Location": ("#1baf7a", "#199e70"),
    "Amenity": ("#e87ba4", "#d55181"),
    "Intent": ("#008300", "#008300"),
    "Query": ("#eda100", "#c98500"),
}
NODE_RADIUS = {"User": 13, "Listing": 8, "Location": 10, "Amenity": 7,
               "Intent": 11, "Query": 5}

ACTION_EDGE = {"view": "VIEWED", "save": "SAVED", "share": "SHARED", "contact": "CONTACTED"}
SAMPLE_USER_IDS = None  # None -> tự chọn theo segment
N_SAMPLE_USERS = 5
MAX_INTER_PER_USER = 4
MAX_AMENITY_PER_LISTING = 2


def _load(name, model):
    with open(os.path.join(DATA_DIR, name), encoding="utf-8") as f:
        return [model(**row) for row in json.load(f)]


# ---------------------------------------------------------------------------
# Thống kê toàn đồ thị (đọc từ kg/edges.csv nếu có, nếu không tự đếm)
# ---------------------------------------------------------------------------
def full_graph_stats(users, listings, interactions):
    node_counts = Counter()
    node_counts["User"] = len(users)
    node_counts["Listing"] = len({l.listing_id for l in listings})
    node_counts["Location"] = len({l.district for l in listings})
    amen = set()
    for l in listings:
        amen |= {f for f, v in l.features.items() if v}
    node_counts["Amenity"] = len(amen)
    node_counts["Intent"] = len({u.primary_intent for u in users})
    node_counts["Query"] = len(interactions)

    edge_counts = Counter()
    for l in listings:
        edge_counts["LOCATED_IN"] += 1
        edge_counts["HAS_AMENITY"] += sum(1 for v in l.features.values() if v)
    for u in users:
        edge_counts["HAS_INTENT"] += 1
        edge_counts["PREFERS_DISTRICT"] += len(u.explicit_preferences.preferred_districts)
        edge_counts["LIKES_AMENITY"] += len(u.explicit_preferences.liked_amenities)
    for it in interactions:
        edge_counts[ACTION_EDGE[it.action_type]] += 1
        edge_counts["SEARCHED"] += 1
    return node_counts, edge_counts


# ---------------------------------------------------------------------------
# Subgraph mẫu
# ---------------------------------------------------------------------------
def build_sample_graph(users, listings, interactions):
    listing_by_id = {l.listing_id: l for l in listings}
    inter_by_user = defaultdict(list)
    for it in interactions:
        inter_by_user[it.user_id].append(it)

    # chọn user đa dạng segment, ưu tiên user có action tích cực
    if SAMPLE_USER_IDS:
        chosen = SAMPLE_USER_IDS
    else:
        by_seg = defaultdict(list)
        for u in users:
            by_seg[u.segment].append(u)
        chosen = []
        segs = list(by_seg)
        i = 0
        while len(chosen) < N_SAMPLE_USERS and any(by_seg.values()):
            seg = segs[i % len(segs)]
            if by_seg[seg]:
                chosen.append(by_seg[seg].pop(0).user_id)
            i += 1

    user_by_id = {u.user_id: u for u in users}
    G = nx.Graph()
    meta = {}  # node -> (label, display)

    def node(nid, label, display):
        if nid not in meta:
            meta[nid] = (label, display)
            G.add_node(nid)

    edge_styles = {}  # (a,b) -> (rel, weight)

    for uid in chosen:
        u = user_by_id[uid]
        node(f"U:{uid}", "User", uid)
        node(f"I:{u.primary_intent}", "Intent", u.primary_intent)
        G.add_edge(f"U:{uid}", f"I:{u.primary_intent}")
        edge_styles[(f"U:{uid}", f"I:{u.primary_intent}")] = ("HAS_INTENT", 1.0)

        # interaction (ưu tiên action mạnh)
        inters = sorted(inter_by_user.get(uid, []),
                        key=lambda x: x.implicit_score, reverse=True)[:MAX_INTER_PER_USER]
        for it in inters:
            l = listing_by_id.get(it.listing_id)
            if not l:
                continue
            ln = f"L:{l.listing_id}"
            node(ln, "Listing", str(l.listing_id))
            rel = ACTION_EDGE[it.action_type]
            G.add_edge(f"U:{uid}", ln)
            edge_styles[(f"U:{uid}", ln)] = (rel, it.implicit_score)
            # location
            loc = f"Loc:{l.district}"
            node(loc, "Location", l.district)
            G.add_edge(ln, loc)
            edge_styles[(ln, loc)] = ("LOCATED_IN", 0.6)
            # vài amenity
            feats = [f for f, v in l.features.items() if v][:MAX_AMENITY_PER_LISTING]
            for f in feats:
                an = f"A:{f}"
                node(an, "Amenity", f)
                G.add_edge(ln, an)
                edge_styles[(ln, an)] = ("HAS_AMENITY", 0.4)
    return G, meta, edge_styles


def layout_svg(G, meta, edge_styles, width=940, height=640):
    pos = nx.spring_layout(G, seed=42, k=1.8 / (len(G) ** 0.5), iterations=200)
    xs = [p[0] for p in pos.values()]
    ys = [p[1] for p in pos.values()]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    pad = 60

    def sx(x):
        return pad + (x - minx) / (maxx - minx + 1e-9) * (width - 2 * pad)

    def sy(y):
        return pad + (y - miny) / (maxy - miny + 1e-9) * (height - 2 * pad)

    # edges
    edge_svg = []
    for a, b in G.edges():
        rel, w = edge_styles.get((a, b)) or edge_styles.get((b, a)) or ("", 0.5)
        strong = rel in ("CONTACTED", "SAVED", "SHARED")
        sw = 2.2 if strong else (1.3 if rel in ("VIEWED", "HAS_INTENT") else 0.8)
        cls = "edge strong" if strong else "edge"
        edge_svg.append(
            f'<line class="{cls}" x1="{sx(pos[a][0]):.1f}" y1="{sy(pos[a][1]):.1f}" '
            f'x2="{sx(pos[b][0]):.1f}" y2="{sy(pos[b][1]):.1f}" stroke-width="{sw}">'
            f'<title>{rel}</title></line>')

    # nodes
    node_svg = []
    for n in G.nodes():
        label, disp = meta[n]
        r = NODE_RADIUS[label]
        x, y = sx(pos[n][0]), sy(pos[n][1])
        show_label = label in ("User", "Location", "Intent")
        lbl = (f'<text class="nlabel" x="{x:.1f}" y="{y - r - 4:.1f}">{disp}</text>'
               if show_label else "")
        node_svg.append(
            f'<g class="node {label}"><circle cx="{x:.1f}" cy="{y:.1f}" r="{r}">'
            f'<title>{label}: {disp}</title></circle>{lbl}</g>')
    return "".join(edge_svg), "".join(node_svg), width, height


# ---------------------------------------------------------------------------
# Bar chart SVG (ngang, có nhãn trực tiếp)
# ---------------------------------------------------------------------------
def hbar_chart(counts: dict, color_role: str, width=440, bar_h=26, gap=10, unit=""):
    items = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    maxv = max(counts.values()) if counts else 1
    label_w, val_w, pad = 130, 60, 8
    plot_w = width - label_w - val_w
    height = len(items) * (bar_h + gap) + gap
    rows = []
    for i, (name, val) in enumerate(items):
        y = gap + i * (bar_h + gap)
        bw = max(2, plot_w * val / maxv)
        rows.append(
            f'<text class="clabel" x="{label_w - pad}" y="{y + bar_h/2:.1f}" text-anchor="end">{name}</text>'
            f'<rect class="bar {color_role}" x="{label_w}" y="{y}" width="{bw:.1f}" height="{bar_h}" rx="4"/>'
            f'<text class="cval" x="{label_w + bw + 6:.1f}" y="{y + bar_h/2:.1f}">{val:,}{unit}</text>')
    return f'<svg viewBox="0 0 {width} {height}" class="chart" role="img">{"".join(rows)}</svg>'


def grouped_eval_chart(results, metrics, width=680, group_gap=26, bar_h=18):
    # results: {rec: {metric: val}}; grouped by metric, bars = recommenders
    recs = list(results)
    rec_role = {r: role for r, role in zip(recs, ["s1", "s2", "s3", "s4"])}
    label_w, pad = 110, 8
    plot_w = width - label_w - 60
    row_h = len(recs) * (bar_h + 3)
    height = len(metrics) * (row_h + group_gap) + group_gap
    maxv = max((results[r].get(m, 0) for r in recs for m in metrics), default=1) or 1
    out, y = [], group_gap
    for m in metrics:
        out.append(f'<text class="mlabel" x="{pad}" y="{y - 6}">{m}</text>')
        for r in recs:
            v = results[r].get(m, 0)
            bw = max(2, plot_w * v / maxv)
            out.append(
                f'<rect class="bar {rec_role[r]}" x="{label_w}" y="{y}" width="{bw:.1f}" height="{bar_h}" rx="3"><title>{r}: {v}</title></rect>'
                f'<text class="cval" x="{label_w + bw + 6:.1f}" y="{y + bar_h/2:.1f}">{v}</text>')
            y += bar_h + 3
        y += group_gap
    legend = " ".join(
        f'<span class="lg"><i class="sw {rec_role[r]}"></i>{r}</span>' for r in recs)
    svg = f'<svg viewBox="0 0 {width} {height}" class="chart" role="img">{"".join(out)}</svg>'
    return svg, legend


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------
def render_html(node_counts, edge_counts, edges_svg, nodes_svg, gw, gh,
                eval_blob):
    node_bar = hbar_chart(dict(node_counts), "s1")
    edge_bar = hbar_chart(dict(edge_counts), "s3")
    legend_items = "".join(
        f'<span class="lg"><i class="dot {lbl}"></i>{lbl}</span>' for lbl in NODE_COLORS)

    eval_section = ""
    if eval_blob:
        res = {r: {k: v for k, v in m.items() if k not in ("engine",)}
               for r, m in eval_blob["results"].items()}
        metrics = ["NDCG@10", "Recall@10", "HitRate@10", "MAP@10", "Precision@10"]
        chart, elegend = grouped_eval_chart(res, metrics)
        engine = next(iter(eval_blob["results"].values())).get("engine", "")
        eval_section = f"""
  <h2>4 · Kết quả đánh giá</h2>
  <div class="card">
    <p class="sub">Engine: <code>{engine}</code> · K={eval_blob.get('k')} · sampled-negatives (N={eval_blob.get('num_neg_samples')}). MRR bỏ khỏi biểu đồ vì repo chuẩn hoá khác thang.</p>
    <div class="legend">{elegend}</div>
    <div class="chart-wrap">{chart}</div>
  </div>"""

    # node color CSS
    light_vars = "\n".join(f"    --c-{k.lower()}: {v[0]};" for k, v in NODE_COLORS.items())
    dark_vars = "\n".join(f"    --c-{k.lower()}: {v[1]};" for k, v in NODE_COLORS.items())
    node_fill_css = "\n".join(
        f"  .node.{k} circle {{ fill: var(--c-{k.lower()}); }}" for k in NODE_COLORS)
    dot_css = "\n".join(
        f"  .dot.{k} {{ background: var(--c-{k.lower()}); }}" for k in NODE_COLORS)

    return f"""<!doctype html>
<html lang="vi"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Knowledge Graph — Visualize</title>
<style>
  :root {{
    color-scheme: light;
    --surface: #fcfcfb; --plane: #f9f9f7; --text: #0b0b0b; --text2: #52514e;
    --muted: #898781; --grid: #e1e0d9; --border: rgba(11,11,11,.10);
    --edge: #c7c6bf; --edge-strong: #52514e;
    --s1: #2a78d6; --s2: #eb6834; --s3: #1baf7a; --s4: #e87ba4;
{light_vars}
  }}
  @media (prefers-color-scheme: dark) {{ :root:where(:not([data-theme="light"])) {{
    color-scheme: dark;
    --surface: #1a1a19; --plane: #0d0d0d; --text: #fff; --text2: #c3c2b7;
    --muted: #898781; --grid: #2c2c2a; --border: rgba(255,255,255,.10);
    --edge: #3a3a37; --edge-strong: #c3c2b7;
    --s1: #3987e5; --s2: #d95926; --s3: #199e70; --s4: #d55181;
{dark_vars}
  }} }}
  :root[data-theme="dark"] {{
    color-scheme: dark;
    --surface: #1a1a19; --plane: #0d0d0d; --text: #fff; --text2: #c3c2b7;
    --muted: #898781; --grid: #2c2c2a; --border: rgba(255,255,255,.10);
    --edge: #3a3a37; --edge-strong: #c3c2b7;
    --s1: #3987e5; --s2: #d95926; --s3: #199e70; --s4: #d55181;
{dark_vars}
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; background: var(--plane); color: var(--text);
    font: 15px/1.6 system-ui, -apple-system, "Segoe UI", sans-serif; }}
  .wrap {{ max-width: 1000px; margin: 0 auto; padding: 36px 22px 70px; }}
  h1 {{ font-size: 24px; margin: 0 0 4px; letter-spacing: -.01em; }}
  h2 {{ font-size: 18px; margin: 34px 0 6px; }}
  .sub {{ color: var(--text2); font-size: 13.5px; margin: 2px 0 0; }}
  code {{ background: var(--grid); padding: 1px 5px; border-radius: 4px; font-size: 12.5px; }}
  .card {{ background: var(--surface); border: 1px solid var(--border);
    border-radius: 12px; padding: 18px 20px; margin: 14px 0; }}
  .legend {{ display: flex; flex-wrap: wrap; gap: 14px; margin: 6px 0 14px; font-size: 13px; color: var(--text2); }}
  .lg {{ display: inline-flex; align-items: center; gap: 6px; }}
  .dot {{ width: 12px; height: 12px; border-radius: 50%; display: inline-block; }}
  .sw {{ width: 12px; height: 12px; border-radius: 3px; display: inline-block; }}
  .sw.s1 {{ background: var(--s1); }} .sw.s2 {{ background: var(--s2); }}
  .sw.s3 {{ background: var(--s3); }} .sw.s4 {{ background: var(--s4); }}
{dot_css}
  .graph-wrap {{ overflow-x: auto; }}
  svg.graph {{ width: 100%; height: auto; display: block; background: var(--surface); border-radius: 8px; }}
  .edge {{ stroke: var(--edge); }}
  .edge.strong {{ stroke: var(--edge-strong); }}
  .node circle {{ stroke: var(--surface); stroke-width: 2; cursor: pointer; transition: r .1s; }}
  .node:hover circle {{ stroke: var(--text); stroke-width: 2.5; }}
  .node.User circle, .node.Intent circle {{ stroke-width: 2.5; }}
{node_fill_css}
  .nlabel {{ font-size: 10.5px; fill: var(--text); text-anchor: middle; font-weight: 600;
    paint-order: stroke; stroke: var(--surface); stroke-width: 3px; }}
  .chart-wrap {{ overflow-x: auto; }}
  svg.chart {{ max-width: 100%; height: auto; }}
  .chart .bar.s1 {{ fill: var(--s1); }} .chart .bar.s2 {{ fill: var(--s2); }}
  .chart .bar.s3 {{ fill: var(--s3); }} .chart .bar.s4 {{ fill: var(--s4); }}
  .clabel {{ fill: var(--text2); font-size: 12px; dominant-baseline: middle; }}
  .cval {{ fill: var(--text); font-size: 11.5px; dominant-baseline: middle; font-variant-numeric: tabular-nums; }}
  .mlabel {{ fill: var(--text); font-size: 12.5px; font-weight: 600; }}
  .grid2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
  @media (max-width: 720px) {{ .grid2 {{ grid-template-columns: 1fr; }} }}
  .meta-svg text {{ font-size: 12px; }}
  .elabel {{ fill: var(--muted); font-size: 10.5px; paint-order: stroke;
    stroke: var(--surface); stroke-width: 4px; stroke-linejoin: round; }}
  footer {{ margin-top: 40px; padding-top: 16px; border-top: 1px solid var(--border); color: var(--muted); font-size: 12px; }}
</style></head>
<body><div class="wrap">
  <h1>Knowledge Graph — Real Estate RecSys</h1>
  <p class="sub">Trực quan hoá đồ thị tri thức sinh từ <code>users / listings / interactions</code>. Đồ thị đầy đủ: <b>{sum(node_counts.values()):,}</b> node · <b>{sum(edge_counts.values()):,}</b> edge.</p>

  <h2>1 · Schema (meta-graph)</h2>
  <div class="card">
    <div class="graph-wrap">{schema_svg()}</div>
  </div>

  <h2>2 · Subgraph mẫu ({N_SAMPLE_USERS} user)</h2>
  <div class="card">
    <div class="legend">{legend_items}</div>
    <p class="sub">Kích thước node theo loại; cạnh đậm = action mạnh (contact/save/share). Di chuột lên node/cạnh để xem chi tiết.</p>
    <div class="graph-wrap"><svg class="graph" viewBox="0 0 {gw} {gh}" role="img" aria-label="Sampled knowledge subgraph">
      <g class="edges">{edges_svg}</g>
      <g class="nodes">{nodes_svg}</g>
    </svg></div>
  </div>

  <h2>3 · Thống kê đồ thị</h2>
  <div class="grid2">
    <div class="card"><b>Số node theo loại</b><div class="chart-wrap">{node_bar}</div></div>
    <div class="card"><b>Số edge theo quan hệ</b><div class="chart-wrap">{edge_bar}</div></div>
  </div>
{eval_section}

  <footer>Sinh bởi <code>visualize_graph.py</code> · màu theo palette đã validate (dataviz) · tự-chứa, theme-aware.</footer>
</div></body></html>"""


def schema_svg():
    """Meta-graph tĩnh: 6 loại node + quan hệ chính."""
    # toạ độ tay, tách nhau để nhãn cạnh không đè node
    P = {
        "User": (150, 260), "Intent": (150, 90), "Query": (150, 470),
        "Listing": (560, 300), "Location": (860, 130), "Amenity": (860, 460),
    }
    # (a, b, label, t) — t = vị trí nhãn dọc cạnh (0=gần a, 1=gần b)
    edges = [
        ("User", "Intent", "HAS_INTENT", 0.5),
        ("User", "Query", "SEARCHED", 0.5),
        ("User", "Location", "PREFERS_DISTRICT", 0.42),
        ("User", "Amenity", "LIKES_AMENITY", 0.32),
        ("User", "Listing", "VIEWED / SAVED / CONTACTED", 0.5),
        ("Listing", "Location", "LOCATED_IN", 0.55),
        ("Listing", "Amenity", "HAS_AMENITY", 0.55),
    ]
    e = []
    for a, b, lbl, t in edges:
        ax, ay = P[a]; bx, by = P[b]
        lx, ly = ax + (bx - ax) * t, ay + (by - ay) * t
        e.append(f'<line class="edge strong" x1="{ax}" y1="{ay}" x2="{bx}" y2="{by}" stroke-width="1.6"/>'
                 f'<text class="elabel" x="{lx:.0f}" y="{ly-5:.0f}" text-anchor="middle">{lbl}</text>')
    n = []
    for lbl, (x, y) in P.items():
        r = 32
        n.append(f'<g class="node {lbl}"><circle cx="{x}" cy="{y}" r="{r}"/>'
                 f'<text x="{x}" y="{y+4}" text-anchor="middle" fill="#fff" font-size="12" font-weight="700">{lbl}</text></g>')
    return (f'<svg class="graph meta-svg" viewBox="0 0 1000 560" role="img" '
            f'aria-label="KG schema">{"".join(e)}{"".join(n)}</svg>')


def main():
    users = _load("users.json", UserProfile)
    listings = _load("listings.json", Listing)
    interactions = _load("interactions.json", Interaction)

    node_counts, edge_counts = full_graph_stats(users, listings, interactions)
    G, meta, styles = build_sample_graph(users, listings, interactions)
    edges_svg, nodes_svg, gw, gh = layout_svg(G, meta, styles)

    eval_blob = None
    ev = os.path.join(DATA_DIR, "eval_results.json")
    if os.path.exists(ev):
        with open(ev, encoding="utf-8") as f:
            eval_blob = json.load(f)

    html = render_html(node_counts, edge_counts, edges_svg, nodes_svg, gw, gh, eval_blob)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[viz] subgraph: {G.number_of_nodes()} nodes / {G.number_of_edges()} edges")
    print(f"[viz] full graph: {sum(node_counts.values())} nodes / {sum(edge_counts.values())} edges")
    print(f"[viz] -> {OUT}")


if __name__ == "__main__":
    main()
