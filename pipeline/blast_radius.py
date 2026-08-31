#!/usr/bin/env python3
"""Blast-radius analysis — what the committed findings would actually do.

The prevalence study counts findings; this flips the axis to consequence.
Every finding (bundle checks, env-file secrets, verification-adjusted) is
mapped to one of four tiers, where tier = what the credential would grant
IF valid:

    A — data access   : grants data read/write/exfiltration (role-verified
                        service_role, live DB credentials, AWS keys, live
                        Stripe/Clerk keys, GitHub tokens, symmetric secrets
                        like JWT_SECRET/ENCRYPTION_KEY)
    B — cost          : burns money if used (OpenAI/Gemini/Anthropic/Resend
                        API keys)
    C — bounded       : safe by design unless misconfigured (anon keys,
                        bounded by RLS; test-mode keys)
    D — none          : hygiene only (duplicate families, benign env files)

No confirmed-live testing: "A" means "would grant access if valid".
Where the format allows, validity is verified structurally — Supabase
roles come from the JWT payload itself (0/269 false positives), Stripe
keys from the sk_live_/sk_test_ prefix. Everything else is inferred from
the credential class.

Usage:
    python backend/scripts/corpus/blast_radius.py [--dir data/corpus] [--out data/corpus]
"""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from datetime import datetime, timezone

from common import DATA_DIR, json_dump, read_jsonl

from scanner.corpus_stats import grade_from_score, security_score, wilson_ci

TIER_A = "A — data access"
TIER_B = "B — cost"
TIER_C = "C — bounded"
TIER_D = "D — none"
TIER_ORDER = [TIER_A, TIER_B, TIER_C, TIER_D]

# ── check_id → tier ──
CHECK_TIER = {
    "supabase_service_role": TIER_A,
    "db_connection_string": TIER_A,
    "aws_access_key": TIER_A,
    "stripe_live_secret": TIER_A,
    "clerk_live_secret": TIER_A,
    "github_token": TIER_A,
    "private_key": TIER_A,
    "gcp_service_account": TIER_A,
    "openai_key": TIER_B,
    "google_gemini_key": TIER_B,
    "anthropic_key": TIER_B,
    "resend_api_key": TIER_B,
    "cloudinary_secret": TIER_B,
    "supabase_anon": TIER_C,
    "stripe_test_secret": TIER_C,
    "clerk_test_secret": TIER_C,
    "google_api_key": TIER_C,
    "hardcoded_id_route": TIER_C,
    "duplicate_files": TIER_D,
    "env_committed": TIER_D,
}

# env-file secret lines carry their class in the preview label
ENV_LABEL_TIER = {
    "Database connection string with credentials": TIER_A,
    "Supabase service_role key": TIER_A,
    "Stripe live secret key exposed": TIER_A,
    "URL with embedded credentials": TIER_A,
    "GitHub token exposed": TIER_A,
    "secret-shaped value under non-public key": TIER_A,
    "OpenAI API key exposed": TIER_B,
    "Google API key exposed": TIER_B,
    "JWT with unknown role": TIER_C,
}


def env_tier(finding: dict) -> str:
    lbl = finding.get("preview", "").split(" — ")[1] if " — " in finding.get("preview", "") else ""
    return ENV_LABEL_TIER.get(lbl, TIER_A if finding.get("severity") == "critical" else TIER_B)


def finding_tier(finding: dict) -> str:
    cid = finding["check_id"]
    if cid == "env_committed_secret":
        return env_tier(finding)
    return CHECK_TIER.get(cid, TIER_D)


