# fpna-jobs

A daily board of senior **corporate FP&A / Strategic Finance / Business
Finance** roles in the NYC area or remote-for-NY, for a candidate moving out of
agency client finance. Runs daily at 12:30 UTC via GitHub Actions and publishes
a static dashboard to GitHub Pages
(https://shiggins03.github.io/fpna-jobs/).

Repo owner: shiggins03. **The board is built for someone else, who reads it via
the Pages link.** That shapes two things: the dashboard is the product (there is
no MCP artifact), and the repo is public, so nothing identifying about the
candidate is committed — the profile exists here only as term lists and scoring
weights, never as a first-person narrative or an employer name.

## Relationship to unifier-jobs — READ THIS FIRST

This repo was adapted from `unifier-jobs`, a **separate, actively maintained
project owned by the same person for their own job search**. The two are
independent by explicit instruction:

- **Never write to `unifier-jobs`.** No edits, no commits, no branches, no
  pushes. Read it for reference if genuinely useful, nothing more.
- The `scraper/` fetch layer arrived here as a **copy, not a dependency**. Bug
  fixes do not propagate in either direction; that is the accepted cost of
  isolation. If a fix here would also help there, say so — do not go do it.
- The rosters overlap (Amazon, Meta, NVIDIA, Oracle, Accenture). If a shared
  endpoint breaks — Meta's `doc_id` rotating, say — both boards break
  independently and each needs its own fix here.
- The daily cron is staggered (12:30 vs 11:00 UTC) so the two runs don't hit
  shared hosts at the same minute.
- Free-tier API keys must not be reused across the two repos: one key in two
  places splits one quota.

## Hard rules — never break these

1. **Never guess a displayed fact.** Company, title, location, posted date,
   compensation text and description render verbatim from the source or
   "Not listed". No estimates, no paraphrasing, no inferred dates, and
   specifically **no estimated total compensation** — bonus and equity are
   reported only as "mentioned" when the posting mentions them.
   The scores are the deliberate exception and they are fenced: fit score,
   FP&A transition score, seniority band, gap flags and recommendation are
   DERIVED from `config/roles.yaml` term lists, marked as derived on every card
   and in the footer, and never presented as employer statements.
2. **Free tier only.** Never add a paid API or service, even as an optional
   fallback, without the owner's explicit consent in that conversation.
3. **No LinkedIn/Indeed in the automated loop** — anti-bot walls and
   account-ban risk. Their content arrives indirectly via aggregator APIs.
4. **Direct employer listings are the product.** Aggregator APIs
   (JSearch/Adzuna/Jooble) are discovery only: resolve a hit to the employer's
   own ATS posting, add that employer to the roster, discard the board copy.
   Staffing-firm spam goes to quarantine, not the dashboard.
5. **Never drop a job silently.** Everything that fails a soft test gets a
   collapsed section (below comp target, lower fit, no longer listed) or a
   counted skip reason in the run log. A filter you can't see is a filter you
   can't judge.
6. **Nothing personal in the repo.** Public repo, permanent history. No name,
   no current employer, no resume text, no application tracking (that lives in
   the viewer's `localStorage`).

## Layout

- `scraper/` — deterministic fetch/qualify/dedup/score/publish (Python; stdlib
  + requests + bs4 + yaml only)
- `config/keywords.yaml` — the three gates: function terms, seniority levels,
  exclusions, comp bands, and the ATS search queries
- `config/roles.yaml` — derived-scoring surface: FP&A capability areas, the
  candidate's transferable experience, gap definitions, fit weights, bands
- `config/companies.yaml` — monitor roster; per-employer quirks inline
- `config/cities.yaml` — NYC-or-remote scope + sort order
- `config/seed_jobs.yaml` — hand-copied postings for employers that block bots
- `data/jobs.jsonl` — job store; `health.json` — per-source counts;
  `needs_triage.json` — queue (entries are never deleted; set status
  handled/ignored); `feed.json` — small machine-readable index, currently
  unconsumed (the seam for adding an artifact later)
- `docs/index.html` — generated dashboard (**never hand-edit**; edit
  `scraper/site_gen.py`)

## Qualification, and why it's shaped this way

Unlike a rare-token search, finance titles are high-volume and most matches are
noise, so `filters.qualifies()` is a three-gate AND: function signals ≥ 2,
seniority ≥ manager, location in NYC/metro/remote, and no excluded title term.

- **Comp is not a gate.** The owner's spec: an otherwise strong role with no
  posted salary must appear labelled Unknown, not be excluded. Unknown comp
  therefore scores *neutral* (half the component), never zero.
- **"Manager" is never rejected on title.** At Tier A employers
  Manager/Senior Manager are senior levels that pay in range, so `fit_score`
  *lifts* them (+0.20 on the seniority component) instead of ranking by title
  wording. Conversely SVP/CFO levels are damped: the goal is broadened FP&A
  scope, not the most senior title.
- **Titles with no level word are treated as `manager`, not junior.** At big
  tech the leveling often lives in the body; dropping them would silently lose
  real postings. Only explicit analyst/associate/coordinator titles fall below
  the floor.
- **Location "unknown" stays in scope.** Workday and Google publish
  "4 Locations" for reqs that often include New York. Those render with a
  "not specific" marker and score neutral on location.
- **Exclusions are title-only.** A good FP&A posting often mentions accounting
  or revenue recognition in passing; excluding on body text would gut the
  board. Body-level agency signals (`exclude.body_demote`) instead cost half a
  point of transition score each — which is exactly what that score is for.
- **Gaps need `gap_min_hits` to fire.** SQL named once in a "nice to have"
  list is not a SQL-first analytics role, so RED gaps require two hits.

Derived fields are recomputed for the **whole store** every run, not just
today's fetch — otherwise tuning `roles.yaml` never reaches jobs already
stored, and a source that fails for a day leaves its jobs unscored.

Scope is also re-applied to the whole store each run, so tightening the
location filter retroactively purges stored postings instead of letting them
linger two runs and then be mislabelled "no longer listed".

`python -m scraper.test_filters` asserts both directions (too-loose *and*
too-tight). **Add a case for every term list you change** — a broad term can
silently migrate whole employers between buckets.

## Runtime cost — keep an eye on the query count

`keywords.yaml: queries` is run once per employer, and the Workday adapter
fetches a detail page per posting. Five queries × 20 results × N Workday
tenants adds up fast inside the 30-minute job timeout. Greenhouse is exempt by
design: `queries_for()` sends it a single empty query because its adapter
downloads the whole board and filters client-side, so one request covers
everything. Prefer narrowing `queries` over adding more.

## Diagnosing endpoints (the probe workflow)

Claude-session sandboxes usually can't reach career sites (proxy policy), but
GitHub Actions can. `scraper/probe.py` + `.github/workflows/probe.yml`
(workflow_dispatch only): write probes into `main()`, push, dispatch, read the
Actions log, iterate. **Batch them** — one dispatch covering ten candidates,
not ten dispatches. `run_adapter()` exercises a real adapter end-to-end before
you trust it in the daily run. Keep `main()` empty between investigations and
record findings in `companies.yaml` notes.

Inherited lessons worth not relearning:
- Always run an **echo/negative control** before trusting a keyword search:
  query a nonsense string and confirm the result differs. A search page that
  echoes the query, or falls back to all jobs on no match, looks like a hit.
- **Brochure vs ATS**: a company careers page is often marketing copy while the
  real portal is a Workday/Greenhouse tenant. Grep the page for
  `myworkdayjobs|greenhouse|lever|icims|smartrecruiters|ashby` links first.
- Workday `searchText` is fuzzy — expect unrelated postings; the gates drop
  them. That is noise, not breakage.
- `generic_page` checks RAW html, not extracted text (JS-app job data lives in
  embedded script JSON). On this board `generic_page` is nearly useless anyway:
  every careers page contains the word "finance".

## Current state (update this section when you change it) — as of 2026-08-10

- **Initial build.** Adapted from unifier-jobs: `sources.py`, `models.py`,
  `probe.py` copied essentially verbatim; `filters.py` and `site_gen.py`
  rewritten for FP&A qualification and scoring; `main.py` reworked for
  multi-query fetching and whole-store scoring. Config is all new.
- Three `sources.py` edits vs the original: UA string, `fetch_amazon_jobs` no
  longer hardcodes a second "Primavera" query, and `fetch_google_careers`
  templates `{query}` into its configured URL (it previously took a fixed
  single-keyword URL).
- **Live on day one (endpoints reused from unifier-jobs, verified there):**
  Amazon, Meta, NVIDIA, Accenture, Oracle. Everything else ships **disabled**
  with a note, and shows greyed on the dashboard.
- **Probe round 1 is written and waiting in `probe.py:main()`**: Workday tenant
  guesses (Adobe, Salesforce, Intuit, PayPal), Greenhouse board tokens
  (Airbnb, Pinterest, Stripe, Datadog, DoorDash, Block, Spotify),
  SmartRecruiters tokens (Publicis, Havas, dentsu), the Google careers API
  shape, and an end-to-end FP&A-query run of the five enabled adapters.
  Dispatch it, then enable what verifies.
- **Deferred on purpose** (need bespoke adapters, not config guesses): Apple,
  Microsoft, Netflix (Eightfold — would pay for itself), Uber, Spotify,
  LinkedIn, Block. Ad holdcos WPP/Omnicom/Dentsu/Havas hire through operating
  companies, so each is 5+ endpoints with low expected yield — expand only if
  the board is thin.
- Aggregator discovery is **dormant**: no API keys in repo secrets. Note from
  unifier-jobs: JSearch's free RapidAPI plan does not include `/search` (404 by
  plan gating, verified 2026-07-30) — Adzuna is the better first key.
- Not built, by decision: MCP artifact, filter chips, LLM-written narrative.
  Card analysis text is assembled from template sentences in
  `filters.narrative()` so the same posting reads the same way every run and
  every clause traces to a term the posting actually uses.
