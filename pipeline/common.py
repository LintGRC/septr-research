"""Shared helpers for the corpus pipeline scripts (staged research repo).

This is a tailored copy for the standalone septr-research layout: the
`scanner` package lives next to the scripts (pipeline/scanner), and the
published data lives at ../data. The monorepo original computes paths
relative to the backend package; here everything resolves locally.

Scripts run from anywhere; this module puts the local pipeline on
sys.path and provides GitHub auth + a polite HTTP client.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

PIPELINE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.normpath(os.path.join(PIPELINE_DIR, "..", "data"))
if PIPELINE_DIR not in sys.path:
    sys.path.insert(0, PIPELINE_DIR)

SEARCH_RATE_SLEEP = 2.2  # seconds between code-search requests (30/min limit)

_token_cache: str | None = None


def github_token() -> str:
    """GITHUB_TOKEN env var, falling back to the git credential helper."""
    global _token_cache
    if _token_cache is not None:
        return _token_cache
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        try:
            out = subprocess.run(
                ["git", "credential", "fill"],
                input="protocol=https\nhost=github.com\n\n",
                capture_output=True, text=True, timeout=10,
            ).stdout
            for line in out.splitlines():
                if line.startswith("password="):
                    token = line[len("password="):].strip()
        except Exception:
            pass
    if not token:
        sys.exit("No GitHub token: set GITHUB_TOKEN (or gh auth login / git credential helper).")
    _token_cache = token
    return token


def api_get_json(url: str, token: str, retries: int = 5) -> dict:
    """GET a GitHub API URL with rate-limit backoff. Returns parsed JSON."""
    last_err: Exception | None = None
    for attempt in range(retries):
        req = urllib.request.Request(
            url, headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json_load(resp.read())
        except urllib.error.HTTPError as e:
            if e.code == 403 and (e.headers.get("x-ratelimit-remaining") == "0"):
                reset = int(e.headers.get("x-ratelimit-reset", "0"))
                wait = max(reset - int(time.time()), 5) + 1
                print(f"  rate limited — sleeping {wait}s", file=sys.stderr)
                time.sleep(min(wait, 120))
                continue
            if e.code == 404:
                raise
            last_err = e
        except Exception as e:
            last_err = e
        time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"GitHub API failed after {retries} attempts: {last_err}")


def json_load(data: bytes) -> dict:
    import json
    return json.loads(data.decode("utf-8", errors="replace"))


def json_dump(path: str, obj: object) -> None:
    import json
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        json.dump(obj, fh, indent=2)


def read_jsonl(path: str) -> list[dict]:
    import json
    rows = []
    if os.path.exists(path):
        with open(path) as fh:
            for line in fh:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
    return rows


def write_jsonl(path: str, rows: list[dict]) -> None:
    import json
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")


def repo_id(full_name: str) -> str:
    import hashlib
    return hashlib.sha256(full_name.encode()).hexdigest()[:12]
