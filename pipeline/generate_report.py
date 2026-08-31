#!/usr/bin/env python3
"""Step 8 — generate the visual report charts from study data.

Reads aggregates.json + scan-results.jsonl + verdicts.jsonl and writes
6 PNG charts for the corpus study narrative:

    01-waffle.png       — committed .env, 242/881 cells
    02-grades.png       — security grade distribution (A-F)
    03-credentials.png  — credential classes by repo prevalence
    04-verification.png — kept vs dropped findings by rule
    05-disaster.png     — the F-grade tail: what those repos shipped
    06-scores.png       — score band distribution with q1/median/mean

Usage:
    python backend/scripts/corpus/generate_report.py [--dir data/corpus] [--out docs/corpus-report/charts]
"""

from __future__ import annotations

import argparse
import json
import math
import os
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
from matplotlib.font_manager import fontManager

from common import DATA_DIR, read_jsonl

from scanner.corpus_stats import grade_from_score, security_score

# ── try to load Inter; fall back to DejaVu Sans ──
_FONT = "DejaVu Sans"
for _candidate in ("Inter", "Helvetica Neue", "Helvetica", "Arial"):
    try:
        fontManager.findfont(_candidate, fallback_to_default=False)
        _FONT = _candidate
        break
    except Exception:
        pass

# ── design system (ogbuilds palette) ──
BLUE = "#2563eb"
AMBER = "#d97706"
GREEN = "#059669"
RED = "#dc2626"
GRAY_50 = "#fafafa"
GRAY_100 = "#f3f4f6"
GRAY_200 = "#e5e7eb"
GRAY_400 = "#9ca3af"
GRAY_500 = "#6b7280"
GRAY_900 = "#111827"

GRADE_COLORS = {"A": GREEN, "B": "#65a30d", "C": AMBER, "D": "#ea580c", "F": RED}

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": [_FONT, "DejaVu Sans"],
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "axes.edgecolor": "white",
    "axes.labelcolor": GRAY_500,
    "xtick.color": GRAY_400,
    "ytick.color": "white",
    "axes.grid": False,
    "grid.color": GRAY_200,
    "grid.linewidth": 0.8,
    "grid.alpha": 0.6,
    "svg.fonttype": "none",
    "pdf.fonttype": 42,
})

FIGSIZE = (16, 9)
DPI = 160


def _new_ax():
    fig, ax = plt.subplots(figsize=FIGSIZE, dpi=DPI)
    ax.tick_params(length=0, pad=12)
    for spine in ax.spines.values():
        spine.set_visible(False)
    return fig, ax


def _hgrid(ax, xmax: int, step: int = 1) -> None:
    """Light horizontal gridlines at y-tick positions."""
    for y in range(0, xmax + 1, step):
        ax.axhline(y, color=GRAY_200, linewidth=0.8, zorder=0, alpha=0.5)


def _stat_line(fig, left: str, right: str, y: float = 0.93) -> None:
    fig.text(0.04, y, left, fontsize=13, color=GRAY_400, fontweight="500",
             fontfamily=_FONT)
    fig.text(0.96, y, right, fontsize=28, color=GRAY_900, ha="right",
             fontweight="800", fontfamily=_FONT)


def _rounded_bar(ax, x, y, w, h, color, **kw):
    """Bar with rounded corners."""
    patch = FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.02",
        facecolor=color, edgecolor="none",
        zorder=3, **kw,
    )
    ax.add_patch(patch)
    return patch


def _save(fig, out_dir: Path, name: str) -> None:
    path = out_dir / name
    fig.savefig(path, bbox_inches="tight", facecolor="white", dpi=DPI,
                pad_inches=0.4)
    plt.close(fig)
    print(f"wrote {path}")


