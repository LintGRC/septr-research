# Corpus Study — AI coding isn't the problem, the generators are

The general baseline (N = 591, + an app-shaped slice of N = 91):
repositories describing themselves as AI-coded leak at 1.5% (7.7%
app-shaped) versus Lovable's 27.5% — the exposure tracks generator
workflows, not AI coding itself.

**Status: full run — N = 591 repos** (a fixed-seed sample of the 1,000-repo
frame: the `ai-generated` GitHub topic, 898 repos — the complete
enumerable surface — merged with READMEs containing "vibe-coded", top
best-match). 591 downloaded and scanned; 9 exceeded the 150 MB archive
cap.

The general baseline for the corpus program: repositories that *describe
themselves* as AI-coded, without a generator-specific signal. This is the
population ogbuilds used for their 549-repo cross-corpus comparison, and
it answers the question behind the whole program: **is the exposure we
measured in Lovable and v0 a property of AI-built apps, or of specific
generators?**

**Signal honesty:** 27.1% of scanned repos carry a README text marker
("vibe-coded", "ai-generated", "built with ai"…); the rest are
topic-identified (`ai-generated` topic), which the tarball cannot
confirm. The frame is defined as "topic OR README self-description",
which is exactly what "describes itself as AI-coded" means.

## Method

- **Signal:** self-description — `topic:ai-generated` (repo search, 898 =
  complete surface) + `"vibe-coded" filename:README.md` (code search).
  Fixed-seed sample of 600 (seed `20260812`).
- **Scan:** the same Septr rules engine as the Lovable and v0 studies,
  offline, over each repo's GitHub tarball.
- **Verification:** **all 45 findings** across all 15 repos with
  non-existence findings were adjudicated with surrounding code —
  exhaustive, no subsample. **37 dropped (82%), 8 kept.** Only
  high-confidence drops count.
- **Ethics:** aggregates and anonymized rows only; no repo-to-credential
  mapping; no confirmed-live testing.

## Headline numbers (N = 591)

| Figure | AI-coded (Septr) | v0 (Septr) | Lovable (Septr) | ogbuilds 549-repo |
|---|---|---|---|---|
| Committed `.env` | **1.5%** (CI 0.8–2.9) | 7.0% | 27.5% | 20.4% exposed-secret (unverified) |
| No root `.gitignore` | **38.7%** (CI 34.9–42.7) | 38.2% | 10.4% | — |
| Fully clean | **92.9%** (CI 90.5–94.7) | 64.7% | 50.9% | — |
| Median score | 100 | 100 | 100 | — |
| **Mean score** | **99.2** (q1 100 / q3 100) | 93.4 | 90.5 | — |
| A grade | **98.1%** | 82.3% | 84.0% | — |
| F grade | **0.7%** (4) | 4.7% | 7.3% | — |

**The exposure is generator-specific, not AI-specific.** The
self-described AI-coded population is the cleanest of the three: 1.5%
commit `.env` (Lovable: 27.5%), 92.9% come back with nothing, and the
mean score is 99.2. Lovable's high env rate is a Lovable property (its
generator wires Vite + Supabase + `.env` by default); v0's hardcoded-key
pattern is a v0 property. AI-generated code per se is not the problem —
the specific generators' workflows are.

ogbuilds' 549-repo corpus reported 20.4% with an exposed-secret finding —
rule output before verification. Our verified read of the same population
is ~1% (8 kept findings, 6 repos). Their 20.4% was raw pattern output; our
82% drop rate on that output shows how much of it was placeholders, docs
examples, and test fixtures.

## The app-shaped correction (N = 91)

The self-described frame is dominated by repos that are not apps at all:
**61% have no dependency manifest**, and the median repo is 17 files /
119 KB — versus 119 files / 1.6 MB (Lovable) and 79 files / 1.4 MB
(v0). A 17-file repo has nothing to leak. To compare like with like, the
frame is filtered to **app-shaped repos**: a dependency manifest
(package.json or requirements.txt), a recognizable framework
(react/next/vue/vite/flask/fastapi/…), and ≥ 30 files.

| Figure | AI-coded, app-shaped (N=91) | AI-coded, all (N=591) | v0 (N=513) | Lovable (N=881) |
|---|---|---|---|---|
| Median repo | 107 files / 3.0 MB | 17 files / 119 KB | 79 files / 1.4 MB | 119 files / 1.6 MB |
| Committed `.env` | **7.7%** (CI 3.8–15.0) | 1.5% | 7.0% | 27.5% |
| No root `.gitignore` | **8.8%** (CI 4.5–16.4) | 38.7% | 38.2% | 10.4% |
| Fully clean | 71.4% (CI 61.4–79.7) | 92.9% | 64.7% | 50.9% |
| Mean score | 96.8 (q1 98 / q3 100) | 99.2 | 93.4 | 90.5 |
| A grade | 92.3% | 98.1% | 82.3% | 84.0% |
| F grade | 2.2% (2) | 0.7% | 4.7% | 7.3% |
| Data-access tier (rule output) | 4.4% | 1.2% | 15.4% | 10.0% |

The app-shaped population sits **between** the unfiltered frame and the
generators — which is the honest comparison. App-shaped AI-coded repos:
- commit `.env` at **7.7%** — between v0 (7.0%) and Lovable (27.5%), not
  the 1.5% of the unfiltered frame;
- have the **best hygiene of all four populations** (8.8% missing
  .gitignore — Lovable 10.4%, v0 38.2%);
