#!/usr/bin/env python3
"""Step 2 — sample the frame and download repo archives.

Downloads codeload tarballs for a fixed-seed sample of the frame, streaming
with a byte cap. Resumes across restarts (existing archives are skipped).
Failures are recorded in the manifest, not raised.

Usage:
    python backend/scripts/corpus/download_corpus.py \
        --frame backend/data/corpus/frame.json --count 1000 --seed 20260812 \
        --workers 8
"""

from __future__ import annotations

import argparse
import json
import os
import random
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

from common import DATA_DIR, api_get_json, github_token, json_dump, repo_id

MAX_REPO_BYTES = 150 * 1024 * 1024
_BRANCH_CACHE: dict[str, str] = {}


def default_branch(token: str, full_name: str) -> str:
    if full_name in _BRANCH_CACHE:
        return _BRANCH_CACHE[full_name]
    data = api_get_json(f"https://api.github.com/repos/{full_name}", token)
    branch = data.get("default_branch", "main")
    _BRANCH_CACHE[full_name] = branch
    return branch


def download_one(token: str, repo: dict, archives_dir: str, manifest: dict) -> dict:
    full = repo["full_name"]
    rid = repo["id"]
    dest = os.path.join(archives_dir, f"{rid}.tar.gz")
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        return {"id": rid, "full_name": full, "status": "already", "bytes": os.path.getsize(dest)}
    branch = default_branch(token, full)
    url = f"https://codeload.github.com/{full}/tar.gz/refs/heads/{branch}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Septr-Corpus/1.0"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            content_length = int(resp.headers.get("content-length") or 0)
            if content_length > MAX_REPO_BYTES:
                return {"id": rid, "full_name": full, "status": "too_large", "bytes": content_length}
            total = 0
            with open(dest, "wb") as fh:
                while True:
                    chunk = resp.read(1024 * 256)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > MAX_REPO_BYTES:
                        os.remove(dest)
                        return {"id": rid, "full_name": full, "status": "too_large", "bytes": total}
                    fh.write(chunk)
        manifest[rid] = {"full_name": full, "status": "downloaded", "bytes": total}
        return {"id": rid, "full_name": full, "status": "downloaded", "bytes": total}
    except urllib.error.HTTPError as e:
        return {"id": rid, "full_name": full, "status": f"http_{e.code}", "bytes": 0}
    except Exception as e:
        return {"id": rid, "full_name": full, "status": "error", "detail": str(e)[:120], "bytes": 0}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--frame", default=os.path.join(DATA_DIR, "frame.json"))
    ap.add_argument("--count", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=20260812)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--out", default=DATA_DIR)
    args = ap.parse_args()

    with open(args.frame) as fh:
        frame = json.load(fh)
    repos = frame["repos"]
    rng = random.Random(args.seed)
    sampled = rng.sample(repos, min(args.count, len(repos)))
    print(f"sampled {len(sampled)} repos (seed {args.seed}) from frame of {len(repos)}")

    archives_dir = os.path.join(args.out, "archives")
    os.makedirs(archives_dir, exist_ok=True)
    manifest_path = os.path.join(args.out, "download-manifest.json")
    manifest: dict = {}
    if os.path.exists(manifest_path):
        with open(manifest_path) as fh:
            manifest = json.load(fh)

    token = github_token()
    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(download_one, token, r, archives_dir, manifest): r for r in sampled}
        for i, fut in enumerate(as_completed(futures), 1):
            res = fut.result()
            results.append(res)
            if res["status"] in ("downloaded", "already"):
                manifest[res["id"]] = {"full_name": res["full_name"], "status": "downloaded",
                                       "bytes": res["bytes"]}
            if i % 25 == 0 or i == len(futures):
                statuses = {}
                for r in results:
                    statuses[r["status"]] = statuses.get(r["status"], 0) + 1
                print(f"  {i}/{len(futures)} {statuses}", flush=True)

    json_dump(manifest_path, manifest)
    print(f"done: {sum(1 for r in results if r['status'] in ('downloaded','already'))} "
          f"archives in {archives_dir}")


if __name__ == "__main__":
    main()