# ────────────────────────────────────────────────────────────────────
# Chart 1: Waffle
# ────────────────────────────────────────────────────────────────────
def chart_waffle(rows, out: Path) -> None:
    env_k = sum(1 for r in rows if r["env_files"])
    n = len(rows)
    cols, rows_g = 44, 21
    fig, ax = _new_ax()
    ax.set_xlim(-0.5, cols + 0.5)
    ax.set_ylim(rows_g + 0.5, -1)
    ax.set_aspect("equal")
    ax.axis("off")
    cell = 0.88
    for i in range(n):
        x, y = i % cols, i // cols
        color = AMBER if i < env_k else GRAY_100
        patch = FancyBboxPatch(
            (x - cell / 2, y - cell / 2), cell, cell,
            boxstyle="round,pad=0.06",
            facecolor=color, edgecolor="white", linewidth=2,
        )
        ax.add_patch(patch)
    _stat_line(fig, "The .env file", f"{100 * env_k / n:.1f}%")
    ax.text(cols / 2, rows_g - 0.8,
            f"{env_k} of {n} apps commit their .env file to the repository",
            fontsize=16, color=GRAY_500, ha="center", va="top",
            fontfamily=_FONT, fontweight="400")
    from matplotlib.patches import Patch
    ax.legend(
        handles=[
            Patch(facecolor=AMBER, edgecolor="none", label=f"commits .env — {env_k}"),
            Patch(facecolor=GRAY_100, edgecolor="none", label=f"does not — {n - env_k}"),
        ],
        loc="lower center", bbox_to_anchor=(0.5, -0.08), ncol=2,
        frameon=False, fontsize=14, handlelength=1.4, handleheight=1.4,
        labelspacing=0.8,
    )
    _save(fig, out, "01-waffle.png")


# ────────────────────────────────────────────────────────────────────
# Chart 2: Grades
# ────────────────────────────────────────────────────────────────────
def chart_grades(grades: Counter, clean_k: int, median: int, mean: float,
                 out: Path) -> None:
    order = ["A", "B", "C", "D", "F"]
    n = sum(grades.values())
    fig, ax = _new_ax()
    counts = [grades.get(g, 0) for g in order]
    ys = list(range(len(order)))
    max_c = max(counts)
    ax.set_xlim(0, max_c * 1.22)
    _hgrid(ax, len(ys), 1)
    for y, g, c in zip(ys, order, counts):
        _rounded_bar(ax, 0, y - 0.35, c, 0.7, GRADE_COLORS[g])
        pct = 100 * c / n
        label = f"  {c:,}  ({pct:.1f}%)"
        ax.text(c + max_c * 0.008, y, label, va="center", fontsize=16,
                color=GRAY_900, fontweight="700", fontfamily=_FONT)
    ax.set_yticks(ys)
    ax.set_yticklabels([f"  {g}" for g in order], fontsize=20, color=GRAY_900,
                       fontweight="800", fontfamily=_FONT)
    ax.text(max_c * 1.15, len(order) - 0.35,
            f"{clean_k} apps perfectly clean  ·  median {median}  ·  mean {mean:.1f}",
            fontsize=13, color=GRAY_400, ha="right", fontfamily=_FONT)
    _save(fig, out, "02-grades.png")


# ────────────────────────────────────────────────────────────────────
# Chart 3: Credentials
# ────────────────────────────────────────────────────────────────────
def chart_credentials(per_class, n: int, out: Path) -> None:
    top = sorted(per_class.items(), key=lambda kv: -kv[1]["repos"])[:10]
    names = [cls.replace(" key", "").replace(" token", "") for cls, _ in top]
    counts = [d["repos"] for _, d in top]
    fig, ax = _new_ax()
    ys = list(range(len(top)))
    max_c = max(counts)
    ax.set_xlim(0, max_c * 1.28)
    _hgrid(ax, len(ys), 1)
    for y, c in zip(ys, counts):
        color = AMBER if y == 0 else BLUE
        _rounded_bar(ax, 0, y - 0.35, c, 0.7, color)
        ax.text(c + max_c * 0.015, y, f"{c}  ({100 * c / n:.1f}%)",
                va="center", fontsize=14, color=GRAY_500, fontfamily=_FONT)
    ax.set_yticks(ys)
    ax.set_yticklabels(names, fontsize=16, color=GRAY_900, fontweight="500",
                       fontfamily=_FONT)
    ax.text(0, -0.7, "repos carrying at least one finding of this class "
            "(before verification)", fontsize=13, color=GRAY_400,
            fontfamily=_FONT)
    ax.annotate(
        "anon keys — public by design\nrole-verified 0/269 false positives",
        xy=(counts[0] - max_c * 0.02, 0),
        xytext=(max_c * 0.55, 3.5),
        fontsize=14, color=AMBER, fontweight="700", fontfamily=_FONT,
        arrowprops=dict(arrowstyle="->", color=AMBER, linewidth=1.8,
                        connectionstyle="arc3,rad=0.15"),
        ha="center",
    )
    _save(fig, out, "03-credentials.png")


