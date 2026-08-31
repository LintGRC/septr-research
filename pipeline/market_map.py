#!/usr/bin/env python3
"""Vibe-coding landscape census — who says they ship AI-built, and with what.

Read-only GitHub search over README self-descriptions (models, tools, vibe
terms) and repo topics, plus the app-shape taxonomy computed from the
AI-coded corpus scan. Outputs market-map.json:

    queries: {label: {query, total, created_at: [sample of repo created dates]}}
    topics:  {label: total}
    taxonomy: {n, no_manifest, app_shaped, framework_counts, median_files,
               median_bytes, app_median_files, app_median_bytes}

Honest framing (stated in the report, not hidden): self-identification
share, NOT usage share — Claude users advertise their tool choice more
than GPT/Copilot users. The census is a snapshot (generated_at), not a
time series.

Usage:
    python backend/scripts/corpus/market_map.py \
        [--results backend/data/corpus-aicoded/scan-results-app.jsonl] \
        [--out backend/data/corpus-aicoded/market-map.json]
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import time
import urllib.parse
from collections import Counter
from datetime import datetime, timezone

from common import DATA_DIR, api_get_json, github_token, json_dump, read_jsonl

# (label, query, endpoint) — endpoint: code | repositories
CENSUS_QUERIES: list[tuple[str, str, str]] = [
    # model-level self-descriptions (README)
    ("built with claude", '"built with claude" filename:README.md', "code"),
    ("built with claude code", '"built with claude code" filename:README.md', "code"),
    ("made with claude", '"made with claude" filename:README.md', "code"),
    ("generated with claude", '"generated with claude" filename:README.md', "code"),
    ("built with chatgpt", '"built with chatgpt" filename:README.md', "code"),
    ("built with gpt", '"built with gpt" filename:README.md', "code"),
    ("built with cursor", '"built with cursor" filename:README.md', "code"),
    ("built with copilot", '"built with copilot" filename:README.md', "code"),
    ("built with gemini", '"built with gemini" filename:README.md', "code"),
    ("built with codex", '"built with codex" filename:README.md', "code"),
    # tool-level self-descriptions
    ("built with v0", '"built with v0" filename:README.md', "code"),
    ("built with lovable", '"built with lovable" filename:README.md', "code"),
    ("built with bolt", '"built with bolt" filename:README.md', "code"),
    # vibe terms
    ("vibe coded", '"vibe coded" filename:README.md', "code"),
    ("vibe-coded", '"vibe-coded" filename:README.md', "code"),
    ("generated with ai", '"generated with ai" filename:README.md', "code"),
    ("built with ai", '"built with ai" filename:README.md', "code"),
    ("ai-generated", '"ai-generated" filename:README.md', "code"),
    # repo topics
    ("topic:ai-generated", "topic:ai-generated", "repositories"),
    ("topic:vibe-coding", "topic:vibe-coding", "repositories"),
    ("topic:vibe-coded", "topic:vibe-coded", "repositories"),
    ("topic:ai-app", "topic:ai-app", "repositories"),
]

CREATED_SAMPLE = 100  # repos sampled for created_at per query


def census(token: str) -> dict:
    out: dict[str, dict] = {}
    for label, query, endpoint in CENSUS_QUERIES:
        url = f"https://api.github.com/search/{endpoint}?" + urllib.parse.urlencode(
            {"q": query, "per_page": CREATED_SAMPLE}
        )
        try:
            data = api_get_json(url, token)
        except Exception as e:
            out[label] = {"query": query, "total": None, "created_at": [], "error": str(e)}
            time.sleep(2.2)
            continue
        items = data.get("items", [])
        created = []
        for it in items:
            repo = it.get("repository") or it
            created.append(repo.get("created_at", ""))
        out[label] = {
            "query": query,
            "total": data.get("total_count", 0),
            "created_at": [c for c in created if c],
        }
        time.sleep(2.2)
    return out


def taxonomy(results_path: str) -> dict:
    rows = [r for r in read_jsonl(results_path) if r.get("ok")]
    n = len(rows)
    no_manifest = sum(1 for r in rows
                      if not r["app_shape"]["has_package_json"]
                      and not r["app_shape"]["has_requirements"])
    app_shaped = sum(1 for r in rows
                     if (r["app_shape"]["has_package_json"]
                         or r["app_shape"]["has_requirements"])
                     and r["app_shape"]["framework"] and r["files"] >= 30)
    frameworks = Counter(r["app_shape"]["framework"] for r in rows
                         if r["app_shape"]["framework"])
    med = lambda xs: statistics.median(xs) if xs else 0
    return {
        "n": n,
        "no_manifest": no_manifest,
        "no_manifest_pct": 100 * no_manifest / max(n, 1),
        "app_shaped": app_shaped,
        "app_shaped_pct": 100 * app_shaped / max(n, 1),
        "framework_counts": dict(frameworks.most_common()),
        "median_files": med(sorted(r["files"] for r in rows)),
        "median_bytes": int(med(sorted(r["bytes"] for r in rows))),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--results", default=os.path.join(DATA_DIR, "scan-results-app.jsonl"))
    ap.add_argument("--out", default=os.path.join(DATA_DIR, "market-map.json"))
    args = ap.parse_args()

    token = github_token()
    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "queries": census(token),
        "taxonomy": taxonomy(args.results),
    }
    json_dump(args.out, out)

    print("## Vibe-coding landscape census\n")
    print("| label | total |")
    print("|---|---|")
    for label, q in out["queries"].items():
        print(f"| {label} | {q['total']} |")
    t = out["taxonomy"]
    print(f"\n## Taxonomy (n={t['n']})")
    print(f"no manifest: {t['no_manifest']} ({t['no_manifest_pct']:.0f}%) | "
          f"app-shaped: {t['app_shaped']} ({t['app_shaped_pct']:.0f}%) | "
          f"median files: {t['median_files']} / {t['median_bytes']//1024} KB")
    print("frameworks:", ", ".join(f"{k} {v}" for k, v in
                                    list(t["framework_counts"].items())[:10]))
    print(f"\nmarket-map → {args.out}")


if __name__ == "__main__":
    main()
