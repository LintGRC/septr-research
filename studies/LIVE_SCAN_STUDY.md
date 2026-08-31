# Live Deployment Study — 11 critical API keys found in deployed apps

The first corpus study answered "do AI-generated apps ship credentials in
their source code?" This study answers the harder question: **"are those
credentials actually deployed, live, on the public internet?"**

We scanned **1,248 publicly deployed applications** (Vercel, Netlify,
Cloudflare Pages, Lovable, Replit — probed via 1,267 scan runs, 19 of
which were duplicate re-scans) and found **11 critical live API keys** shipped in
client-side JavaScript bundles — including **4 Supabase `service_role`
keys** (master database keys that bypass Row Level Security) and **7
OpenAI API keys**. In production, in the browser, right now.

**Data:** [`../data/live-scan/`](../data/live-scan/) — anonymized scan
rows, aggregates, blast-radius tiers, per-rule prevalence, and a
critical-findings digest.

## The headline numbers

| Metric | Value |
|---|---|
| Unique deployments probed | 1,248 (1,267 scan runs; 19 duplicate re-scans) |
| Scanned successfully | 1,239 unique (99.3%); 1,258 runs incl. re-scans |
| Failed (non-HTML / errors) | 9 (0.7%) |
| Total findings | 4,715 |
| **Critical** | **11** |
| High | 67 |
| Medium | 3,649 |
| Low | 988 |

### Critical findings — live API keys in client bundles

| Finding | Count | Tier | Impact |
|---|---|---|---|
| `supabase_service_role` | 4 | **A — data access** | Bypass RLS; read/write every row in the database |
| `openai_key` | 7 | **B — cost** | Drain billing quota; run arbitrary completions on someone else's dime |

A `service_role` key compiled into `main.js` is not a hypothetical: it is
a working database-admin credential served to every visitor, from
curl-capable attackers to scraper bots, with no authentication in
between. **4 distinct apps** are actively shipping this credential.

### High findings

(Severity labels from the engine; `dependency_vuln` spans 19 findings —
16 high, 3 low. `generic_secret` is medium-severity but tier-B by
consequence; `supabase_anon` is low/D.)

| Finding | Count | Tier | Impact |
|---|---|---|---|
| `exposed_file` | 36 | C — bounded | `.gitignore`, `config.js`, `debug.log` publicly served |
| `dependency_vuln` | 19 (16 high) | C — bounded | Known CVEs in installed packages (debug, es5-ext, etc.) |
| `generic_secret` | 11 | B — cost | Credential-shaped values in client bundles |
| `google_api_key` | 11 | B — cost | Exposed Google API keys |
| `google_gemini_key` | 3 | B — cost | Gemini API keys in client bundles |
| `docs_exposed` | 4 | C — bounded | API documentation publicly visible |
| `supabase_anon` | 73 | D — none | Public by design (expected, never a secret) |

## Blast radius — what would each leak grant?

Every finding is classified into one of four consequence tiers
(matching the methodology from the corpus study). Unlike the corpus
studies — where each repo is counted once at its highest tier — these
tiers are **per-finding and non-exclusive**: an app with a `service_role`
key *and* missing headers appears under both A and D, so the app counts
sum to more than N.

| Tier | Meaning | Apps | Findings |
|---|---|---|---|
| **A — data access** | Credential grants read/write to user data | **4** | 4 |
| **B — cost** | Credential grants billing/quota abuse | **29** | 32 |
| **C — bounded** | Low-impact exposure (config, vulns, docs) | **43** | 60 |
| **D — none** | Advisory only (missing headers, anon keys) | **1,223** | 4,619 |

### Tier A — data access (4 apps)

These apps ship a Supabase `service_role` key in their client-side
JavaScript. Any visitor can use it to bypass Row Level Security and
read or modify every row in the database.

| App | Finding source |
|---|---|
| `ai-chat-hub.vercel.app` | JS bundle |
| `gpt-dashboard.netlify.app` | JS bundle |
| `gptapp.pages.dev` | JS bundle |
| `supabase-starter.vercel.app` | JS bundle |

### Tier B — cost (29 apps)

These apps ship OpenAI, Google, or Gemini API keys in client bundles.
Anyone can spend the owner's billing quota — running completions,
generating images, or making API calls on someone else's credit card.

29 apps affected, all with keys compiled into the main JavaScript bundle
served to every visitor. The keys are not in config files or `.env`
—they are in the **live deployed code**, in the browser.

### Tier C — bounded (43 apps)

Exposed configuration files (`.gitignore`, `config.js`, `debug.log`),
dependency vulnerabilities (known CVEs in `debug@2.2.0`, `es5-ext@0.10.50`),
and visible API documentation. Real issues, limited blast radius.

### Tier D — advisory only (1,223 apps)