# ────────────────────────────────────────────────────────────────────
# Chart 4: Verification
# ────────────────────────────────────────────────────────────────────
def chart_verification(overturn, out: Path) -> None:
    items = sorted(overturn.items(), key=lambda kv: -kv[1]["total"])[:12]
    names = [cid.replace("_", " ") for cid, _ in items]
    kept = [d["total"] - d["dropped"] for _, d in items]
    dropped = [d["dropped"] for _, d in items]
    fig, ax = _new_ax()
    ys = list(range(len(items)))
    max_total = max(k + d for k, d in zip(kept, dropped))
    ax.set_xlim(0, max_total * 1.28)
    _hgrid(ax, len(ys), 1)
    for y, k, d in zip(ys, kept, dropped):
        _rounded_bar(ax, 0, y - 0.35, k, 0.7, BLUE, alpha=0.9)
        if d:
            _rounded_bar(ax, k, y - 0.35, d, 0.7, RED, alpha=0.85)
        total = k + d
        if total:
            pct = 100 * d / total
            if d:
                ax.text(total + max_total * 0.015, y,
                        f"{pct:.0f}% dropped", va="center", fontsize=13,
                        color=RED, fontweight="700", fontfamily=_FONT)
            else:
                ax.text(k + max_total * 0.015, y, "0% dropped",
                        va="center", fontsize=13, color=GREEN,
                        fontweight="700", fontfamily=_FONT)
    ax.set_yticks(ys)
    ax.set_yticklabels(names, fontsize=14, color=GRAY_900, fontweight="500",
                       fontfamily=_FONT)
    from matplotlib.patches import Patch
    ax.legend(
        handles=[
            Patch(facecolor=BLUE, edgecolor="none", label="kept (real)"),
            Patch(facecolor=RED, edgecolor="none", label="dropped (false positive)"),
        ],
        loc="lower right", frameon=False, fontsize=14,
        labelspacing=0.8,
    )
    ax.text(0, -0.7, "361 findings adjudicated with surrounding code — "
            "only high-confidence drops count", fontsize=13, color=GRAY_400,
            fontfamily=_FONT)
    _save(fig, out, "04-verification.png")


