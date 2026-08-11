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

## Finding compensation: never assume a "$" (corrected 2026-08-11)

**Two real bugs, both found by the owner spotting a range on a posting whose
card said "not listed". Both were ours, not the employer's.**

1. **Amazon writes pay with no dollar sign**, one line per metro, at the end of
   `preferred_qualifications` — a field the adapter already fetches and stores:

       USA, NY, New York - 104,900.00 - 179,500.00 USD annually
       USA, TX, Irving - 95,400.00 - 163,200.00 USD annually

   Every comp pattern was `\$`-anchored, so all of them missed it — and so did
   three rounds of my own investigation, which searched the API and the page
   HTML for `\$[\d,]{4,}` and concluded from zero hits that Amazon "doesn't
   serve the numbers". The data was there the whole time. `PLAIN_USD_RANGE_RE`
   now matches per LINE, so the quote keeps the employer's metro label, and the
   New York line wins when several are listed.

2. **Stripe's Greenhouse payload has no pay section at all** — verified against
   `boards-api.greenhouse.io/v1/boards/stripe/jobs/7463755`. The range lives
   only on stripe.com's own listing, in server-rendered HTML ("The annual US
   base salary range for this role is $133,800 - $200,800"). So `main.run()`
   now calls `sources.fetch_posting_text(url)` for any job that qualified and
   still has no comp, and parses that. One request per unpriced role.

**The lesson worth keeping:** when a source appears to omit a field, test for
the field's *content*, not for one formatting convention. A negative result
from a single regex is not evidence of absence. Before concluding "the employer
doesn't publish X", grep the payload for the surrounding words the human reader
sees ("USD", "salary range", "annually"), not for the punctuation you expect.

`COMP_OFFSITE_RE` and the "range stated on the posting" label remain for the
genuine case where a posting says a range is published and neither the payload
nor the page carries it. That path should now be rare — if it shows up on a
whole employer at once, suspect a parsing gap first.

## Superseded: "Amazon's salary is unreadable" (wrong — see above)

The owner pointed at a live posting showing a base range at the bottom of the
page while the card said "Compensation not listed". It is not a parsing bug:

- `search.json` carries 32 fields per job and **none** contains a dollar figure
  (probe round 2 dumped every one of them).
- The rendered job page is 43,948 bytes with **zero** dollar figures, under both
  the adapter UA and a browser UA (probe round 3) — and an in-browser `fetch`
  of the same URL with the owner's own cookies, from their own network, returned
  the byte-identical document, still with none.
- `/api/v1/jobs/{id}`, `…/compensation`, `…/pay-range`, `/api/jobs/{id}` all
  404; `/en/jobs/{id}.json` 406s with an HTML error page.
- The page's own `POST /auth/token` returns 401 outside a real session, which is
  most likely what gates the pay component. The description text ends with the
  sentence "The base salary range for this position is listed below" — the words
  ship, the numbers are appended client-side.

Reading it would need a real browser session per posting, which a daily cron
can't do. So `COMP_OFFSITE_RE` detects that sentence and the card says
**"Range stated on the posting — open the link"** instead of "Compensation not
listed", which was actively misleading. No figure is ever invented; rule 1 is
intact. Don't add browser automation for this without the owner asking.

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
- **13 of 27 companies live.** Reused from unifier-jobs: Amazon, Meta, NVIDIA,
  Accenture, Oracle. Added by probe round 1: Adobe, Salesforce, PayPal
  (Workday), Airbnb, Pinterest, Stripe, Datadog, Block (Greenhouse).
- **Probe round 1 verdicts (2026-08-10)** — per-company detail is in
  `companies.yaml` notes; the transferable lessons:
  - Workday host and site name both matter: `salesforce` works on wd12 and
    422s on wd1; Adobe is `external_experienced`, not `AdobeCareers`.
  - Intuit's Workday answers **401** for every site name — authenticated
    tenant, not a wrong guess. Don't keep guessing site names at a 401.
  - Greenhouse board tokens: airbnb/pinterest/stripe/datadog/block live;
    doordash and spotify 404 (moved off the public board API). Block needed no
    custom adapter after all.
  - **SmartRecruiters gives a false green**: an unknown company token returns
    200 with `totalFound=0`, not a 404. All four guesses looked "fine" and were
    all wrong. Read the token off a live apply URL.
  - Both Google careers v3 search shapes 404. Needs an XHR capture from the
    live careers UI (the technique that cracked Meta in unifier-jobs).
  - Meta returns five fuzzy hits per query with **no descriptions** —
    "Planning Lead" for a financial-planning query. `main.run()` now guards the
    triage path with a title-only function/seniority/exclusion check, or Meta
    would refill the triage queue on every run.
  - Amazon's 100 relevance-ranked results were almost all Seattle/Bellevue, so
    `loc_queries` runs a New York-scoped pass alongside the unscoped one.
    Amazon descriptions come inline, so each pass costs one request.
- **Live board as of the 2026-08-10 evening run: 10 scored listings** (3 at fit
  75+) plus 5 unscoreable Meta titles, 0 health warnings. Amazon NYC finance
  managers, two Stripe Finance & Strategy partners, Airbnb Principal Strategic
  Finance, an Oracle Central FP&A manager, Accenture. Thin but clean — every
  row is a real senior finance role in scope.
- Skip counts printed at the end of each run are the fastest read on whether a
  gate is mistuned. Current shape: excluded title term ~945, outside US ~546,
  outside NYC/remote ~442, not a finance title ~227, below seniority ~39.
- **Three bugs the first live runs exposed** (all now have regression tests —
  this is the pattern to keep: ship, read the actual board, fix what the data
  shows):
  1. `unknown_patterns` were substring-searched, so "united states" matched
     inside "Nashville, TN, United States" and put Tennessee on a NYC board.
     They are `re.fullmatch`ed now.
  2. Body-only function matching admitted "Manager, Mid-Market Sales",
     "Director of Field Sales", "Marketing Operations Lead" and
     "Sr. Data Scientist" — sales and marketing descriptions are full of
     forecasting, KPIs, P&L and business partnering. Hence `require.title_terms`
     and the narrow non-finance title exclusions. **"Sales finance" is
     deliberately still allowed** — that is real business finance.
  3. Airbnb's "Pay Range\n$168,000\n—\n$206,000 USD" was missed because the
     dash class lacked the em-dash and the newlines broke the labelled pattern:
     a posting *with* a stated range displayed "Not listed". Whenever a card
     says "Not listed", check whether the parser missed it before believing it.
- Comp is genuinely absent for Amazon, Oracle and Stripe here: their pay blurb
  is not in the fields the adapters fetch (Amazon's `search.json` returns
  description + qualifications only). "Not listed" is honest, not a parser bug.
  Fixing it would mean a per-job detail fetch — not worth the request budget yet.
- **Next levers if the board is too thin**, cheapest first: (1) get Intuit,
  DoorDash, Spotify and the SmartRecruiters tokens right — pure config, one
  probe round; (2) widen `keywords.yaml: queries` (watch the request budget);
  (3) an Eightfold adapter, which unlocks Netflix and others at once;
  (4) an Adzuna key to switch discovery on; (5) ad-holdco operating companies,
  the most work for the least expected yield.
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
