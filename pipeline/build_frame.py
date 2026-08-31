#!/usr/bin/env python3
"""Step 1 — build a corpus frame via GitHub code search.

GitHub code search does not support date qualifiers and caps at 1,000
results per query, so the frame is the first `--max-results` best-match
results of the platform's signal query (relevance order), with optional
`--size-slices` fallback queries merged in so the frame is not dominated
by one size bucket. Reproducible within a run; the study must describe
the frame as "top best-match results", not as a random sample.

Platforms:
    lovable — `lovable-tagger filename:package.json` (the vite plugin
              Lovable writes into every generated project; 78k+ hits)
    v0      — `data-v0- language:HTML` (+ `data-v0- extension:tsx`
              fallback) — the attribute v0.dev writes into every
              generated component; 671 hits, complete surface
    aicoded — repositories that describe themselves as AI-coded:
              the `ai-generated` topic (repo search, 898 — complete
              surface) merged with READMEs saying "vibe-coded" (code
              search, top best-match). Same population ogbuilds used
              for their 549-repo cross-corpus comparison.
    bolt    — NOT supported: the __bolt__ marker lives in Bolt.new's
              browser environment, not committed repos. A spike found
              81 noisy hits (icon sets, data files) and zero
              package.json presence — no deterministic signal exists.

Usage:
    GITHUB_TOKEN=... python backend/scripts/corpus/build_frame.py \
        --platform v0 --out backend/data/corpus-v0/frame.json
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import time
import urllib.parse

from common import DATA_DIR, api_get_json, github_token, json_dump, repo_id

PLATFORM_QUERIES: dict[str, list[str]] = {
    "lovable": ["lovable-tagger filename:package.json"],
    "v0": ["data-v0- language:HTML", "data-v0- extension:tsx"],
    "aicoded": ["topic:ai-generated", '"vibe-coded" filename:README.md'],
}


def search_pages(token: str, query: str, max_results: int) -> list[dict]:
    """Page through one search query (cap 1000, polite sleep). `topic:`
    queries run against the repositories endpoint (items carry `full_name`
    at top level); everything else uses code search (items nest under
    `repository`)."""
    endpoint = "repositories" if query.startswith("topic:") else "code"
    out: list[dict] = []
    page = 1
    while len(out) < max_results:
        url = f"https://api.github.com/search/{endpoint}?" + urllib.parse.urlencode(
            {"q": query, "per_page": 100, "page": page}
        )
        data = api_get_json(url, token)
        items = data.get("items", [])
        out.extend(items)
        if len(items) < 100:
            break
        page += 1
        time.sleep(2.5)  # 30/min authenticated search limit
    return out[:max_results]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--platform", default="lovable",
                    choices=sorted(PLATFORM_QUERIES))
    ap.add_argument("--max-results", type=int, default=1000)
    ap.add_argument("--size-slices", action="store_true",
                    help="merge a size-bucketed second query to widen coverage")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    token = github_token()
    seen: dict[str, dict] = {}
    queries = PLATFORM_QUERIES[args.platform]

    def absorb(items: list[dict]) -> None:
        for it in items:
            repo = it.get("repository") or it
            if repo.get("private"):
                continue
            full = repo["full_name"]
            seen.setdefault(full, {
                "id": repo_id(full),
                "full_name": full,
                "html_url": repo["html_url"],
                "pushed_at": repo.get("pushed_at") or "",
            })

    for q in queries:
        if len(seen) >= args.max_results:
            break
        absorb(search_pages(token, q, args.max_results - len(seen)))
        time.sleep(2.5)
    if args.size_slices and len(seen) < args.max_results:
        # Size-bucketed slices pull in results the relevance ordering hides.
        # Only `size:lo..hi` range syntax is accepted by code search.
        for lo, hi in [(0, 10000), (10000, 100000), (100000, 1000000), (1000000, 1000000000)]:
            if len(seen) >= args.max_results:
                break
            q = f"{queries[0]} size:{lo}..{hi}"
            absorb(search_pages(token, q, args.max_results - len(seen)))
            time.sleep(2.5)

    out = args.out or os.path.join(DATA_DIR, f"{args.platform}-frame.json")
    frame = {
        "platform": args.platform,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "queries": queries + (["size-sliced fallbacks"] if args.size_slices else []),
        "n_repos": len(seen),
        "repos": sorted(seen.values(), key=lambda r: r["full_name"]),
    }
    json_dump(out, frame)
    print(f"frame written: {out} ({len(frame['repos'])} public repos)")


if __name__ == "__main__":
    main()