- still verify almost clean: every credential class except
  role-verified anon keys (2.2%, bounded) drops to ~0% — 21/21 generic
  secrets dropped.

**Reading:** even the app-shaped slice of the self-described population
leaks far less than Lovable (7.7% vs 27.5% env) and shows no
generator-specific mechanics — the exposure really is a property of the
generators' default workflows, not of AI coding. The unfiltered frame's
"92.9% clean" was partly an artifact of including non-apps; the
app-shaped slice keeps the direction but grounds it (71.4% clean, still
the cleanest real-app population).

The app-shaped slice is what "AI-built apps without a generator signal"
actually looks like — the fair baseline for the corpus program.

![Four-population comparison — same engine, one adjudication standard](../report/charts/09-comparison.png)

## Blast radius: what the findings would actually do

| Tier | Repos | % (CI) | Lovable | v0 |
|---|---|---|---|---|
| **A — data access** | 7 | 1.2% (CI 0.6–2.4) | 10.0% | 15.4% |
| **B — cost** | 1 | 0.2% | 2.5% | 1.4% |
| **C — bounded** | 2 | 0.3% | 21.1% | 2.1% |
| **D — none** | 581 | 98.3% (CI 96.9–99.1) | 66.4% | 81.1% |

98.3% of self-described AI-coded repos carry nothing beyond hygiene at
worst — versus 66.4% (Lovable) and 81.1% (v0). The tier-A count (7) is
rule output; after verification (37/45 dropped) the real data-access
subset is a handful of repos — including one genuine Pexels API key
(56-char, format-exact, in all four example files) and two live Supabase
anon keys in client code (bounded by RLS).

## Verification (45/45 findings, exhaustive)

| Rule | Dropped | Total | Notes |
|---|---|---|---|
| `generic_secret` | 22 | 26 | Docs placeholders, test-fixture JWT secrets, a key-*name* FP (`STACKER_BOT_PASSWORD` with runtime-generated value) |
| `aws_access_key` | 8 | 8 | All AKIA…EXAMPLE docs/test shapes |
| `github_token` | 3 | 3 | `ghp_xxx` test fixtures |
| `private_key` / `resend` / `db` / `anthropic` | 1 each | 1 each | Placeholder forms |
| `supabase_anon` | 0 | 4 | Role-verified public-by-design — kept |

**Overall: 37/45 dropped (82%)** — the highest drop rate of the three
studies (Lovable 12.5%, v0 22.6%). This population's findings are
dominated by docs examples and test fixtures: the repo says "AI-coded"
and ships tutorial-adjacent code with placeholder credentials.

## Where secrets live

| Location | A — data | total |
|---|---|---|
| docs | 4 | 25 |
| committed `.env` | 9 | 17 |
| tests | 7 | 15 |
| frontend | 0 | 7 |
| config | 1 | 5 |

No tier-A findings in the frontend bundle at all. The small residual
surface sits in docs and tests — the least-deployed places.

## Raw data (this directory)

- `frame.json` — the 1,000-repo frame (queries, timestamps)
- `archives/` — 591 downloaded tarballs (gitignored)
- `scan-results.jsonl` — per-repo rows (existence flags + findings, redacted previews)
- `verify-task.jsonl` — the 45 adjudication tasks
- `verdicts.jsonl` — verdicts, confidence, reasons
- `aggregates.json`, `blast-radius.json`, `secret-locations.json` — machine-readable results
- `scan-results.anonymized.jsonl`, `verdicts.anonymized.jsonl` — published rows

## How to reproduce

```bash
GITHUB_TOKEN=... python backend/scripts/corpus/build_frame.py --platform aicoded \
    --out ../data/corpus-aicoded/frame.json
python backend/scripts/corpus/download_corpus.py --frame ../data/corpus-aicoded/frame.json \
    --out ../data/corpus-aicoded --count 600 --seed 20260812 --workers 8
python backend/scripts/corpus/scan_corpus.py --dir ../data/corpus-aicoded --platform aicoded --workers 4
python backend/scripts/corpus/verify_corpus.py --dir ../data/corpus-aicoded --repos 100 --seed 20260812
python backend/scripts/corpus/aggregate_corpus.py --dir ../data/corpus-aicoded --platform "AI-coded"
python backend/scripts/corpus/blast_radius.py --dir ../data/corpus-aicoded
python backend/scripts/corpus/secret_locations.py --dir ../data/corpus-aicoded
python backend/scripts/corpus/anonymize_corpus.py --dir ../data/corpus-aicoded

# App-shaped slice (manifest + framework + >=30 files)
python backend/scripts/corpus/scan_corpus.py --dir ../data/corpus-aicoded \
    --platform aicoded --out ../data/corpus-aicoded/scan-results-app.jsonl
# filter rows by app_shape, keep verdicts of surviving repos → corpus-aicoded-app/
python backend/scripts/corpus/aggregate_corpus.py --dir ../data/corpus-aicoded-app --platform "AI-coded apps"
python backend/scripts/corpus/blast_radius.py --dir ../data/corpus-aicoded-app
python backend/scripts/corpus/anonymize_corpus.py --dir ../data/corpus-aicoded-app
```

## Known limitations

- The frame is a self-selected population (repos that identify as
  AI-coded) — not a uniform sample of all AI-built code. Tutorials,
  prompt collections, and non-app repos inflate the clean share; deployed
  apps are under-represented relative to the generator frames.
- README text confirmation covers only 27.1% of repos; the rest are
  topic-identified.
- Verification is single-model, high-confidence-drops-only, consistent
  with the other two studies.
