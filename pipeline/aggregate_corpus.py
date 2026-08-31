#!/usr/bin/env python3
"""Step 5 — aggregate scan results (optionally with verdicts) into a study.

Computes per-check and per-class prevalence with Wilson 95% CIs, security
score/grade distributions, and — when verdicts.jsonl is present — overturn
rates per check with adjusted prevalence. Prints markdown tables and writes
aggregates.json.

Usage:
    python backend/scripts/corpus/aggregate_corpus.py [--verdicts ...]
"""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timezone

from common import DATA_DIR, json_dump, read_jsonl

from scanner.corpus_stats import (
    credential_class,
    env_label_class,
    grade_from_score,
    overturn_by_class,
    security_score,
    wilson_ci,
)


def _pct(k: int, n: int) -> str:
    if n == 0:
        return "—"
    lo, hi = wilson_ci(k, n)
    return f"{100*k/n:.1f}% (CI {100*lo:.1f}–{100*hi:.1f})"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dir", default=DATA_DIR)
    ap.add_argument("--platform", default="Lovable")
    ap.add_argument("--results", default=None)
    ap.add_argument("--verdicts", default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    results = [r for r in read_jsonl(args.results or os.path.join(args.dir, "scan-results.jsonl")) if r.get("ok")]
    verdicts = read_jsonl(args.verdicts or os.path.join(args.dir, "verdicts.jsonl"))
    n = len(results)
    if n == 0:
        print("no scan results")
        return

    # ── existence checks (the durable figures) ──
    env_k = sum(1 for r in results if r["env_files"])
    gi_k = sum(1 for r in results if r["gitignore_missing"])
    giant_k = sum(1 for r in results if r["giant_files"])
    curl_k = sum(1 for r in results if r["curl_pipe"])
    plat_k = sum(1 for r in results if r["platform_confirmed"])
    dup_k = sum(1 for r in results
                if any(f["check_id"] == "duplicate_files" for f in r["findings"]))

    # ── per-check and per-class prevalence ──
    # check_repos counts distinct repos per check (a repo trips a check once,
    # no matter how many findings it has); check_findings counts findings.
    check_repos: Counter[str] = Counter()
    check_findings: Counter[str] = Counter()
    for r in results:
        seen: set[str] = set()
        for f in r["findings"]:
            check_findings[f["check_id"]] += 1
            seen.add(f["check_id"])
        for cid in seen:
            check_repos[cid] += 1
    class_repos: Counter[str] = Counter()
    class_findings: Counter[str] = Counter()
    for r in results:
        seen_classes: set[str] = set()
        for f in r["findings"]:
            cls = credential_class(f["check_id"])
            if cls is None and f["check_id"] == "env_committed_secret":
                cls = env_label_class(f.get("preview", ""))
            if cls:
                seen_classes.add(cls)
                class_findings[cls] += 1
        for cls in seen_classes:
            class_repos[cls] += 1

    # ── security score / grade ──
    scores = [security_score(r["findings"]) for r in results]
    grades = Counter(grade_from_score(s) for s in scores)
    # Nearest-rank convention: q1/q3 and the median are actual observed
    # scores (index len//4, 3*len//4, len//2 of the sorted list).
    sorted_scores = sorted(scores)
    median = sorted_scores[len(sorted_scores) // 2]
    q1 = sorted_scores[len(sorted_scores) // 4]
    q3 = sorted_scores[3 * len(sorted_scores) // 4]
    mean = sum(sorted_scores) / n
    bands = Counter(s // 10 * 10 for s in sorted_scores)
    clean_k = sum(1 for r in results if not r["findings"])

    # ── verdicts: overturn per check + per credential class ──
    overturn: dict[str, tuple[int, int]] = defaultdict(lambda: (0, 0))  # dropped, total
    for v in verdicts:
        total = overturn[v["check_id"]][1] + 1
        dropped = overturn[v["check_id"]][0] + (1 if v.get("verdict") == "drop" else 0)
        overturn[v["check_id"]] = (dropped, total)
    # Roll verdicts up to credential classes (the class table reports classes,
    # not check ids — joining through the same mapping the class counts use).
    class_overturn = overturn_by_class(verdicts)

    def _ci(k: int, n: int) -> dict:
        lo, hi = wilson_ci(k, n)
        return {"value": k / n if n else 0, "ci_low": lo, "ci_high": hi}

    out = {
        "n": n,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "existence": {
            "env_committed": {"count": env_k, **_ci(env_k, n)},
            "gitignore_missing": {"count": gi_k, **_ci(gi_k, n)},
            "giant_file": {"count": giant_k, **_ci(giant_k, n)},
            "curl_pipe_sh": {"count": curl_k, **_ci(curl_k, n)},
            "platform_confirmed": {"count": plat_k, **_ci(plat_k, n)},
            "duplicate_family": {"count": dup_k, **_ci(dup_k, n)},
        },
        "findings": {
            "total": sum(len(r["findings"]) for r in results),
            "clean_repos": {"count": clean_k, **_ci(clean_k, n)},
            "median_score": median,
            "mean_score": round(mean, 1),
            "quartiles": {"q1": q1, "median": median, "q3": q3},
            "score_bands": {str(b): c for b, c in sorted(bands.items())},
            "grades": {g: {"count": c, **_ci(c, n)} for g, c in grades.items()},
            "per_check": {
                cid: {
                    "findings": check_findings[cid],
                    "repos": c,
                    "pct": 100 * c / n,
                    **_ci(c, n),
                }
                for cid, c in check_repos.items()
            },
            "per_class": {
                cls: {
                    "findings": class_findings[cls],
                    "repos": c,
                    "pct": 100 * c / n,
                    **_ci(c, n),
                }
                for cls, c in class_repos.items()
            },
        },
        "verification": {
            "tasks": len(verdicts),
            "overturn_per_check": {cid: {"dropped": d, "total": t}
                                   for cid, (d, t) in overturn.items()},
        },
    }

    print(f"## Corpus: {n} {args.platform} apps (archive scan, Septr rules engine)\n")
    print("### Existence checks (durable figures)")
    print(f"| check | repos | proportion |")
    print("|---|---|---|")
    print(f"| committed .env | {env_k} | {_pct(env_k, n)} |")
    print(f"| no root .gitignore | {gi_k} | {_pct(gi_k, n)} |")
    print(f"| giant text file (>1MB) | {giant_k} | {_pct(giant_k, n)} |")
    print(f"| curl | sh pattern | {curl_k} | {_pct(curl_k, n)} |")
    print(f"| lovable-tagger confirmed ({args.platform} signal) | {plat_k} | {_pct(plat_k, n)} |")
    print(f"| duplicated file family (≥3 copies, scored low) | {dup_k} | {_pct(dup_k, n)} |")

    print("\n### Credential classes (% of repos, rule output before verification)")
    print("| class | findings | repos | proportion | adjusted |")
    print("|---|---|---|---|---|")
    for cls, c in class_repos.most_common():
        fc = class_findings[cls]
        d, t = class_overturn.get(cls, (0, 0))
        adj = ""
        if t:
            adj_val = c * (1 - d / t)
            adj = f"~{100*adj_val/n:.0f}% (verif {t}, dropped {d})"
        print(f"| {cls} | {fc} | {c} | {_pct(c, n)} | {adj} |")

    print("\n### Grades (security score, 100 − per-finding points, floor 0)")
    print(f"median score {median}; mean {mean:.1f}; q1 {q1} / q3 {q3}; "
          f"clean: {clean_k} ({_pct(clean_k, n)})")
    bands_str = ", ".join(
        f"{b}+: {bands[b]}" if b == 100 else f"{b}–{b + 9}: {bands[b]}"
        for b in sorted(bands, reverse=True)
    )
    print(f"score bands: {bands_str}")
    for g in ("A", "B", "C", "D", "F"):
        c = grades.get(g, 0)
        print(f"- {g}: {c} ({_pct(c, n)})")

    if overturn:
        print("\n### Verification subsample (overturn by check)")
        for cid, (d, t) in sorted(overturn.items(), key=lambda kv: -kv[1][0] / max(kv[1][1], 1)):
            print(f"- {cid}: {d}/{t} dropped")

    json_dump(args.out or os.path.join(args.dir, "aggregates.json"), out)
    print(f"\naggregates → {args.out or os.path.join(args.dir, 'aggregates.json')}")


if __name__ == "__main__":
    main()
