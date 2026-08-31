"""Septr Scan: archive-level existence checks for corpus studies.

These checks answer "is X present in the committed archive" — the class of
finding the ogbuilds study showed is never overturned by adversarial
verification (a file is either in the archive or it is not). They are pure
functions over file listings and text; no network, no state.
"""

from __future__ import annotations

import hashlib
import json
import re

GIANT_FILE_BYTES = 1024 * 1024

# Root-level .env family: .env, .env.local, .env.production, ...
# .env.example / .env.sample are templates, committed by design — excluded.
_ENV_FILE_RE = re.compile(r"^\.env(\.[a-z0-9_-]+)?$", re.I)
_ENV_EXCLUDED = {".env.example", ".env.sample"}

# curl ... | sh / bash / zsh (optionally through sudo), the install-pipe pattern.
_CURL_PIPE_RE = re.compile(
    r"curl[^\n|;]*\|\s*(?:sudo\s+)?(?:sh|bash|zsh)\b", re.I
)

_TEXT_EXTS = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".json", ".html",
              ".css", ".scss", ".py", ".go", ".rs", ".java", ".rb", ".php",
              ".sql", ".md", ".txt", ".yml", ".yaml", ".toml", ".ini", ".cfg",
              ".env", ".sh", ".bash", ".zsh", ".dockerfile", ".conf"}
_TEXT_NAMES = {".env", ".env.local", ".env.production", ".env.development",
               "dockerfile", "makefile", ".gitignore", ".npmrc", ".yarnrc"}


def env_files_committed(paths: list[str]) -> list[str]:
    """Absolute paths whose basename is a committed .env file
    (.env.example / .env.sample templates do not count)."""
    out = []
    for p in paths:
        base = p.rsplit("/", 1)[-1]
        if base not in _ENV_EXCLUDED and _ENV_FILE_RE.match(base):
            out.append(p)
    return out


def gitignore_missing(paths: list[str]) -> bool:
    """True when no root-level .gitignore exists in the archive.

    Callers must pass repo-root-relative paths (no leading directory).
    """
    return ".gitignore" not in {p.rsplit("/", 1)[-1] for p in paths if "/" not in p}


def giant_files(sizes: list[tuple[str, int]]) -> list[tuple[str, int]]:
    """(path, bytes) pairs for text-ish files over 1 MB."""
    return [(p, n) for p, n in sizes if n > GIANT_FILE_BYTES]


def curl_pipe_sh(text: str) -> bool:
    """True when a script pipes curl straight into a shell."""
    return bool(_CURL_PIPE_RE.search(text or ""))


def prune_vendored(dir_path: str) -> bool:
    """True for the Go module cache layout `pkg/mod` at any depth.

    Vendored dependency trees (Go's equivalent of node_modules) are skipped
    by walk loops, but name-based skip sets can't express it: "pkg" is a
    legit source-dir convention and "mod" is too generic. The v0 corpus
    showed the cost at scale — private-key testdata and hash fixtures under
    `pkg/mod/golang.org/x/crypto/.../testdata` produced 20/20 false
    positives (verified by adjudication, matching betterleaks' identical
    blind spot on the same archives).
    """
    parts = dir_path.replace("\\", "/").rstrip("/").split("/")
    return len(parts) >= 2 and parts[-2] == "pkg" and parts[-1] == "mod"


def lovable_tagger_confirmed(package_json_texts: list[str]) -> bool:
    """True when any fetched package.json references the lovable-tagger
    vite plugin — the signal Lovable writes into every generated project."""
    return any("lovable-tagger" in (t or "") for t in package_json_texts)


def v0_confirmed(markup_texts: list[str]) -> bool:
    """True when any HTML/TSX file carries a data-v0-* attribute — the
    marker v0.dev writes into every generated component. Verified against
    a spike of the frame signal (data-v0- language:HTML / extension:tsx)."""
    return any("data-v0-" in (t or "") for t in markup_texts)


_AICODED_MARKERS = (
    "vibe-coded", "vibe coded", "vibe-coded ", "ai-generated",
    "ai generated", "generated with ai", "built with ai",
)


