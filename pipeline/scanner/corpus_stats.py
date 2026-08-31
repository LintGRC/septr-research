"""Septr Scan: stats helpers for corpus studies (pure, testable)."""

from __future__ import annotations

import math

SEVERITY_POINTS = {"critical": 20, "high": 10, "medium": 5, "low": 2}

CREDENTIAL_CLASS = {
    "supabase_service_role": "supabase jwt",
    "supabase_anon": "supabase jwt",
    "stripe_live_secret": "stripe key",
    "stripe_test_secret": "stripe key",
    "stripe_restricted_key": "stripe key",
    "clerk_live_secret": "clerk key",
    "clerk_test_secret": "clerk key",
    "openai_key": "openai key",
    "anthropic_key": "anthropic key",
    "aws_access_key": "aws key",
    "github_token": "github token",
    "google_api_key": "google api key",
    "google_gemini_key": "google api key",
    "resend_api_key": "resend key",
    "cloudinary_secret": "cloudinary key",
    "db_connection_string": "db connection string",
    "private_key": "private key",
    "gcp_service_account": "gcp service account",
    "generic_secret": "generic secret",
}


def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson confidence interval for a proportion k/n."""
    if n <= 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, center - margin), min(1.0, center + margin))


def security_score(findings: list[dict]) -> int:
    """100 minus per-finding severity points, floored at 0 (one repo)."""
    penalty = sum(SEVERITY_POINTS.get(f.get("severity", ""), 0) for f in findings)
    return max(0, 100 - penalty)


def grade_from_score(score: int) -> str:
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "F"


def credential_class(check_id: str) -> str | None:
    return CREDENTIAL_CLASS.get(check_id)


def overturn_by_class(verdicts: list[dict]) -> dict[str, tuple[int, int]]:
    """Roll verdict drop counts up per credential class: {class: (dropped, total)}.

    Same (dropped, total) convention as the per-check overturn table.
    Verdicts reference check ids; the credential-class table reports classes,
    so the two must be joined through the same mapping the class counts use.
    Verdicts whose check has no class (existence checks, env findings — never
    sampled) are skipped.
    """
    out: dict[str, tuple[int, int]] = {}
    for v in verdicts:
        cls = credential_class(v.get("check_id", ""))
        if cls is None:
            continue
        dropped, total = out.get(cls, (0, 0))
        out[cls] = (dropped + (1 if v.get("verdict") == "drop" else 0), total + 1)
    return out


# env_probe classifier labels → credential class, so env-file secrets
# (env_committed_secret) count in the same class table as bundle findings.
_ENV_LABEL_CLASS = [
    ("database connection string", "db connection string"),
    ("supabase service_role key", "supabase jwt"),
    ("stripe", "stripe key"),
    ("openai api key", "openai key"),
    ("anthropic api key", "anthropic key"),
    ("aws access key", "aws key"),
    ("github token", "github token"),
    ("google api key", "google api key"),
    ("private key", "private key"),
    ("url with embedded credentials", "url credentials"),
    ("jwt with unknown role", "hardcoded jwt"),
    ("secret-shaped value", "generic secret"),
]


def env_label_class(label: str) -> str | None:
    """Map an env_probe classifier label (e.g. "Database connection string
    with credentials") to a credential class name."""
    label_l = (label or "").lower()
    for needle, cls in _ENV_LABEL_CLASS:
        if needle in label_l:
            return cls
    return None