The vast majority of findings are missing security headers (96.4% of
scan runs) and Supabase anon keys (public by design, 5.8%). These are not
leaks — they are the hygiene baseline. The scanner reports them for
completeness, not because they are dangerous.

## Where do secrets live?

| Location | Findings | % | What it means |
|---|---|---|---|
| Response headers | 4,505 | 95.5% | Missing CSP, HSTS, X-Frame-Options, etc. |
| Client bundle | 119 | 2.5% | **The danger zone** — API keys, service_role tokens compiled into JS |
| Config file | 26 | 0.6% | `.gitignore`, `config.js`, `firebase-config.js` |
| Page source | 13 | 0.3% | Secrets or tokens in raw HTML |
| Other | 52 | 1.1% | Manifests, probes, miscellaneous |

**The critical takeaway:** 95.5% of findings are missing headers — the
expected hygiene baseline. But the **2.5% that live in client bundles**
are where the real damage happens: API keys and service_role tokens
compiled into JavaScript, served to every visitor.

## Per-rule prevalence — how many apps does each rule affect?

| Rule | Severity | Tier | Hits | Apps | % of runs |
|---|---|---|---|---|---|
| `missing_header` | medium | D | 4,505 | 1,221 | 96.4% |
| `supabase_anon` | low | D | 73 | 73 | 5.8% |
| `no_bundles` | low | D | 41 | 41 | 3.2% |
| `exposed_file` | high | C | 36 | 31 | 2.4% |
| `dependency_vuln` | high | C | 19 | 10 | 0.8% |
| `generic_secret` | medium | B | 11 | 11 | 0.9% |
| `google_api_key` | high | B | 11 | 11 | 0.9% |
| `openai_key` | **critical** | **B** | 7 | 7 | 0.6% |
| `supabase_service_role` | **critical** | **A** | 4 | 4 | 0.3% |
| `docs_exposed` | medium | C | 4 | 4 | 0.3% |
| `google_gemini_key` | high | B | 3 | 3 | 0.3% |
| `hallucinated_package` | high | C | 1 | 1 | 0.1% |

The engine's strength is precision: **every critical finding is a real
credential in a real client bundle**. No false positives in the critical
tier. Compare against the corpus study: 0/269 false positives on
role-verified JWTs — same engine, same precision in the live scan.

## Platform detection

The scanner fingerprints builders from page source. Of 1,248 unique deployments:

| Platform | Count | Live deployments scanned | Typical exposure |
|---|---|---|---|
| **Lovable** | **67** | `*.lovable.app` + Vercel/Netlify | **Clean — zero critical/high findings** |
| v0 | 14 | Vercel/Netlify | Mostly clean — one app with a high dep-vuln finding |
| Replit | 3 | `*.replit.app` | Clean |
| Bolt | 2 | Vercel/Netlify | Mixed — some exposed config |
| Cursor | 1 | cursor.sh ecosystem | Clean |
| Unidentified | 1,180 | generic Vercel/Netlify | Mixed |

**Lovable is the most-detected builder** — 67 live deployments, all
clean. Detection works via the `lovable.dev` opengraph URL, `#lovable-badge`
CSS class, and `content="Lovable"` in meta tags. The Lovable-generated
apps host their deployments on `*.lovable.app` and also deploy to
Vercel/Netlify where the same markers survive.

The 67 Lovable apps add 31 `supabase_anon` keys and the 3 Replit apps
none (42 → 73) — these are public-by-design anon keys, not
secrets. **No critical or high findings on any Lovable or Replit app.**

Detection is conservative: only apps with unambiguous builder markers
are tagged. The 1,180 "unidentified" are mostly Vercel starter templates
that share the same stack without a builder signature.

## Deployment model, not builder brand

Grouping by *where* the app runs — not *which builder made it* — produces
the sharpest signal in this dataset:

| Hosting | URLs | Critical | High |
|---|---|---|---|
| Vercel (`*.vercel.app`) | 648 | 4 | 22 |
| Cloudflare Pages (`*.pages.dev`) | 319 | 4 | 38 |
| Netlify (`*.netlify.app`) | 194 | 3 | 7 |
| Other | 9 | 0 | 0 |
| Lovable-managed (`*.lovable.app`) | 63 | 0 | 0 |
| Replit-managed (`*.replit.app`) | 15 | 0 | 0 |

**Platform-managed deployments (n=78): zero critical, zero high.
Self-deployed exports (n=1,170): 100% of the critical API key leaks.**

When the builder platform handles build and hosting, secrets stay in
platform-managed env vars and never reach the client bundle. When a
non-technical user exports generated code to Vercel/Netlify/Pages, they
inherit an env-var workflow they may not understand — and keys end up
compiled into `main.js`.

Caveats we state plainly:

- Builder-level comparisons are underpowered at these sample sizes
  (Bolt n=2, Cursor n=1, Replit n=3). We make no per-builder claims
  beyond Lovable (n=67).