def aicoded_confirmed(readme_texts: list[str]) -> bool:
    """True when any README describes the repo as AI-coded — the frame
    signal for the general AI-coded corpus (self-description, the same
    population ogbuilds used for their 549-repo cross-corpus)."""
    lowered = " ".join((t or "").lower() for t in readme_texts)
    return any(m in lowered for m in _AICODED_MARKERS)


_JS_FRAMEWORKS = (
    "next", "react", "vue", "svelte", "angular", "nuxt", "vite",
    "express", "fastify", "astro", "remix", "gatsby", "sveltekit",
)
_PY_FRAMEWORKS = ("fastapi", "django", "flask", "streamlit", "gradio")


def app_shape_from_manifests(package_json_texts: list[str],
                             requirements_texts: list[str]) -> dict:
    """App-shape signal: does this repo look like a real application rather
    than a tutorial/collection? Presence of a dependency manifest and a
    recognizable framework, read from package.json deps and requirements.txt.

    Used to filter the self-described AI-coded frame down to app-shaped
    repos — the fair baseline for 'AI-built apps without a generator
    signal' (a 17-file repo with no package.json has nothing to leak).
    """
    shape = {
        "has_package_json": bool(package_json_texts),
        "has_requirements": bool(requirements_texts),
        "framework": "",
    }
    for text in package_json_texts:
        try:
            data = json.loads(text)
        except Exception:
            continue
        deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
        for fw in _JS_FRAMEWORKS:
            if any(fw == d or d.startswith(fw) for d in deps):
                shape["framework"] = fw
                break
        if shape["framework"]:
            break
    if not shape["framework"]:
        joined = " ".join(requirements_texts).lower()
        for fw in _PY_FRAMEWORKS:
            if fw in joined:
                shape["framework"] = fw
                break
    return shape


def content_hash(text: str) -> str:
    """Deterministic content digest for duplicate detection."""
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()


def duplicate_families(groups: dict[str, list[str]], min_copies: int = 3) -> list[dict]:
    """Families of >= min_copies files with identical content.

    `groups` maps a content hash to the paths sharing it (the caller hashes
    each scanned text file once). Returns one entry per family, largest
    first: {"count": n, "paths": [sorted paths]}. The same file copied into
    many places is the ogbuilds rule class that never overturns in
    adversarial verification.
    """
    out = []
    for members in groups.values():
        if len(members) >= min_copies:
            out.append({"count": len(members), "paths": sorted(members)})
    out.sort(key=lambda fam: -fam["count"])
    return out


def is_text_file(path: str) -> bool:
    """Heuristic: extension or known name suggests a scannable text file."""
    name = path.rsplit("/", 1)[-1].lower()
    if name in _TEXT_NAMES:
        return True
    if "." in path:
        ext = "." + path.rsplit(".", 1)[-1].lower()
        return ext in _TEXT_EXTS
    return False


def env_committed_findings(
    env_files: list[str],
    lines_by_file: dict[str, list],
) -> list[dict]:
    """Content-derived findings for committed .env files.

    The classifier is the single authority for env-file content: the caller
    suppresses bundle findings for these files, so nothing double-counts and
    nothing is skipped. One finding per live-secret line (at that line's
    severity); a file with no live secrets gets one low finding (hygiene
    signal, not an active exposure).
    """
    from scanner.env_probe import KIND_SECRET

    out: list[dict] = []
    for path in env_files:
        lines = lines_by_file.get(path, [])
        secrets = [l for l in lines if l.kind == KIND_SECRET]
        if secrets:
            for line in secrets:
                out.append({
                    "check_id": "env_committed_secret",
                    "severity": line.severity,
                    "file": path,
                    "preview": f"{line.key} — {line.label}",
                })
        else:
            out.append({
                "check_id": "env_committed",
                "severity": "low",
                "file": path,
                "preview": "committed .env — no live secrets "
                           "(public-by-design or placeholder values)",
            })
    return out