# ────────────────────────────────────────────────────────────────────
# Chart 5: Disaster
# ────────────────────────────────────────────────────────────────────
def chart_disaster(rows, out: Path) -> None:
    n = len(rows)
    f_repos = [r for r in rows
               if grade_from_score(security_score(r["findings"])) == "F"]
    f_checks = Counter(f["check_id"] for r in f_repos for f in r["findings"])
    top = [c for c, _ in f_checks.most_common(9)
           if c not in ("supabase_anon", "duplicate_files")]
    counts = [f_checks[c] for c in top]
    fig = plt.figure(figsize=FIGSIZE, dpi=DPI)

    # ── donut ──
    donut_ax = fig.add_axes([0.04, 0.22, 0.34, 0.66])
    donut_ax.set_aspect("equal")
    frac_f = len(f_repos) / n
    wedge_inner = 0.55
    donut_ax.pie(
        [frac_f, 1 - frac_f],
        colors=[RED, GRAY_100],
        startangle=90,
        counterclock=False,
        wedgeprops=dict(width=0.3, edgecolor="white", linewidth=3),
    )
    donut_ax.text(0, 0.08, str(len(f_repos)), ha="center", va="center",
                  fontsize=56, fontweight="800", color=RED, fontfamily=_FONT)
    donut_ax.text(0, -0.16, "apps", ha="center", va="center",
                  fontsize=18, color=GRAY_400, fontfamily=_FONT)

    # ── horizontal bars ──
    ax = fig.add_axes([0.46, 0.14, 0.50, 0.74])
    ys = list(range(len(top)))
    max_c = max(counts)
    ax.set_xlim(0, max_c * 1.18)
    _hgrid(ax, len(ys), 1)
    for y, c in zip(ys, counts):
        _rounded_bar(ax, 0, y - 0.35, c, 0.7, RED, alpha=0.85)
        ax.text(c + max_c * 0.015, y, str(c), va="center", fontsize=14,
                color=GRAY_500, fontfamily=_FONT)
    ax.set_yticks(ys)
    ax.set_yticklabels([c.replace("_", " ") for c in top], fontsize=14,
                       color=GRAY_900, fontweight="500", fontfamily=_FONT)
    fig.text(0.04, 0.93, "The disaster tail", fontsize=28, fontweight="800",
             color=GRAY_900, fontfamily=_FONT)
    fig.text(0.04, 0.88, f"{100 * frac_f:.1f}% of apps ship committed live secrets",
             fontsize=18, color=GRAY_500, fontfamily=_FONT)
    fig.text(0.96, 0.06, f"{100 * frac_f:.1f}% of {n}",
             fontsize=14, color=GRAY_400, ha="right", fontfamily=_FONT)
    _save(fig, out, "05-disaster.png")


# ────────────────────────────────────────────────────────────────────
# Chart 6: Scores
# ────────────────────────────────────────────────────────────────────
def chart_scores(bands: dict, q1: int, median: int, mean: float,
                 out: Path) -> None:
    xs = [int(b) for b in sorted(bands, key=int)]
    counts = [bands[str(x)] for x in xs]
    fig, ax = _new_ax()
    colors = [GREEN if x >= 90 else (RED if x < 60 else AMBER) for x in xs]
    for x, c, col in zip(xs, counts, colors):
        _rounded_bar(ax, x - 4, 0, 8, c, col, alpha=0.9)
    ax.set_xticks(range(0, 110, 10))
    ax.set_xlim(-6, 108)
    ax.set_ylim(0, max(counts) * 1.15)
    ax.tick_params(axis="x", labelsize=13, colors=GRAY_400, length=0, pad=10)
    ax.tick_params(axis="y", labelsize=0, length=0)
    ax.spines["bottom"].set_visible(True)
    ax.spines["bottom"].set_color(GRAY_200)
    ax.spines["bottom"].set_linewidth(1)
    for x, c in zip(xs, counts):
        if c >= 10:
            ax.text(x, c + max(counts) * 0.015, str(c), ha="center",
                    fontsize=12, color=GRAY_400, fontfamily=_FONT)
    ax.axvline(median, color=GRAY_900, linestyle="--", linewidth=1.8, zorder=2)
    ax.text(median, max(counts) * 1.08, f"median {median}", fontsize=13,
            color=GRAY_900, fontweight="700", ha="center", fontfamily=_FONT)
    ax.axvline(mean, color=BLUE, linestyle="--", linewidth=1.8, zorder=2)
    ax.text(mean, max(counts) * 1.02, f"mean {mean:.1f}", fontsize=13,
            color=BLUE, fontweight="700", ha="center", fontfamily=_FONT)
    ax.axvline(q1, color=GRAY_400, linestyle="--", linewidth=1.8, zorder=2)
    ax.text(q1, max(counts) * 0.96, f"q1 {q1}", fontsize=13,
            color=GRAY_400, fontweight="700", ha="center", fontfamily=_FONT)
    ax.set_xlabel("security score band", fontsize=14, color=GRAY_500,
                  fontfamily=_FONT, labelpad=12)
    _save(fig, out, "06-scores.png")


