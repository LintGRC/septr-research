# Pipeline

The corpus pipeline: frame → download → scan → verify → aggregate →
analyze → publish. Two tiers:

## Reproducible from this repo's data (no engine needed)

These scripts run against the published `../data/` and reproduce every
number in the studies:

```bash
# from this directory (analysis reads the published anonymized rows)
python3 aggregate_corpus.py --dir ../data/corpus --platform "Lovable" \
    --results ../data/corpus/scan-results.anonymized.jsonl \
    --verdicts ../data/corpus/verdicts.anonymized.jsonl
python3 aggregate_corpus.py --dir ../data/corpus-v0 --platform "v0" \
    --results ../data/corpus-v0/scan-results.anonymized.jsonl \
    --verdicts ../data/corpus-v0/verdicts.anonymized.jsonl
python3 aggregate_corpus.py --dir ../data/corpus-aicoded --platform "AI-coded" \
    --results ../data/corpus-aicoded/scan-results.anonymized.jsonl \
    --verdicts ../data/corpus-aicoded/verdicts.anonymized.jsonl
python3 aggregate_corpus.py --dir ../data/corpus-aicoded-app --platform "AI-coded apps" \
    --results ../data/corpus-aicoded-app/scan-results.anonymized.jsonl \
    --verdicts ../data/corpus-aicoded-app/verdicts.anonymized.jsonl

python3 blast_radius.py --dir ../data/corpus \
    --results ../data/corpus/scan-results.anonymized.jsonl
python3 secret_locations.py --dir ../data/corpus \
    --results ../data/corpus/scan-results.anonymized.jsonl
python3 market_map.py --results ../data/corpus-aicoded/scan-results-app.jsonl \
    --out ../data/corpus-aicoded/market-map.json   # needs GITHUB_TOKEN (live census)

python3 generate_report.py --dir ../data/corpus --out /tmp/charts
python3 generate_report.py --compare "Lovable:../data/corpus,v0:../data/corpus-v0,AI-coded:../data/corpus-aicoded,AI-coded apps:../data/corpus-aicoded-app"
python3 anonymize_corpus.py --dir ../data/corpus
```

The analysis chain reproduces the published numbers exactly (verified:
881 repos, 27.5% committed .env, mean 90.5, tier A 88 — from the
anonymized rows alone). `blast_radius.py` / `secret_locations.py` accept
`--results` to read the anonymized scan rows; the raw scan layer
(repo ids + paths) is intentionally not published.

The trimmed `scanner/` package here contains the pure-function checks
(existence checks, duplicate families, corpus statistics) — the parts
needed for the analysis chain.

## Requires Septr's engine (described in methodology)

`scan_corpus.py` and `verify_corpus.py` import Septr's server-side rules
engine (`scanner.checks`, `scanner.env_probe`) — the full suppressor
corpus that powers the product. That engine is described rule-by-rule in
the study methodology (`studies/CORPUS_STUDY*.md` → "Engine fixes" and
"Scoring"), and the published scan results + verdicts in `../data/` are
its output, fully auditable without the engine source.

Why not ship it: the suppressor corpus is the product's defensible layer
— the accumulated false-positive knowledge that keeps precision at
0/269 role-verified findings. The studies are reproducible from the
verdicts; the engine stays server-side.

## The verification standard (why the numbers are trustworthy)

- Every finding in every published sample was adjudicated by hand with
  the surrounding code, under the rule: **only high-confidence drops
  count**. Verdicts are published raw (`verdicts.anonymized.jsonl`).
- Supabase keys are role-verified from the JWT payload itself —
  **0/269 false positives** across the Lovable sample.
- Drop rates are published per rule: Lovable 12.5% (45/361),
  v0 22.6% (55/243), AI-coded 82% (37/45).
