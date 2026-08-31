# Septr Research — the evidence

**2,076 AI-generated apps scanned. 649 findings verified by hand.
One rules engine. No secrets published, no keys tested.**

Plus a **live deployment study: 1,248 publicly deployed apps probed
(1,267 scan runs), 11 critical API keys found in client-side JavaScript
bundles.**

Four populations, one engine, one adjudication standard:

| Population | N | Committed .env | Fully clean | Mean score | F grade |
|---|---|---|---|---|---|
| Lovable | 881 | 27.5% | 50.9% | 90.5 | 7.3% |
| v0 | 513 | 7.0% | 64.7% | 93.4 | 4.7% |
| AI-coded (self-described) | 591 | 1.5% | 92.9% | 99.2 | 0.7% |
| AI-coded, app-shaped | 91 | 7.7% | 71.4% | 96.8 | 2.2% |

**The finding:** the exposure is a property of generator workflows, not
of AI coding. Lovable builds env-wired apps and 27.5% commit their
`.env`; v0 builds code-heavy frontends and 15.4% ship data-access
credentials in config and bundles; self-described AI-coded apps leak at
1.5–7.7% even when filtered to app shape. AI coding isn't the problem —
the generators are.

## The live deployment study

We didn't stop at source code. We probed **1,248 live deployments**
(Vercel, Netlify, Cloudflare Pages) and found **11 critical API keys**
shipped in client-side JavaScript bundles — **7 live OpenAI keys and 4
Supabase `service_role` keys** (master keys that bypass Row Level
Security), plus **36 exposed configuration files** and **19 vulnerable
dependencies**, in production, served to every visitor.

A `service_role` key in a GitHub repo is a code-quality issue. The same
key compiled into a live `main.js` bundle is a database credential leak
served to the internet. **That's the difference between the two
studies:** the corpus study proves the scanner is precise; the live
study proves the mistakes are deployed.

- **[`studies/LIVE_SCAN_STUDY.md`](studies/LIVE_SCAN_STUDY.md)** — the
  full write-up with methodology, ethics, and limitations
- **[`data/live-scan/`](data/live-scan/)** — anonymized scan rows,
  aggregates, and the critical-findings digest

## What's here

- **[`report/`](report/index.html)** — the five visual reports (also on
  GitHub Pages): the .env problem, code leaks, the generators, the
  vibe-coding landscape, and the four-populations case study
- **[`studies/`](studies/)** — the full technical write-ups with
  methodology, verification tables, and known limitations
- **[`data/`](data/)** — machine-readable results: aggregates,
  blast-radius tiers, the market census, **anonymized scan rows +
  verdicts** (every finding, every verdict, the ones against us
  included), and the **live deployment scan**
- **[`pipeline/`](pipeline/)** — the corpus pipeline; the analysis chain
  reproduces every number in the studies from `data/`

## The benchmark story

- **0/269** false positives on role-verified Supabase JWTs (verified
  from the JWT payload itself)
- Drop rates published raw per rule: Lovable **12.5%**, v0 **22.6%**,
  AI-coded **82%** — the largest classes of "findings" in the wild are
  placeholders and docs examples, and we say so per rule
- Compared against gitleaks/betterleaks on the same archives: they
  covered 92% of our verified findings — and their extras were ~85%
  false positives (product SKU codes, Go module cache hashes,
  courseware keys)

Rules engine described in methodology; precision numbers are in the
published verdicts.

## Reproduce it

```bash
# analysis chain (no engine needed)
cd pipeline
python3 aggregate_corpus.py --dir ../data/corpus --platform "Lovable"
python3 blast_radius.py --dir ../data/corpus
# see pipeline/README.md for the full list
```

## The flywheel

Read the studies → scan your own repo → want live monitoring?

**Septr — runtime security middleware for AI-built apps: secrets
scrubbing, RLS enforcement, BOLA/missing-auth/tamper/SSRF detection,
prompt-injection shielding, rate limiting — with a SOC2 evidence report
generated from your app's own verified traffic.**

Live monitoring: coming soon. [Get notified →](https://github.com)

## Methodology in one paragraph

Deterministic GitHub search frames (complete enumerable surfaces where
they exist), offline archive scans with one rules engine, and **every
finding adjudicated by hand with surrounding code** under the rule that
only high-confidence drops count. The live deployment study extends the
same engine to 1,248 public URLs (Vercel/Netlify/Cloudflare Pages/Lovable/Replit).
Ethics: aggregates and anonymized rows only; no repo-to-credential
mapping; no confirmed-live credential testing — establishing that a key
works means using someone's credential against their account, which is
not a thing this study will do. Published live-scan rows strip raw
context, truncate URLs to hostnames, and scrub every string field for
credential-shaped values.

Every proportion carries a 95% Wilson confidence interval in the
aggregates files.

## License

MIT — the data, the studies, and the pipeline are free to reuse with a
link back to this page. The rules engine described in the methodology is
Septr's product; the verdicts are the evidence.
