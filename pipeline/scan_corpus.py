#!/usr/bin/env python3
"""Step 3 — scan downloaded archives with the Septr rules engine.

For each archive: extract, run the existence checks (env committed,
gitignore, giant files, curl-pipe, lovable-tagger confirm) and the bundle
rules engine over every text file. Writes one JSONL row per repo. Only
redacted previews are stored — raw values never touch the results file.

Usage:
    python backend/scripts/corpus/scan_corpus.py --workers 4
"""

from __future__ import annotations

import argparse
import json
import os
import tarfile
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed

from common import DATA_DIR, read_jsonl, repo_id, write_jsonl

from scanner.checks import scan_all_bundle
from scanner.corpus_checks import (
    aicoded_confirmed,
    app_shape_from_manifests,
    content_hash,
    curl_pipe_sh,
    duplicate_families,
    env_committed_findings,
    env_files_committed,
    giant_files,
    gitignore_missing,
    is_text_file,
    lovable_tagger_confirmed,
    prune_vendored,
    v0_confirmed,
)
from scanner.env_probe import classify_env
from scanner.fetcher import MAX_ENV_CONTENT_BYTES

IGNORE_DIRS = {
    "node_modules", ".git", "dist", ".next", ".nuxt", ".output", "build",
    "__pycache__", ".venv", "venv", "vendor", ".cache", ".pytest_cache",
}
MAX_FILE_BYTES = 4 * 1024 * 1024
MAX_PKG_BYTES = 256 * 1024
DUP_MAX_BYTES = 1024 * 1024  # files over 1 MB are already giant-file flags

# platform confirmation: which files to sniff for the marker, and the check
PLATFORM_CONFIRM = {
    "lovable": (lambda rel: rel.endswith("package.json"), lovable_tagger_confirmed),
    "v0": (lambda rel: rel.endswith((".html", ".htm", ".tsx", ".jsx")), v0_confirmed),
    "aicoded": (lambda rel: "readme" in rel.lower(), aicoded_confirmed),
}

_pkg_texts: list[str] = []


def _safe_extract(tf: tarfile.TarFile, dest: str) -> None:
    for member in tf.getmembers():
        name = member.name.replace("\\", "/")
        if ".." in name.split("/") or name.startswith("/"):
            continue
        member.name = name
        try:
            tf.extract(member, dest)
        except Exception:
            continue