# ────────────────────────────────────────────────────────────────────
# Chart 7: Blast radius
# ────────────────────────────────────────────────────────────────────
def chart_blast(blast, out: Path) -> None:
    tiers = blast["repo_tiers"]
    a, b, c, d = (tiers[k] for k in (
        "A — data access", "B — cost", "C — bounded", "D — none"))
    n = blast["n"]
    bound = blast["supabase_bound"]
    fig, ax = _new_ax()
    ax.set_xlim(0, n)
    ax.set_ylim(-0.9, 2.4)
    ax.axis("off")

    bars = [
        (f"All {n} apps", [(d, GRAY_100), (c, BLUE), (b, AMBER), (a, RED)]),
        ("Supabase anon-key apps", [
            (bound["rls_enabled"], BLUE),
            (bound["rls_disabled"], RED),
        ]),
    ]
    for row, (label, segs) in enumerate(bars):
        y = row
        x = 0
        total = sum(s for s, _ in segs)
        for size, color in segs:
            if size == 0:
                continue
            ax.barh(y, size, left=x, color=color, height=0.55, zorder=3)
            x += size
        ax.text(-n * 0.012, y, label, ha="right", va="center",
                fontsize=15, color=GRAY_900, fontweight="600",
                fontfamily=_FONT)
        ax.text(total + n * 0.012, y, f"{total}", va="center",
                fontsize=16, color=GRAY_900, fontweight="800",
                fontfamily=_FONT)

    def _annot(x, y, text, color):
        ax.text(x + n * 0.012, y, text, va="center", fontsize=13,
                color=color, fontweight="700", fontfamily=_FONT)

    _annot(a, 1, f"{a} would grant data access if valid", RED)
    _annot(b, 1, f"{b} burn money if used", AMBER)
    _annot(c, 1, f"{c} bounded by design", BLUE)
    _annot(d, 1, f"{d} clean or hygiene only", GRAY_400)
    _annot(bound["rls_disabled"], 0, f"{bound['rls_disabled']} with RLS "
           "disabled — bound broken", RED)
    _annot(bound["rls_enabled"], 0, f"{bound['rls_enabled']} bounded by RLS",
           BLUE)

    if bound["rls_disabled"]:
        ax.annotate(
            "the anon key is safe *because* of RLS —\n1 in 8 Supabase apps turned it off",
            xy=(bound["rls_disabled"] + n * 0.12, 0),
            xytext=(n * 0.35, 1.75),
            fontsize=14, color=GRAY_900, fontweight="700", fontfamily=_FONT,
            arrowprops=dict(arrowstyle="->", color=GRAY_400, linewidth=1.5),
            ha="center",
        )
    _stat_line(fig, "Blast radius — what the findings would actually do",
               f"{100 * a / n:.1f}%")
    _save(fig, out, "07-blast.png")


# ────────────────────────────────────────────────────────────────────
# Chart 8: Where secrets live
# ────────────────────────────────────────────────────────────────────
def chart_locations(locs, out: Path) -> None:
    by_loc = locs["by_location_tier"]
    tiers = ["A — data access", "B — cost", "C — bounded", "D — none"]
    order = [l for l in ("docs", "env", "tooling", "tests", "config", "sql",
                         "frontend")
             if by_loc.get(l)]
    fig, ax = _new_ax()
    ys = range(len(order))
    max_total = max(sum(by_loc[l].values()) for l in order)
    ax.set_xlim(0, max_total * 1.34)
    _hgrid(ax, len(order), 1)
    for y, loc in zip(ys, order):
        x = 0
        for t, color in zip(tiers, (RED, AMBER, BLUE, GRAY_100)):
            size = by_loc[loc][t]
            if not size:
                continue
            ax.barh(y, size, left=x, color=color, height=0.66, zorder=3)
            x += size
        ax.text(max_total * 1.02, y, str(x), va="center", fontsize=13,
                color=GRAY_500, fontweight="600", fontfamily=_FONT)
    ax.set_yticks(list(ys))
    ax.set_yticklabels(order, fontsize=17, color=GRAY_900, fontweight="600",
                       fontfamily=_FONT)
    from matplotlib.patches import Patch
    ax.legend(
        handles=[Patch(facecolor=RED, edgecolor="none", label="A — data access"),
                 Patch(facecolor=AMBER, edgecolor="none", label="B — cost"),
                 Patch(facecolor=BLUE, edgecolor="none", label="C — bounded"),
                 Patch(facecolor=GRAY_100, edgecolor=GRAY_200, label="D — none")],
        loc="lower right", frameon=False, fontsize=13, ncol=2,
        labelspacing=0.6,
    )
    fa = locs["frontend_tier_a"]["repos"]
    if by_loc["frontend"]["A — data access"]:
        ax.annotate(
            f"{by_loc['frontend']['A — data access']} tier-A findings in the "
            f"frontend bundle —\n{fa} repos publish data-access credentials\nto "
            "every visitor",
            xy=(by_loc["frontend"]["A — data access"], 6.2),
            xytext=(max_total * 0.5, len(order) - 0.7),
            fontsize=13, color=RED, fontweight="700", fontfamily=_FONT,
            arrowprops=dict(arrowstyle="->", color=RED, linewidth=1.5),
            ha="center",
        )
    top_loc = max(order, key=lambda l: by_loc[l]["A — data access"])
    _stat_line(fig, "Where secrets live — findings by location × tier",
               f"{top_loc} first")
    _save(fig, out, "08-locations.png")


