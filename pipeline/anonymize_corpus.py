#!/usr/bin/env python3
"""Step 6 — produce the published, anonymized rows.

Maps repo ids to sequential app-XXX ids (deterministic, sorted by id),
strips the repo-root directory segment from finding paths, and drops
full_name. Preview strings are already redacted at scan time — nothing raw
is re-emitted here.

Usage:
    python backend/scripts/corpus/anonymize_corpus.py
"""

from __future__ import annotations

import argparse
import os

from common import DATA_DIR, read_jsonl, write_jsonl


def _strip_root(path: str) -> str:
    parts = path.split("/")
    return "/".join(parts[1:]) if len(parts) > 1 else path


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dir", default=DATA_DIR)
    args = ap.parse_args()

    scan = read_jsonl(os.path.join(args.dir, "scan-results.jsonl"))
    verdicts = read_jsonl(os.path.join(args.dir, "verdicts.jsonl"))

    ids = sorted({r["id"] for r in scan})
    mapping = {rid: f"app-{i + 1:03d}" for i, rid in enumerate(ids)}

    out_scan = []
    for r in scan:
        row = {k: v for k, v in r.items() if k != "full_name"}
        row["id"] = mapping[r["id"]]
        row["env_files"] = [p for p in r.get("env_files", [])]  # already repo-root-relative
        row["giant_files"] = [_strip_root(p) for p in r.get("giant_files", [])]
        row["findings"] = [dict(f, file=_strip_root(f["file"])) for f in r.get("findings", [])]
        out_scan.append(row)

    out_verdicts = []
    for v in verdicts:
        repo, _, task = v["task_id"].rpartition("-")
        out_verdicts.append({
            "verdict": v["verdict"],
            "confidence": v.get("confidence"),
            "check_id": v["check_id"],
            "reason": v.get("reason", ""),
            "repo": mapping.get(repo, repo),
            "task": task,
        })

    write_jsonl(os.path.join(args.dir, "scan-results.anonymized.jsonl"), out_scan)
    write_jsonl(os.path.join(args.dir, "verdicts.anonymized.jsonl"), out_verdicts)
    print(f"anonymized {len(out_scan)} scan rows, {len(out_verdicts)} verdicts → {args.dir}")


if __name__ == "__main__":
    main()