def scan_archive(archive_path: str, rid: str, platform: str = "lovable") -> dict:
    row = {"id": rid, "full_name": "", "ok": False, "env_files": [],
           "gitignore_missing": False, "giant_files": [], "curl_pipe": False,
           "platform_confirmed": False, "files": 0, "bytes": 0, "findings": []}
    with tempfile.TemporaryDirectory() as tmp:
        try:
            with tarfile.open(archive_path, "r:gz") as tf:
                members = [m for m in tf.getmembers() if m.isfile()]
                if not members:
                    return row
                root = members[0].name.split("/")[0]
                row["full_name"] = root
                _safe_extract(tf, tmp)
        except (tarfile.TarError, EOFError, OSError) as e:
            row["ok"] = False
            return row

        root_dir = os.path.join(tmp, root)
        paths: list[str] = []
        file_sizes: list[tuple[str, int]] = []  # (archive-relative, bytes)
        for dirpath, dirnames, filenames in os.walk(root_dir):
            dirnames[:] = [d for d in dirnames
                           if d not in IGNORE_DIRS
                           and not prune_vendored(os.path.join(dirpath, d))]
            for fname in filenames:
                full = os.path.join(dirpath, fname)
                try:
                    size = os.path.getsize(full)
                except OSError:
                    continue  # broken symlink / unextractable member
                # repo-root-relative path for existence checks (no prefix)
                repo_rel = os.path.relpath(full, root_dir).replace(os.sep, "/")
                # archive-relative path (with root prefix) for findings, so the
                # verifier can re-locate the file inside the tarball
                rel = os.path.relpath(full, tmp).replace(os.sep, "/")
                paths.append(repo_rel)
                file_sizes.append((rel, size))
                row["bytes"] += size
                row["files"] += 1

        row["env_files"] = env_files_committed(paths)
        row["gitignore_missing"] = gitignore_missing(paths)
        row["giant_files"] = [p for p, _ in giant_files(file_sizes) if is_text_file(p)][:5]
        # Archive-relative env paths: the classifier below is the single
        # authority for these files, so the bundle scan skips them entirely
        # (no double-counting, no skipped secrets).
        env_archive = {f"{root}/{p}" for p in row["env_files"]}

        pkg_texts: list[str] = []
        confirm_ext, confirm_fn = PLATFORM_CONFIRM[platform]
        for rel, size in file_sizes:
            if size > MAX_PKG_BYTES or not confirm_ext(rel):
                continue
            try:
                with open(os.path.join(tmp, rel), encoding="utf-8", errors="replace") as fh:
                    pkg_texts.append(fh.read(MAX_PKG_BYTES))
            except OSError:
                continue
        row["platform_confirmed"] = confirm_fn(pkg_texts)

        # App-shape: dependency manifests + framework (all platforms) —
        # lets the AI-coded study filter to app-shaped repos.
        manifest_texts: dict[str, list[str]] = {"package.json": [], "requirements.txt": []}
        for rel, size in file_sizes:
            name = rel.rsplit("/", 1)[-1]
            if size > MAX_PKG_BYTES or name not in manifest_texts:
                continue
            try:
                with open(os.path.join(tmp, rel), encoding="utf-8", errors="replace") as fh:
                    manifest_texts[name].append(fh.read(MAX_PKG_BYTES))
            except OSError:
                continue
        row["app_shape"] = app_shape_from_manifests(
            manifest_texts["package.json"], manifest_texts["requirements.txt"]
        )

        dup_groups: dict[str, list[str]] = {}
        for rel, size in file_sizes:
            if size > MAX_FILE_BYTES or not is_text_file(rel):
                continue
            if rel in env_archive:
                continue
            try:
                with open(os.path.join(tmp, rel), encoding="utf-8", errors="replace") as fh:
                    text = fh.read(MAX_FILE_BYTES)
            except OSError:
                continue
            if not row["curl_pipe"] and curl_pipe_sh(text):
                row["curl_pipe"] = True
            for m in scan_all_bundle(text):
                row["findings"].append({
                    "check_id": m.check_id,
                    "severity": m.severity,
                    "file": rel,
                    "preview": m.preview,
                })
            if size <= DUP_MAX_BYTES and text:
                dup_groups.setdefault(content_hash(text), []).append(rel)

        # Committed .env files: classified content (per-secret findings),
        # appended after the bundle findings so earlier finding indexes (and
        # verification task ids) stay stable.
        lines_by_file: dict[str, list] = {}
        for rel, size in file_sizes:
            if size > MAX_ENV_CONTENT_BYTES or rel not in env_archive:
                continue
            try:
                with open(os.path.join(tmp, rel), encoding="utf-8", errors="replace") as fh:
                    text = fh.read(MAX_ENV_CONTENT_BYTES)
            except OSError:
                continue
            lines_by_file[rel] = classify_env(text)
        row["findings"].extend(env_committed_findings(env_archive, lines_by_file))

        # Duplicated-file families: content-derived hygiene finding, appended
        # last so bundle finding order (and verification task ids) stay stable.
        # One aggregate finding per repo: a repo that vendors multiple version
        # snapshots can hit hundreds of families, which is one pathology, not
        # hundreds of findings.
        fams = duplicate_families(dup_groups)
        if fams:
            largest = fams[0]
            row["findings"].append({
                "check_id": "duplicate_files",
                "severity": "low",
                "file": largest["paths"][0],
                "preview": (f"{len(fams)} file families with >=3 identical copies "
                            f"(largest: {largest['count']} copies of {largest['paths'][0]})"),
            })
        row["ok"] = True
        return row


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dir", default=DATA_DIR)
    ap.add_argument("--platform", default="lovable",
                    choices=sorted(PLATFORM_CONFIRM))
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    archives_dir = os.path.join(args.dir, "archives")
    out_path = args.out or os.path.join(args.dir, "scan-results.jsonl")
    existing = {r["id"] for r in read_jsonl(out_path)}

    archives = [f for f in sorted(os.listdir(archives_dir)) if f.endswith(".tar.gz")]
    todo = [a for a in archives if a[:-len(".tar.gz")] not in existing]
    print(f"{len(archives)} archives, {len(existing)} already scanned, {len(todo)} to do")

    rows = read_jsonl(out_path)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(scan_archive, os.path.join(archives_dir, a),
                        a[:-len(".tar.gz")], args.platform): a
            for a in todo
        }
        for i, fut in enumerate(as_completed(futures), 1):
            row = fut.result()
            rows.append(row)
            if i % 25 == 0 or i == len(futures):
                found = sum(1 for r in rows if r["ok"])
                print(f"  {i}/{len(todo)} scanned, {found} ok", flush=True)
    write_jsonl(out_path, rows)

    n_ok = sum(1 for r in rows if r["ok"])
    n_env = sum(1 for r in rows if r["env_files"])
    n_clean = sum(1 for r in rows if r["ok"] and not r["findings"])
    print(f"\nscanned {n_ok} repos | env committed: {n_env} | fully clean: {n_clean}")


if __name__ == "__main__":
    main()