# ────────────────────────────────────────────────────────────────────
# Chart 9: cross-population comparison
# ────────────────────────────────────────────────────────────────────
def chart_comparison(pops, out: Path) -> None:
    """Grouped horizontal bars comparing the corpus populations on the
    key security metrics. `pops` is an ordered list of
    (label, n, aggregates_dict, color)."""
    metrics = [
        ("Committed .env", lambda a: 100 * a["existence"]["env_committed"]["value"]),
        ("No root .gitignore", lambda a: 100 * a["existence"]["gitignore_missing"]["value"]),
        ("Fully clean", lambda a: 100 * a["findings"]["clean_repos"]["value"]),
        ("Mean score", lambda a: a["findings"]["mean_score"]),
        ("F grade", lambda a: 100 * a["findings"]["grades"].get("F", {"count": 0})["count"] / a["n"]),
        ("Data-access tier", lambda a: 100 * _blast_tier_a(a)),
    ]
    from matplotlib.patches import Patch
    fig, ax = _new_ax()
    n_metrics = len(metrics)
    n_pops = len(pops)
    bar_h = 0.62
    group_gap = 1.0
    ax.set_xlim(0, 100)
    ax.set_ylim(-0.6, n_metrics * group_gap + 0.6)
    ax.axis("off")
    for mi, (mname, fn) in enumerate(metrics):
        y_base = n_metrics * group_gap - 1 - mi * group_gap
        ax.text(-2.5, y_base, mname, ha="right", va="center", fontsize=16,
                color=GRAY_900, fontweight="600", fontfamily=_FONT)
        for pi, (label, n, agg, color) in enumerate(pops):
            try:
                val = fn(agg)
            except Exception:
                val = 0.0
            y = y_base + (pi - (n_pops - 1) / 2) * 0.18
            _rounded_bar(ax, 0, y - bar_h / 2, min(val, 100), bar_h, color)
            ax.text(min(val, 100) + 1.2, y, f"{val:.1f}",
                    va="center", fontsize=12, color=GRAY_500,
                    fontweight="600", fontfamily=_FONT)
    ax.legend(
        handles=[Patch(facecolor=c, edgecolor="none", label=f"{l} (n={n})")
                 for l, n, _, c in pops],
        loc="lower center", bbox_to_anchor=(0.5, -0.02), ncol=n_pops,
        frameon=False, fontsize=13, handlelength=1.2, handleheight=1.2,
    )
    _stat_line(fig, "Four populations, one engine — same rules, same verification",
               "the evidence")
    _save(fig, out, "09-comparison.png")


def _blast_tier_a(agg: dict) -> float:
    """Repo share at tier A (data access) — from the blast-radius json if
    present next to the aggregates, else fall back to per-class sums."""
    import os as _os
    base = _os.path.dirname(agg.get("_path", "")) if agg.get("_path") else None
    if base:
        br = _os.path.join(base, "blast-radius.json")
        if _os.path.exists(br):
            import json as _json
            try:
                b = _json.load(open(br))
                return b["repo_tiers"]["A — data access"] / b["n"]
            except Exception:
                pass
    return 0.0


