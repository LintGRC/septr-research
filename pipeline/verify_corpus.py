#!/usr/bin/env python3
"""Step 4 — emit the verification task for in-window adjudication.

Samples repos from scan-results, and for each finding re-extracts the
archive to build a redacted context window (the matched value is replaced
with its redacted form, never stored raw). Writes verify-task.jsonl, which
is meant to be adjudicated by an LLM operator (e.g. the agent that built
the pipeline) and answered as verdicts.jsonl.

Usage:
    python backend/scripts/corpus/verify_corpus.py --repos 25 --seed 20260812
"""

from __future__ import annotations

import argparse
import json
import os
import random
import tarfile
import tempfile

from common import DATA_DIR, read_jsonl, repo_id, write_jsonl

from scanner.checks import BUNDLE_CHECKS, redact

CHECKS_BY_ID = {c.id: c for c in BUNDLE_CHECKS}

# Content-classified existence/hygiene checks — not pattern rules; excluded
# from LLM verification (the existence class is never overturned).
EXISTENCE_CHECK_IDS = ("env_committed", "env_committed_secret", "duplicate_files")

CONTEXT_WINDOW = 160
MAX_FILE_BYTES = 4 * 1024 * 1024


def build_context(archive_path: str, file_rel: str, check_id: str) -> str:
    """Re-extract the archive and return a redacted context window around
    the first pattern match of the check in the given file."""
    check = CHECKS_BY_ID.get(check_id)
    if check is None or check.pattern is None:
        return ""
    with tempfile.TemporaryDirectory() as tmp:
        try:
            with tarfile.open(archive_path, "r:gz") as tf:
                # scan-results `file` already includes the repo-root directory
                # (e.g. "owner-repo-main/src/lib/client.ts"); match it exactly.
                target = file_rel.lstrip("/")
                fpath = None
                for member in tf.getmembers():
                    if member.isfile() and member.name.replace("\\", "/") == target:
                        member.name = os.path.basename(member.name)
                        tf.extract(member, tmp)
                        fpath = os.path.join(tmp, os.path.basename(member.name))
                        break
                if fpath is None:
                    return ""
        except (tarfile.TarError, EOFError, OSError, IndexError):
            return ""
        try:
            with open(fpath, encoding="utf-8", errors="replace") as fh:
                text = fh.read(MAX_FILE_BYTES)
        except (OSError, TypeError):
            return ""
        m = check.pattern.search(text)
        if not m:
            return ""
        raw = m.group(0)
        start = max(0, m.start() - CONTEXT_WINDOW)
        end = min(len(text), m.end() + CONTEXT_WINDOW)
        window = text[start:end].replace("\n", "⏎")
        return window.replace(raw, redact(raw)) if raw else window


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dir", default=DATA_DIR)
    ap.add_argument("--results", default=None)
    ap.add_argument("--repos", type=int, default=25)
    ap.add_argument("--seed", type=int, default=20260812)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    results = read_jsonl(args.results or os.path.join(args.dir, "scan-results.jsonl"))
    archives_dir = os.path.join(args.dir, "archives")

    with_findings = [
        r for r in results
        if r.get("ok") and any(f["check_id"] not in EXISTENCE_CHECK_IDS for f in r.get("findings", []))
    ]
    if not with_findings:
        print("no scanned repos with findings — nothing to verify")
        return
    rng = random.Random(args.seed)
    # Sort by repo id so the sample is deterministic across scan runs
    # (ThreadPoolExecutor completion order is not).
    sampled = rng.sample(sorted(with_findings, key=lambda r: r["id"]),
                         min(args.repos, len(with_findings)))
    print(f"{len(sampled)} repos sampled for verification (seed {args.seed})")

    tasks: list[dict] = []
    for repo in sampled:
        archive = os.path.join(archives_dir, f"{repo['id']}.tar.gz")
        if not os.path.exists(archive):
            continue
        j = 0
        for f in repo["findings"]:
            if f["check_id"] in EXISTENCE_CHECK_IDS:
                continue
            context = build_context(archive, f["file"], f["check_id"])
            tasks.append({
                "task_id": f"{repo['id']}-{j}",
                "repo_id": repo["id"],
                "check_id": f["check_id"],
                "severity": f["severity"],
                "file": f["file"],
                "preview": f["preview"],
                "context": context[:600],
            })
            j += 1

    out_path = args.out or os.path.join(args.dir, "verify-task.jsonl")
    write_jsonl(out_path, tasks)
    print(f"{len(tasks)} verification tasks → {out_path}")


if __name__ == "__main__":
    main()
