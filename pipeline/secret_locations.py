#!/usr/bin/env python3
"""Where secrets live — file-location mechanics of every finding.

Cross-tabs findings by (file location × blast-radius tier). The location
is classified from the file path inside the repo:

    env       — .env / .env.template / *.env files (committed)
    sql       — supabase/migrations, *.sql
    docs      — *.md, docs/, README, *_SETUP_*, *_GUIDE*, *_SUMMARY*,
                *_CHECKLIST*, *_LOG*, *_REPORT*
    tests     — test/, tests/, __tests__, *.test.*, *.spec.*
    config    — .cursor/, .agent/, *.config.*, mcp.json, deno.json
    fixtures  — fixtures/, qiling_output, emulation artifacts
    frontend  — src/, components/, pages/, public/, *.tsx, *.jsx, *.html
                (compiled into the browser bundle — visible to every visitor)
    tooling   — scripts/, server/, api/, backend/, services/, functions/,
                agents/, lib/ (server-side / operational code)
    other     — anything else

The headline question: which locations carry tier-A (data-access)
credentials — and how much of it reaches the frontend bundle, where
VITE_-style exposure publishes it to every visitor.

Usage:
    python backend/scripts/corpus/secret_locations.py [--dir data/corpus]
"""

from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter
from datetime import datetime, timezone

from common import DATA_DIR, json_dump, read_jsonl

from blast_radius import TIER_A, TIER_B, TIER_C, TIER_D, TIER_ORDER, finding_tier

_LOCS = ["frontend", "tooling", "sql", "config", "docs", "tests", "fixtures", "env", "other"]
LOC_ORDER = ["frontend", "tooling", "sql", "config", "docs", "tests", "fixtures", "env", "other"]


_CODE_EXT = (".js", ".ts", ".mjs", ".cjs", ".tsx", ".jsx", ".py", ".sh", ".rb",
             ".go", ".rs")


def classify(file_path: str) -> str:
    p = file_path.lower()
    name = p.rsplit("/", 1)[-1]
    depth = p.count("/")
    if ".env" in name or name.endswith("env.txt") or name.endswith("-env.txt"):
        return "env"
    if p.endswith(".sql") or "/migrations/" in p or "/sql/" in p:
        return "sql"
    if (p.endswith((".md", ".markdown")) or "/docs/" in p
            or p.startswith("readme")
            or any(k in p for k in ("_setup", "_guide", "_summary", "_checklist",
                                    "_log", "_report", "archive/"))):
        return "docs"
    if ("/test/" in p or "/tests/" in p or "/__tests__/" in p
            or ".test." in p or ".spec." in p):
        return "tests"
    if any(k in p for k in (".cursor/", ".agent/", ".config.", "mcp.json",
                            "deno.json", ".yaml", ".yml", "dockerfile",
                            ".toml", "wrangler", "n8n-workflows/",
                            "package.json")):
        return "config"
    if any(k in p for k in ("fixtures/", "qiling_output", "emulation")):
        return "fixtures"
    if (p.endswith((".tsx", ".jsx", ".vue", ".svelte", ".html", ".htm"))
            or "/src/" in p or "/components/" in p or "/pages/" in p
            or "/public/" in p or p.startswith(("src/", "components/", "pages/",
                                                "public/"))):
        return "frontend"
    # tooling: explicit dirs, supabase non-migration files, or shallow
    # root-level code files (scripts written at the repo root)
    if (p.startswith(("scripts/", "server/", "api/", "backend/", "services/",
                      "functions/", "agents/", "lib/", "supabase/"))
            or "/scripts/" in p or "/server/" in p or "/api/" in p
            or "/backend/" in p or "/services/" in p or "/functions/" in p
            or "/agents/" in p or "/lib/" in p
            or (depth <= 2 and p.endswith(_CODE_EXT))):
        return "tooling"
    return "other"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dir", default=DATA_DIR)
    ap.add_argument("--results", default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    rows = [r for r in read_jsonl(args.results or os.path.join(args.dir, "scan-results.jsonl")) if r.get("ok")]
    n = len(rows)

    # findings by (location, tier)
    loc_tier: Counter[tuple[str, str]] = Counter()
    loc_by_check: Counter[tuple[str, str]] = Counter()
    for r in rows:
        for f in r["findings"]:
            loc = classify(f.get("file", ""))
            tier = finding_tier(f)
            loc_tier[(loc, tier)] += 1
            loc_by_check[(loc, f["check_id"])] += 1

    # repo-level: tier-A finding in the frontend bundle (published to visitors)
    frontend_a_repos = 0
    frontend_a_checks: Counter[str] = Counter()
    for r in rows:
        a_in_front = {(classify(f.get("file", "")), f["check_id"])
                      for f in r["findings"]
                      if classify(f.get("file", "")) == "frontend"
                      and finding_tier(f) == TIER_A}
        if a_in_front:
            frontend_a_repos += 1
            for _, cid in a_in_front:
                frontend_a_checks[cid] += 1

    # docs carry — headline stat
    docs_a = sum(loc_tier[("docs", TIER_A)] for _ in [0])
    tier_a_total = sum(loc_tier[(l, TIER_A)] for l in LOC_ORDER)

    out = {
        "n": n,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "by_location_tier": {
            loc: {t: loc_tier[(loc, t)] for t in TIER_ORDER} for loc in LOC_ORDER
        },
        "tier_a_by_location": {loc: loc_tier[(loc, TIER_A)] for loc in LOC_ORDER},
        "frontend_tier_a": {
            "repos": frontend_a_repos,
            "checks": dict(frontend_a_checks),
        },
        "docs_tier_a": docs_a,
        "tier_a_total": tier_a_total,
    }
    json_dump(args.out or os.path.join(args.dir, "secret-locations.json"), out)

    print(f"## Where secrets live (N = {n})\n")
    print("Findings by location × tier:")
    print("| location | A data | B cost | C bounded | D none | total |")
    print("|---|---|---|---|---|---|")
    for loc in LOC_ORDER:
        t = [loc_tier[(loc, tier)] for tier in TIER_ORDER]
        print(f"| {loc} | {t[0]} | {t[1]} | {t[2]} | {t[3]} | {sum(t)} |")
    print()
    print(f"### Tier-A (data access) by location: "
          + ", ".join(f"{loc} {loc_tier[(loc, TIER_A)]}" for loc in LOC_ORDER if loc_tier[(loc, TIER_A)]))
    print(f"- tier-A in the frontend bundle: **{frontend_a_repos} repos** "
          f"({100 * frontend_a_repos / n:.1f}%) — published to every visitor")
    for cid, c in frontend_a_checks.most_common():
        print(f"    - {cid}: {c}")
    print(f"- tier-A in docs: **{docs_a} findings** of {tier_a_total} "
          f"({100 * docs_a / max(tier_a_total, 1):.0f}%) — credentials "
          f"written down with instructions")


if __name__ == "__main__":
    main()