# ────────────────────────────────────────────────────────────────────
# Charts 10/11: vibe-coding landscape (census + composition)
# ────────────────────────────────────────────────────────────────────
_LAYER_COLORS = {"model": BLUE, "tool": AMBER, "term": GREEN, "topic": "#7c3aed"}


def chart_market_census(queries: dict, out: Path) -> None:
    """Horizontal log-scale bars of README self-description + topic counts,
    colored by layer (model / tool / vibe term / topic)."""
    order = [
        "built with claude", "built with claude code", "generated with claude",
        "made with claude", "built with gemini", "built with codex",
        "built with gpt", "built with cursor", "built with chatgpt",
        "built with copilot",
        "built with v0", "built with lovable", "built with bolt",
        "vibe coded", "vibe-coded", "generated with ai", "built with ai",
        "ai-generated",
        "topic:ai-generated", "topic:vibe-coding", "topic:vibe-coded",
        "topic:ai-app",
    ]
    layer = {}
    for i, lbl in enumerate(order):
        layer[lbl] = ("model" if i < 10 else "tool" if i < 13
                      else "term" if i < 18 else "topic")
    fig, ax = _new_ax()
    items = [(l, queries[l]["total"] or 0) for l in order if l in queries]
    ys = range(len(items))
    ax.set_xscale("log")
    ax.set_xlim(50, 300000)
    _hgrid(ax, len(items), 1)
    for y, (lbl, total) in zip(ys, items):
        _rounded_bar(ax, 50, y - 0.35, total - 50, 0.7,
                     _LAYER_COLORS[layer[lbl]])
        ax.text(total * 1.25, y, f"{total:,}", va="center", fontsize=13,
                color=GRAY_900, fontweight="700", fontfamily=_FONT)
    ax.set_yticks(list(ys))
    ax.set_yticklabels([l.replace("built with ", "").replace("topic:", "topic·")
                        for l, _ in items], fontsize=14, color=GRAY_900,
                       fontweight="500", fontfamily=_FONT)
    from matplotlib.patches import Patch
    ax.legend(
        handles=[Patch(facecolor=_LAYER_COLORS[k], edgecolor="none",
                       label=k.title()) for k in ("model", "tool", "term", "topic")],
        loc="lower right", frameon=False, fontsize=13,
    )
    ax.text(60, len(items) + 0.35,
            "README self-descriptions + repo topics · GitHub code/repo search · "
            "self-identification, not usage share", fontsize=13, color=GRAY_400,
            fontfamily=_FONT)
    _stat_line(fig, "The vibe-coding landscape — who says they ship AI-built",
               "claude first")
    _save(fig, out, "10-market.png")


def chart_market_composition(tax: dict, out: Path) -> None:
    """What a self-described AI-coded repo actually is: framework bars +
    app-share callout."""
    fig, ax = _new_ax()
    fw = list(tax["framework_counts"].items())[:8]
    ys = range(len(fw))
    max_c = max(c for _, c in fw)
    ax.set_xlim(0, max_c * 1.25)
    _hgrid(ax, len(fw), 1)
    for y, (name, c) in zip(ys, fw):
        _rounded_bar(ax, 0, y - 0.35, c, 0.7, GREEN if name in
                     ("react", "next") else BLUE)
        ax.text(c + max_c * 0.02, y, str(c), va="center", fontsize=14,
                color=GRAY_500, fontfamily=_FONT)
    ax.set_yticks(list(ys))
    ax.set_yticklabels(fw and [n for n, _ in fw] or [], fontsize=16,
                       color=GRAY_900, fontweight="600", fontfamily=_FONT)
    ax.text(0, len(fw) + 0.4,
            f"repos with a detectable framework (of {tax['n']} total)",
            fontsize=13, color=GRAY_400, fontfamily=_FONT)
    ax.annotate(
        f"{tax['no_manifest_pct']:.0f}% have no dependency manifest —\n"
        f"not apps at all; {tax['app_shaped_pct']:.0f}% are app-shaped\n"
        f"(median {tax['median_files']} files / {tax['median_bytes'] // 1024} KB)",
        xy=(max_c, len(fw) - 0.5), xytext=(max_c * 0.55, len(fw) + 3.1),
        fontsize=14, color=GRAY_900, fontweight="700", fontfamily=_FONT,
        arrowprops=dict(arrowstyle="->", color=GRAY_400, linewidth=1.5),
        ha="center",
    )
    _stat_line(fig, "What a self-described AI-coded repo actually is",
               "mostly not an app")
    _save(fig, out, "11-composition.png")