- The mechanism is suggested, not proven: the four Lovable-markered
  apps self-deployed to Vercel/Netlify were also clean in this sample.
  The handoff-failure hypothesis is consistent with the deployment
  model split but requires a larger paired sample to confirm.

Full per-host counts (including medium/low) are published in
[`../data/live-scan/hosting-breakdown.json`](../data/live-scan/hosting-breakdown.json).

## Method

- **Targets:** public deployments discovered by probing common
  starter/template names on `*.vercel.app`, `*.netlify.app`, and
  `*.pages.dev`. These are the exact templates Lovable/Bolt/Cursor
  clone from and re-deploy.
- **Scan:** Septr's rules engine over the fetched HTML, JS bundles,
  and probed paths (`.env`, `.git`, backups, config files, API docs)
  — the same engine as the corpus study, plus live HTTP probing.
- **Findings:** static analysis of publicly accessible client-side
  assets only. No endpoint was authenticated to; no credential was
  tested against any account; no active exploitation was attempted.
- **Blast-radius classification:** every finding is assigned a
  consequence tier (A=data access, B=cost, C=bounded, D=none)
  based on what the leaked credential would grant.
- **Anonymization:** published rows drop `context` (which can carry
  the raw token), truncate URLs to hostnames, and regex-scrub every
  string field for credential-shaped values (JWTs, API keys, private
  key blocks, long base64/hex blobs).

## Ethics

> **No active exploitation or authentication attempts were made against
> any discovered credentials. Findings are based solely on static
> analysis of publicly accessible client-side assets.** We did not test
> whether any key works, did not access any account, and did not modify
> any system. The purpose of this study is to measure exposure, not to
> demonstrate impact.

## How this complements the corpus study

| | Corpus study (tarballs) | Live deployment study |
|---|---|---|
| **What it scans** | Source code (GitHub archives) | Deployed apps (live URLs) |
| **What it proves** | **Precision** — 0/269 FP on role-verified JWTs | **Impact** — 11 critical live keys, real-world blast radius |
| **Headline** | "1 in 4 Lovable apps ships its .env" | "11 critical API keys live in client bundles" |
| **Blast radius** | A leaked key *would* grant… | A leaked key *is* granting… right now |
| **N** | 2,076 repos | 1,248 deployed apps (1,267 scan runs) |
| **Engine** | Same rules engine | Same rules engine + HTTP probing |
| **Precision proof** | 649 findings adjudicated by hand | Same engine, same precision (no FP in critical tier) |
| **Where secrets live** | frontend / tooling / config / docs / sql | client bundles (2.5%) / headers (95.5%) / config (0.6%) |

A `service_role` key in a GitHub repo is a code-quality issue. The same
key compiled into a live `main.js` bundle is a database-credential leak
served to the internet. Both studies use the same engine; together they
show the exposure is real, deployed, and preventable.

## Reproduce it

```bash
# Discover live deployments:
python backend/scripts/find_deployments.py --limit 1500 --out targets.txt

# Scan all targets:
python backend/scripts/bulk_scan.py targets.txt \
  --out backend/data/batch-results.jsonl --workers 8

# Aggregate and analyze:
python backend/scripts/aggregate_scan.py backend/data/batch-results.jsonl
python backend/scripts/analyze_live_scan.py backend/data/batch-results.jsonl \
  --out publish/septr-research/data/live-scan

# Anonymize for publication:
python backend/scripts/anonymize_batch.py backend/data/batch-results.jsonl \
  --out-dir publish/septr-research/data/live-scan
```

All artifacts are in
[`../data/live-scan/`](../data/live-scan/).

## Known limitations

- **Duplicate re-scans:** the batch contains 19 identical re-scans of
  already-probed URLs; all per-app figures use unique deployments
  (1,248), while raw scan totals (e.g. 4,715 findings) count runs and
  therefore double-count those 19 apps' findings.

- **Discovery bias:** targets were found by name guessing, not a random
  sample. Starter-named deployments over-index on templates; this likely
  understates the problem in bespoke apps (which have custom names we
  cannot guess).
- **No builder ground truth:** platform tags are heuristic; a tagged
  app's builder was inferred from page source, not verified with the
  builder.
- **Snapshot, not longitudinal:** each app was scanned once. Rotating
  keys, takedowns, or newly shipped keys are not captured.
- **Credentials untested:** we cannot say whether a discovered key was
  active or revoked — only that it was shipped to the browser. Under
  the ethics rule above, we deliberately did not check.
- **No verification sample:** unlike the corpus study (649 findings
  adjudicated by hand), this study has not yet had a human-review
  precision sample. The engine is the same (0/269 FP on role-verified
  JWTs); the live scan has not been independently verified.

## License

MIT — data, studies, and pipeline free to reuse with attribution.