def _pct(k: int, n: int) -> str:
    if n == 0:
        return "—"
    lo, hi = wilson_ci(k, n)
    return f"{100 * k / n:.1f}% (CI {100 * lo:.1f}–{100 * hi:.1f})"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dir", default=DATA_DIR)
    ap.add_argument("--results", default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    rows = [r for r in read_jsonl(args.results or os.path.join(args.dir, "scan-results.jsonl")) if r.get("ok")]
    verdicts = read_jsonl(os.path.join(args.dir, "verdicts.jsonl"))
    n = len(rows)

    # ── repo-level tier = highest tier among findings ──
    repo_tier: Counter[str] = Counter()
    tier_by_class: Counter[str] = Counter()
    for r in rows:
        tiers = {finding_tier(f) for f in r["findings"]} - {TIER_D}
        if not tiers:
            repo_tier[TIER_D] += 1
            continue
        top = TIER_ORDER[min(TIER_ORDER.index(t) for t in tiers)]
        repo_tier[top] += 1
        for t in tiers:
            tier_by_class[t] += 1

    # ── the Supabase bound: anon keys are safe *because* of RLS ──
    def has(r, cid):
        return any(f["check_id"] == cid for f in r["findings"])

    anon_repos = [r for r in rows if has(r, "supabase_anon")]
    anon_rls_off = [r for r in anon_repos if has(r, "supabase_rls_disabled")]
    anon_rls_on = len(anon_repos) - len(anon_rls_off)
    svc_repos = [r for r in rows if has(r, "supabase_service_role")]

    # structural subset of tier A: credential classes whose blast radius is
    # verified from the value's own format/type (JWT payload role, live
    # prefixes, credential-bearing connection strings) — no shape guessing.
    STRUCTURAL_A = {
        "supabase_service_role", "db_connection_string", "aws_access_key",
        "stripe_live_secret", "clerk_live_secret", "github_token",
    }
    structural_a = sum(1 for r in rows
                       if any(f["check_id"] in STRUCTURAL_A for f in r["findings"])
                       or any(f["check_id"] == "env_committed_secret"
                              and f["severity"] == "critical" for f in r["findings"]))

    # ── env lines by tier ──
    env_lines: Counter[str] = Counter()
    for r in rows:
        for f in r["findings"]:
            if f["check_id"] == "env_committed_secret":
                env_lines[finding_tier(f)] += 1
    env_repos: Counter[str] = Counter()
    for r in rows:
        seen = set()
        for f in r["findings"]:
            if f["check_id"] == "env_committed_secret":
                seen.add(finding_tier(f))
        for t in seen:
            env_repos[t] += 1

    # ── verification context: classes with 0 drops hold their tier ──
    zero_drop = []
    per_check: Counter[str] = Counter()
    total: Counter[str] = Counter()
    for v in verdicts:
        total[v["check_id"]] += 1
        if v.get("verdict") == "drop":
            per_check[v["check_id"]] += 1
    for cid, t in total.items():
        if per_check.get(cid, 0) == 0 and cid in CHECK_TIER and CHECK_TIER[cid] in (TIER_A, TIER_B):
            zero_drop.append(cid)

    out = {
        "n": n,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo_tiers": {t: repo_tier[t] for t in TIER_ORDER},
        "class_hits": dict(tier_by_class),
        "supabase_bound": {
            "anon_repos": len(anon_repos),
            "rls_enabled": anon_rls_on,
            "rls_disabled": len(anon_rls_off),
            "service_role_repos": len(svc_repos),
        },
        "tier_a_structural_repos": structural_a,
        "env_secret_lines": {t: env_lines[t] for t in TIER_ORDER},
        "env_secret_repos": {t: env_repos[t] for t in TIER_ORDER},
        "verified_zero_drop_classes": zero_drop,
    }
    json_dump(args.out or os.path.join(args.dir, "blast-radius.json"), out)

    print(f"## Blast radius (N = {n}) — what the findings would actually do\n")
    print("Repo tier = highest blast radius among the repo's findings "
          "(A > B > C > D).")
    print("| tier | repos | proportion |")
    print("|---|---|---|")
    for t in TIER_ORDER:
        print(f"| {t} | {repo_tier[t]} | {_pct(repo_tier[t], n)} |")
    print()
    print("### The Supabase bound")
    print(f"- anon-key repos: **{len(anon_repos)}** ({_pct(len(anon_repos), n)})")
    print(f"- of those, RLS disabled: **{len(anon_rls_off)}** "
          f"({100 * len(anon_rls_off) / max(len(anon_repos), 1):.1f}% of "
          f"anon repos) — the anon key is bounded by RLS, and the bound is off")
    print(f"- service_role repos: **{len(svc_repos)}** "
          f"({100 * len(svc_repos) / max(len(anon_repos), 1):.1f}% of Supabase apps) — "
          f"role-verified from the JWT payload, bypasses RLS entirely")
    print(f"- structurally verified tier-A repos (role-verified JWTs, live "
          f"prefixes, credential-bearing DB strings, critical .env lines): "
          f"**{structural_a}** ({_pct(structural_a, n)})")
    print()
    print("### Committed .env secret lines by tier")
    print("| tier | lines | repos |")
    print("|---|---|---|")
    for t in TIER_ORDER:
        print(f"| {t} | {env_lines[t]} | {env_repos[t]} |")
    print()
    if zero_drop:
        print("Verified at zero drops (hold their tier at scale): "
              + ", ".join(zero_drop))


def finding_tier_from_repo(r):
    tiers = {finding_tier(f) for f in r["findings"]} - {TIER_D}
    if not tiers:
        return TIER_D
    return TIER_ORDER[min(TIER_ORDER.index(t) for t in tiers)]


if __name__ == "__main__":
    main()