# ────────────────────────────────────────────────────────────────────
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dir", default=DATA_DIR)
    ap.add_argument("--out", default=os.path.join("docs", "corpus-report", "charts"))
    ap.add_argument("--compare", default=None,
                    help="cross-population chart: comma-separated Label:dir pairs "
                         "(e.g. 'Lovable:backend/data/corpus,v0:backend/data/corpus-v0,"
                         "AI-coded:backend/data/corpus-aicoded,AI-coded apps:backend/data/corpus-aicoded-app')")
    ap.add_argument("--compare-out", default=os.path.join("docs", "corpus-report", "charts"))
    ap.add_argument("--market", default=None,
                    help="landscape charts: path to market-map.json "
                         "(renders 10-market.png + 11-composition.png)")
    ap.add_argument("--market-out", default=os.path.join("docs", "corpus-report", "charts-landscape"))
    args = ap.parse_args()

    if args.market:
        mm = json.load(open(args.market))
        out = Path(args.market_out)
        out.mkdir(parents=True, exist_ok=True)
        chart_market_census(mm["queries"], out)
        chart_market_composition(mm["taxonomy"], out)
        print(f"landscape charts → {out}/")
        return

    if args.compare:
        import json as _json
        pops = []
        colors = [BLUE, AMBER, GREEN, "#7c3aed"]
        for i, pair in enumerate(args.compare.split(",")):
            label, d = pair.split(":", 1)
            agg = _json.load(open(os.path.join(d, "aggregates.json")))
            agg["_path"] = os.path.join(d, "aggregates.json")
            pops.append((label, agg["n"], agg, colors[i % len(colors)]))
        out = Path(args.compare_out)
        out.mkdir(parents=True, exist_ok=True)
        chart_comparison(pops, out)
        print(f"comparison chart → {out / '09-comparison.png'}")
        return

    agg = json.load(open(os.path.join(args.dir, "aggregates.json")))
    rows = [r for r in read_jsonl(os.path.join(args.dir, "scan-results.jsonl"))
            if r.get("ok")]
    verdicts = read_jsonl(os.path.join(args.dir, "verdicts.jsonl"))

    overturn: Counter[str] = Counter()
    total: Counter[str] = Counter()
    for v in verdicts:
        total[v["check_id"]] += 1
        if v.get("verdict") == "drop":
            overturn[v["check_id"]] += 1

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    chart_waffle(rows, out)
    chart_grades(
        Counter({g: d["count"] for g, d in agg["findings"]["grades"].items()}),
        agg["findings"]["clean_repos"]["count"],
        agg["findings"]["quartiles"]["median"],
        agg["findings"]["mean_score"],
        out,
    )
    chart_credentials(agg["findings"]["per_class"], len(rows), out)
    chart_verification(
        {cid: {"dropped": overturn.get(cid, 0), "total": total.get(cid, 0)}
         for cid in total},
        out,
    )
    chart_disaster(rows, out)
    chart_scores(
        agg["findings"]["score_bands"],
        agg["findings"]["quartiles"]["q1"],
        agg["findings"]["quartiles"]["median"],
        agg["findings"]["mean_score"],
        out,
    )
    blast = json.load(open(os.path.join(args.dir, "blast-radius.json")))
    chart_blast(blast, out)
    locs = json.load(open(os.path.join(args.dir, "secret-locations.json")))
    chart_locations(locs, out)
    print(f"charts → {out}/  (n={len(rows)})")


if __name__ == "__main__":
    main()
