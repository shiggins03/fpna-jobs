"""Reusable endpoint-diagnostics harness. The repo's local sandbox (Claude
sessions) usually can't reach career sites, but GitHub Actions can: write
probes into main(), push, dispatch the `probe` workflow (workflow_dispatch
only), read the Actions log, iterate. Keep main() empty between
investigations; findings belong in companies.yaml notes / CLAUDE.md.

History: rounds 1-4 on 2026-07-18 diagnosed the whole broken-roster backlog —
see the notes in companies.yaml and the probe-workflow section in CLAUDE.md."""
import re
import traceback

import requests
from bs4 import BeautifulSoup

from . import sources  # adapters can be exercised end-to-end, see run_adapter

BROWSER_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
              "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
              "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
              "*/*;q=0.8", "Accept-Language": "en-US,en;q=0.9"}
ADAPTER_UA = sources.UA
T = 25


def section(name):
    print(f"\n{'=' * 20} {name} {'=' * 20}", flush=True)


def show(label, fn):
    """Run one probe; print a one-line error instead of killing the run.
    (Full tracebacks drown the Actions log — round 5 lesson.)"""
    try:
        fn()
    except Exception as e:
        print(f"  {label}: EXC {type(e).__name__}: {str(e)[:160]}")


def get(url, ua=BROWSER_UA, **kw):
    r = requests.get(url, headers=ua, timeout=T, **kw)
    print(f"  GET {url} -> {r.status_code} final={r.url} "
          f"len={len(r.text)} ctype={r.headers.get('content-type')}")
    return r


def run_adapter(name, fn, co, query="financial planning"):
    """Call a direct adapter exactly as the pipeline would and dump results."""
    records, ok, inventory = fn(co, query)
    print(f"  {name}: ok={ok} inventory={inventory} records={len(records)}")
    for r in records[:8]:
        print(f"    - {r.get('title')!r} @ {r.get('location')!r} "
              f"desc-len={len(r.get('description') or '') or None} "
              f"search_matched={r.get('search_matched')}")
    return records


def cxs(host, tenant, site):
    """Quick Workday public-API check: 200+total = right pair, 422 = wrong."""
    try:
        r = requests.post(f"https://{host}/wday/cxs/{tenant}/{site}/jobs",
                          json={"appliedFacets": {}, "limit": 1, "offset": 0,
                                "searchText": ""}, headers=ADAPTER_UA, timeout=T)
        total = None
        if r.ok and "json" in (r.headers.get("content-type") or ""):
            total = r.json().get("total")
        print(f"  cxs {host} {tenant}/{site} -> {r.status_code} total={total}")
    except Exception as e:
        print(f"  cxs {host} {tenant}/{site} -> EXC {type(e).__name__}: {e}")


def sf_csb(base, label):
    """SuccessFactors Career Site Builder echo test: server-rendered search
    is usable as generic_page; identical HTML for real vs nonsense query
    means JS-rendered (blind)."""
    try:
        a = requests.get(f"{base}/search/?q=Unifier", headers=BROWSER_UA,
                         timeout=T)
        b = requests.get(f"{base}/search/?q=zzqnope999", headers=BROWSER_UA,
                         timeout=T)
        differs = len(a.text) != len(b.text)
        hits = len(re.findall(r'class="jobTitle|data-careersite-propertyid="title',
                              a.text))
        print(f"  {label}: {a.status_code} lenA={len(a.text)} lenB={len(b.text)} "
              f"differs={differs} title-markers={hits}")
    except Exception as e:
        print(f"  {label}: EXC {type(e).__name__}: {e}")


def greenhouse(board):
    """Board-token check: 200 + a job count means the token is right."""
    try:
        r = requests.get(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs",
                         headers=ADAPTER_UA, timeout=T)
        n = len(r.json().get("jobs", [])) if r.ok else None
        print(f"  greenhouse {board} -> {r.status_code} jobs={n}")
    except Exception as e:
        print(f"  greenhouse {board} -> EXC {type(e).__name__}: {e}")


def smartrecruiters(company):
    try:
        r = requests.get(
            f"https://api.smartrecruiters.com/v1/companies/{company}/postings",
            params={"limit": 1}, headers=ADAPTER_UA, timeout=T)
        total = r.json().get("totalFound") if r.ok else None
        print(f"  smartrecruiters {company} -> {r.status_code} total={total}")
    except Exception as e:
        print(f"  smartrecruiters {company} -> EXC {type(e).__name__}: {e}")


def amazon_pay(job_id):
    """Where does amazon.jobs keep the pay paragraph?

    The owner pointed at a live posting showing a salary at the bottom of the
    page while our card said "Not listed" — so search.json's description +
    qualifications fields do not carry it. Dump every field of both the search
    record and the detail endpoint, and flag which ones contain a dollar
    figure.
    """
    money = re.compile(r"\$[\d,]{4,}")
    for label, url in (("detail", f"https://www.amazon.jobs/en/jobs/{job_id}.json"),
                       ("search", "https://www.amazon.jobs/en/search.json")):
        try:
            params = ({"base_query": "Hub Delivery Finance", "result_limit": 5,
                       "country": "USA"} if label == "search" else None)
            r = requests.get(url, params=params, headers=ADAPTER_UA, timeout=T)
            print(f"  {label} {url} -> {r.status_code}")
            if not r.ok:
                continue
            data = r.json()
            rec = data
            if label == "search":
                jobs = data.get("jobs", [])
                rec = next((x for x in jobs if str(job_id) in str(x.get("id_icims", ""))
                            or str(job_id) in (x.get("job_path") or "")), jobs[0] if jobs else {})
            if "job" in rec and isinstance(rec["job"], dict):
                rec = rec["job"]
            for k, v in sorted(rec.items()):
                s = "" if v is None else str(v)
                hit = "  <-- $" if money.search(s) else ""
                print(f"    {label}.{k}: len={len(s)}{hit}")
                if hit:
                    m = money.search(s)
                    print(f"      ...{s[max(0, m.start()-140):m.start()+90]}...")
        except Exception as e:
            print(f"  {label}: EXC {type(e).__name__}: {str(e)[:160]}")


def amazon_pay_page(job_id):
    """Round 2 proved no search.json field holds a dollar figure. Try the
    detail endpoint with an explicit Accept (it 406'd on the default) and the
    rendered job page, and locate a stable container for the pay paragraph."""
    money = re.compile(r"\$[\d,]{4,}")
    try:
        r = requests.get(f"https://www.amazon.jobs/en/jobs/{job_id}.json",
                         headers={**ADAPTER_UA, "Accept": "application/json"},
                         timeout=T)
        print(f"  detail.json (Accept set) -> {r.status_code} len={len(r.text)} "
              f"money={bool(money.search(r.text))}")
        if r.ok:
            for k, v in sorted((r.json().get("job") or r.json()).items()):
                s = "" if v is None else str(v)
                if money.search(s):
                    m = money.search(s)
                    print(f"    FIELD {k}: ...{s[max(0, m.start()-160):m.start()+110]}...")
    except Exception as e:
        print(f"  detail.json: EXC {type(e).__name__}: {str(e)[:140]}")

    for ua_name, ua in (("adapter-UA", ADAPTER_UA), ("browser-UA", BROWSER_UA)):
        try:
            r = requests.get(f"https://www.amazon.jobs/en/jobs/{job_id}", headers=ua,
                             timeout=T)
            hits = money.findall(r.text)
            print(f"  page {ua_name} -> {r.status_code} len={len(r.text)} "
                  f"money-hits={len(hits)}")
            if r.ok and hits:
                soup = BeautifulSoup(r.text, "html.parser")
                text = soup.get_text("\n")
                m = money.search(text)
                if m:
                    print("    TEXT: ..."
                          + re.sub(r"\s+", " ",
                                   text[max(0, m.start() - 220):m.start() + 160])
                          + "...")
                for tag in soup.find_all(attrs={"class": True}):
                    t = tag.get_text(" ", strip=True)
                    if money.search(t) and len(t) < 900:
                        print(f"    CONTAINER class={tag.get('class')} len={len(t)}")
                        break
        except Exception as e:
            print(f"  page {ua_name}: EXC {type(e).__name__}: {str(e)[:140]}")


FIN_HINT = re.compile(r"(fp&a|financial plan|finance manager|strategic finance|"
                      r"finance director|business finance)", re.I)


def _report(label, r, want_json=True, probe_keys=()):
    """One line per candidate: status, size, whether it looks like job data."""
    body = r.text if r is not None else ""
    ok = r is not None and r.ok
    fin = len(FIN_HINT.findall(body))
    print(f"  {label} -> {r.status_code if r is not None else 'ERR'} "
          f"len={len(body)} finance-hits={fin}")
    if ok and want_json:
        try:
            j = r.json()
            top = list(j.keys())[:8] if isinstance(j, dict) else f"list[{len(j)}]"
            print(f"      json keys: {top}")
            for path in probe_keys:
                cur = j
                for part in path.split("."):
                    cur = (cur or {}).get(part) if isinstance(cur, dict) else None
                if isinstance(cur, list):
                    print(f"      {path}: list[{len(cur)}]"
                          + (f" first-keys={list(cur[0].keys())[:12]}"
                             if cur and isinstance(cur[0], dict) else ""))
                elif cur is not None:
                    print(f"      {path}: {str(cur)[:100]}")
        except Exception as e:
            print(f"      not json: {type(e).__name__} head={body[:120]!r}")
    elif ok:
        m = FIN_HINT.search(body)
        if m:
            print(f"      ...{body[max(0, m.start()-90):m.start()+110]!r}")


def try_get(label, url, ua=BROWSER_UA, probe_keys=(), want_json=True, **kw):
    try:
        r = requests.get(url, headers=ua, timeout=T, **kw)
        _report(label, r, want_json, probe_keys)
        return r
    except Exception as e:
        print(f"  {label} -> EXC {type(e).__name__}: {str(e)[:120]}")
        return None


def try_post(label, url, ua=BROWSER_UA, probe_keys=(), **kw):
    try:
        r = requests.post(url, headers=ua, timeout=T, **kw)
        _report(label, r, True, probe_keys)
        return r
    except Exception as e:
        print(f"  {label} -> EXC {type(e).__name__}: {str(e)[:120]}")
        return None


def ats_markers(label, url):
    """Which ATS does this careers page actually hand off to?

    The unifier-jobs lesson: a holdco careers page is marketing copy while the
    real portal is a Workday/Greenhouse tenant. Grep for the handoff links
    BEFORE guessing tenant names.
    """
    pats = {
        "workday": r"([a-z0-9-]+)\.(wd\d+)\.myworkdayjobs\.com/([A-Za-z0-9_-]+)",
        "greenhouse": r"(?:boards|job-boards)\.greenhouse\.io/([a-z0-9-]+)",
        "greenhouse-api": r"boards-api\.greenhouse\.io/v1/boards/([a-z0-9-]+)",
        "lever": r"jobs\.lever\.co/([a-z0-9-]+)",
        "smartrecruiters": r"(?:careers|jobs)\.smartrecruiters\.com/([A-Za-z0-9_-]+)",
        "smartrecruiters-api": r"api\.smartrecruiters\.com/v1/companies/([A-Za-z0-9_-]+)",
        "ashby": r"jobs\.ashbyhq\.com/([a-z0-9-]+)",
        "icims": r"([a-z0-9-]+)\.icims\.com",
        "eightfold": r"([a-z0-9.-]+)\.eightfold\.ai|explore\.jobs\.([a-z.]+)/api",
        "avature": r"([a-z0-9-]+)\.avature\.net",
        "phenom": r"([a-z0-9-]+)\.phenompeople\.com",
        "successfactors": r"([a-z0-9-]+)\.successfactors\.com",
        "oracle-orc": r"([a-z0-9-]+)\.oraclecloud\.com",
    }
    try:
        r = requests.get(url, headers=BROWSER_UA, timeout=T)
        print(f"  {label} {url} -> {r.status_code} len={len(r.text)}")
        for name, pat in pats.items():
            hits = {m.group(0) for m in re.finditer(pat, r.text, re.I)}
            if hits:
                print(f"      {name}: {sorted(hits)[:4]}")
    except Exception as e:
        print(f"  {label}: EXC {type(e).__name__}: {str(e)[:120]}")


def board_sweep(slugs):
    """Try each slug against Greenhouse, Lever and Ashby. Print only hits.

    Cheaper than reasoning about which vendor a company uses: three small
    requests settle it. Greenhouse is queried WITHOUT content=true here — the
    full board is ~1MB and we only need to know the token resolves.
    """
    for slug in slugs:
        hits = []
        try:
            r = requests.get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
                             headers=BROWSER_UA, timeout=T)
            if r.ok:
                n = len(r.json().get("jobs") or [])
                if n:
                    hits.append(f"greenhouse={n}")
        except Exception:
            pass
        try:
            r = requests.get(f"https://api.lever.co/v0/postings/{slug}",
                             params={"mode": "json"}, headers=BROWSER_UA, timeout=T)
            if r.ok and isinstance(r.json(), list) and r.json():
                hits.append(f"lever={len(r.json())}")
        except Exception:
            pass
        try:
            r = requests.get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}",
                             params={"includeCompensation": "true"},
                             headers=BROWSER_UA, timeout=T)
            if r.ok:
                jobs = r.json().get("jobs") or []
                if jobs:
                    comp = sum(1 for j in jobs
                               if (j.get("compensation") or {}).get("compensationTierSummary"))
                    hits.append(f"ashby={len(jobs)}(priced={comp})")
        except Exception:
            pass
        print(f"  {slug:<22} {' '.join(hits) if hits else '-'}", flush=True)


def wd_from_page(name, url):
    """Read the real Workday host/tenant/site off a careers page.

    Guessing site names cost seven wasted probes on dentsu; the page states it.
    """
    try:
        r = requests.get(url, headers=BROWSER_UA, timeout=T)
        found = set()
        for m in re.finditer(r"([a-z0-9-]+)\.(wd\d+)\.myworkdayjobs\.com"
                             r"(?:/[a-z]{2}-[A-Z]{2})?/([A-Za-z0-9_-]+)",
                             r.text, re.I):
            found.add((m.group(1), m.group(2), m.group(3)))
        other = set()
        for pat in (r"(?:boards|job-boards)\.greenhouse\.io/([a-z0-9-]+)",
                    r"jobs\.lever\.co/([a-z0-9-]+)",
                    r"jobs\.ashbyhq\.com/([a-z0-9-]+)",
                    r"api\.smartrecruiters\.com/v1/companies/([A-Za-z0-9_-]+)",
                    r"([a-z0-9-]+)\.eightfold\.ai",
                    r"([a-z0-9-]+)\.phenompeople\.com"):
            other |= {m.group(0) for m in re.finditer(pat, r.text, re.I)}
        line = f"  {name:<16} {r.status_code}"
        if found:
            line += "  WD: " + "; ".join(f"{t}.{w}/{s}" for t, w, s in sorted(found))
        if other:
            line += "  OTHER: " + ", ".join(sorted(other)[:3])
        print(line, flush=True)
    except Exception as e:
        print(f"  {name:<16} EXC {type(e).__name__}", flush=True)


def wd_matrix(slug, hosts=("wd1", "wd3", "wd5"), sites=None):
    """Brute-force a Workday host/tenant/site triple.

    Used only for employers whose careers page exposes no handoff link (round 9:
    Visa, BlackRock, Moody's, S&P, MSCI, IBM, Disney, Paramount, NBCU, Etsy all
    hid theirs). 200 with a total = right; 404/422/400 = wrong pair. Cheap: no
    detail fetches, one small POST each.
    """
    sites = sites or ("External", "Careers", "ExternalCareerSite",
                      f"{slug.capitalize()}Careers", "External_Career_Site")
    for wd in hosts:
        for site in sites:
            try:
                r = requests.post(
                    f"https://{slug}.{wd}.myworkdayjobs.com/wday/cxs/{slug}/{site}/jobs",
                    json={"appliedFacets": {}, "limit": 1, "offset": 0,
                          "searchText": ""}, headers=ADAPTER_UA, timeout=15)
                if r.ok and "json" in (r.headers.get("content-type") or ""):
                    print(f"  HIT {slug}.{wd}/{site} total={r.json().get('total')}",
                          flush=True)
            except Exception:
                pass


def marker_hunt(name, urls):
    """Grep several candidate careers URLs for ANY ATS we already support.

    Round 9 only fetched landing pages and mostly found nothing; the handoff
    link usually lives on the /search or /jobs subpage. Also looks for phenom,
    avature, successfactors, eightfold and icims — Mastercard and WBD both
    showed phenom markers, and we already have adapters for three of those, so
    a hit here is a config change rather than new code.
    """
    pats = {
        "workday": r"([a-z0-9-]+)\.(wd\d+)\.myworkdayjobs\.com(?:/[a-z]{2}-[A-Z]{2})?/([A-Za-z0-9_-]+)",
        "phenom": r"([a-z0-9-]+)\.phenompeople\.com",
        "avature": r"([a-z0-9-]+)\.avature\.net",
        "successfactors": r"([a-z0-9-]+)\.successfactors\.com",
        "eightfold": r"([a-z0-9-]+)\.eightfold\.ai",
        "icims": r"([a-z0-9-]+)\.icims\.com",
        "greenhouse": r"(?:boards|job-boards)\.greenhouse\.io/([a-z0-9-]+)",
        "smartrecruiters": r"api\.smartrecruiters\.com/v1/companies/([A-Za-z0-9_-]+)",
        "oracle": r"([a-z0-9-]+)\.oraclecloud\.com",
    }
    for url in urls:
        try:
            r = requests.get(url, headers=BROWSER_UA, timeout=20,
                             allow_redirects=True)
            found = []
            for k, pat in pats.items():
                hits = {m.group(0) for m in re.finditer(pat, r.text, re.I)}
                if hits:
                    found.append(f"{k}={sorted(hits)[:2]}")
            if found:
                print(f"  {name:<14} {url[:52]:<52} {r.status_code} "
                      f"{' '.join(found)}", flush=True)
                return
        except Exception:
            pass
    print(f"  {name:<14} no ATS marker on {len(urls)} candidate pages", flush=True)


def main():
    """Round 12 — bulk sweep for the 40+ target.

    Measured rate: 79 employers -> 53 roles -> 27 at fit 75+, i.e. roughly one
    good role per three employers. Component analysis showed nothing is capped
    (each earns 69-90% on average) and only 5 roles sit at 70-74, so
    recalibrating the score would NOT close the gap — it is purely supply.
    Reaching 40+ therefore needs ~40 more employers, so this sweep is wide.
    """
    section("board sweep 3 — wide, for volume")
    board_sweep([
        # devtools / infra / data (national, high comp, remote-friendly)
        "gitlab", "hashicorp", "confluent", "elastic", "grafanalabs", "sentry",
        "launchdarkly", "postman", "fivetran", "dbtlabs", "benchling", "samsara",
        "rubrik", "wiz", "cloudflare", "twilio", "okta", "hubspot", "snyk",
        "jfrog", "sigmacomputing", "montecarlodata", "airbyte", "supabase",
        # fintech / payments / wealth
        "gusto", "rippling", "deel", "toast", "carta", "addepar", "wealthfront",
        "klarna", "wise", "chainalysis", "circle", "checkr", "found",
        # consumer / commerce / marketplaces with real finance orgs
        "lyft", "eventbrite", "patreon", "faire", "whatnot", "thredup",
        "renttherunway", "sweetgreen", "shakeshack", "hellofresh", "grubhub",
        "gopuff", "olo", "warbyparkerinc", "glossierinc",
        # health tech (NYC-dense)
        "hims", "talkspace", "komodohealth", "tempus", "maven", "kindbody",
        "springhealth", "lyrahealth", "modernhealth", "calm", "noom", "whoop",
        "oscar", "cityblockhealth", "included",
        # NYC media / publishing — big corporate finance teams
        "nytimes", "condenast", "hearst", "forbes", "businessinsider", "axios",
        "vox", "buzzfeed", "vimeoinc", "outbrain", "integralad", "mediaocean",
        # enterprise NYC
        "uipath", "peloton-interactive", "betterhelp", "namely", "policygenius",
        "bettercom", "compass", "flatironhealth", "capitalonesoftware",
    ])


def round11():
    """Round 11 — the missing sector: NYC financial services and media.

    The board is at 46 roles / 24 at fit 75+ against a 40+ target. Every
    remaining gain is supply, and the densest untapped pool is exactly the
    sector with the most senior corporate FP&A seats in this city: banks, asset
    managers, insurers, index/ratings firms and the media conglomerates. Round
    10 proved their Workday tenants don't follow the company slug, so this
    hunts the handoff link on their job-search subpages instead.
    """
    section("Amex — verify the Eightfold tenant found in round 9")
    for dom in ("aexp.com", "americanexpress.com", "amex.com"):
        try_get(f"  aexp domain={dom}",
                f"https://aexp.eightfold.ai/api/apply/v2/jobs?domain={dom}"
                f"&query=finance&start=0&num=3", probe_keys=("count", "positions"))

    section("marker hunt — financial services")
    for name, urls in (
            ("BlackRock", ["https://careers.blackrock.com/search-jobs",
                           "https://careers.blackrock.com/early-careers",
                           "https://www.blackrock.com/corporate/careers/professionals"]),
            ("Visa", ["https://usa.visa.com/careers/job-search.html",
                      "https://jobs.visa.com/search-jobs",
                      "https://usa.visa.com/careers.html"]),
            ("Moody's", ["https://careers.moodys.com/search-jobs",
                         "https://careers.moodys.com/jobs"]),
            ("S&P Global", ["https://careers.spglobal.com/search-jobs",
                            "https://www.spglobal.com/en/careers/jobs"]),
            ("MSCI", ["https://careers.msci.com/search-jobs",
                      "https://www.msci.com/careers/open-positions"]),
            ("MetLife", ["https://jobs.metlife.com/search-jobs",
                         "https://www.metlife.com/about-us/careers/"]),
            ("Prudential", ["https://jobs.prudential.com/search-jobs",
                            "https://www.prudential.com/careers"]),
            ("New York Life", ["https://jobs.newyorklife.com/search-jobs",
                               "https://www.newyorklife.com/careers"]),
            ("TIAA", ["https://careers.tiaa.org/search-jobs",
                      "https://www.tiaa.org/public/about-tiaa/careers"]),
            ("Equitable", ["https://careers.equitable.com/search-jobs",
                           "https://equitable.com/about-us/careers"]),
            ("Citi", ["https://jobs.citi.com/search-jobs",
                      "https://www.citigroup.com/global/careers"]),
            ("Blackstone", ["https://www.blackstone.com/careers/open-positions/",
                            "https://www.blackstone.com/careers/"]),
            ("KKR", ["https://www.kkr.com/careers", "https://jobs.kkr.com/"]),
            ("Apollo", ["https://www.apollo.com/careers",
                        "https://careers.apollo.com/"])):
        marker_hunt(name, urls)

    section("marker hunt — media & large tech")
    for name, urls in (
            ("IBM", ["https://www.ibm.com/careers/search?field_keyword_08[0]=Finance",
                     "https://www.ibm.com/careers/us-en/"]),
            ("NBCUniversal", ["https://www.nbcunicareers.com/search-jobs",
                              "https://jobs.nbcuni.com/search-jobs"]),
            ("Paramount", ["https://careers.paramount.com/search-jobs",
                           "https://www.paramount.com/careers/jobs"]),
            ("WBD", ["https://careers.wbd.com/search-jobs",
                     "https://careers.wbd.com/global/en/search-results"]),
            ("Disney", ["https://jobs.disneycareers.com/search-jobs",
                        "https://www.disneycareers.com/en/search-jobs"]),
            ("Etsy", ["https://careers.etsy.com/jobs/search",
                      "https://careers.etsy.com/"]),
            ("Bloomberg", ["https://bloomberg.com/company/careers/search/",
                           "https://careers.bloomberg.com/job/search"]),
            ("SiriusXM", ["https://careers.siriusxm.com/search-jobs",
                          "https://careers.siriusxm.com/"]),
            ("Warner Music", ["https://www.wmg.com/careers",
                              "https://careers.wmg.com/search-jobs"]),
            ("Spotify", ["https://www.lifeatspotify.com/jobs?l=new-york"])):
        marker_hunt(name, urls)


def round10():
    """Round 10 — second expansion pass, aiming at the owner's 40+ target.

    Round 9 took the board to 39 roles / 20 at fit 75+. Reaching 40+ at 75+
    needs roughly double the supply of good roles, so: another batch of
    NYC-dense boards, and a brute-force hunt for the Workday tenants of the big
    financial-services and media employers, which are the densest source of
    senior corporate FP&A seats in this city and are all currently missing.
    """
    section("board sweep 2 — more NYC tech, fintech, media, health")
    board_sweep([
        # fintech / markets
        "circle", "fireblocks", "paxos", "chainalysis", "flexport", "stash",
        "policygenius", "lemonade", "trumid", "clearcover", "kin", "bilt",
        "mercury", "modern-treasury", "unit", "increase",
        # NYC enterprise / data / devtools
        "starburst", "cockroachlabs", "clickhouse", "temporal", "hasura",
        "vercel", "linear", "retool", "sourcegraph", "1password", "grammarly",
        "duolingo", "spring-health", "openai", "anthropic", "scaleai",
        # commerce / media / consumer with NYC finance orgs
        "shopify", "wayfair", "chewy", "seatgeek", "vimeo", "sirius-xm",
        "audacy", "outbrain", "taboola", "integralads", "teads", "mediaocean",
        # health / insurance
        "devoted-health", "included-health", "alma", "headway", "octave",
    ])

    section("Workday tenant hunt — big financial services & media")
    for slug in ("visa", "blackrock", "moodys", "spglobal", "msci", "ibm",
                 "etsy", "nbcuniversal", "paramount", "wbd", "disney",
                 "goldmansachs", "morganstanley", "citi", "fiserv", "ice",
                 "amex", "aexp", "guardianlife", "metlife", "prudential",
                 "newyorklife", "tiaa", "voya", "equitable"):
        wd_matrix(slug)


def round9():
    """Round 9 — roster expansion. The owner wants more volume: NYC is a huge
    market, remote is acceptable, and senior FP&A is a common role.

    Strategy is breadth-first over the adapters we already have, because those
    cost one request per employer. Greenhouse/Lever/Ashby all return a whole
    board, so each added company there is nearly free at runtime. Workday needs
    an exact host/tenant/site, so those are read off careers pages rather than
    guessed.
    """
    section("board sweep — NYC-heavy tech, fintech and consumer")
    board_sweep([
        # fintech / crypto — NYC-dense, pays in band
        "ramp", "brex", "plaid", "chime", "affirm", "robinhood", "coinbase",
        "betterment", "gemini", "sofi", "marqeta", "current", "petal", "alloy",
        # NYC consumer / commerce / media tech
        "squarespace", "peloton", "warbyparker", "etsy", "instacart", "roblox",
        "reddit", "discord", "figma", "notion", "databricks", "mongodb",
        "braze", "datadoghq", "digitalocean", "bombas", "glossier", "casper",
        # health / insurance tech (big NYC finance orgs)
        "oscarhealth", "cedar", "ro", "zocdoc", "capsule", "flatiron",
        "hingehealth", "cityblock",
        # enterprise SaaS with NYC finance teams
        "asana", "airtable", "amplitude", "sprinklr", "yext", "justworks",
        "unqork", "dataiku", "attentive", "klaviyo",
    ])

    section("Workday / other ATS — read off the careers page")
    for name, url in (
            ("Amex", "https://www.americanexpress.com/en-us/careers/"),
            ("Mastercard", "https://careers.mastercard.com/us/en"),
            ("Visa", "https://usa.visa.com/careers.html"),
            ("BlackRock", "https://careers.blackrock.com/"),
            ("Moody's", "https://careers.moodys.com/"),
            ("S&P Global", "https://www.spglobal.com/en/careers"),
            ("MSCI", "https://www.msci.com/careers"),
            ("Nasdaq", "https://www.nasdaq.com/about/careers"),
            ("BMS", "https://careers.bms.com/"),
            ("Regeneron", "https://careers.regeneron.com/"),
            ("IBM", "https://www.ibm.com/careers/search"),
            ("NBCUniversal", "https://www.nbcunicareers.com/"),
            ("Paramount", "https://www.paramount.com/careers"),
            ("WBD", "https://careers.wbd.com/"),
            ("Disney", "https://jobs.disneycareers.com/"),
            ("Etsy", "https://careers.etsy.com/"),
            ("MongoDB", "https://www.mongodb.com/company/careers"),
            ("Squarespace", "https://www.squarespace.com/careers"),
            ("Peloton", "https://www.onepeloton.com/careers"),
            ("Spotify", "https://www.lifeatspotify.com/jobs")):
        wd_from_page(name, url)


def round8():
    """Round 8 — last Microsoft attempt, then it gets documented and dropped.

    Round 7 found the real host in the app shell: app.eightfold.ai with
    domain=microsoft.com (Eightfold's multi-tenant host, not Microsoft's own
    domain — which is why every microsoft.com path returned the SPA shell).
    That host answers 403 from the local sandbox under any UA, so the question
    is whether it wants a Referer or simply blocks non-browser callers.
    """
    section("Microsoft — app.eightfold.ai access")
    base = "https://app.eightfold.ai/api/apply/v2/jobs"
    q = "?domain=microsoft.com&query=finance&start=0&num=3"
    ref = {"Referer": "https://jobs.careers.microsoft.com/",
           "Origin": "https://jobs.careers.microsoft.com"}
    try_get("  browser UA only", base + q, probe_keys=("count", "positions"))
    try_get("  browser UA + referer", base + q,
            ua={**BROWSER_UA, **ref, "Accept": "application/json"},
            probe_keys=("count", "positions"))
    try_get("  adapter UA + referer", base + q,
            ua={**ADAPTER_UA, **ref}, probe_keys=("count", "positions"))
    try_get("  netflix host, ms domain",
            "https://explore.jobs.netflix.net/api/apply/v2/jobs"
            "?domain=microsoft.com&query=finance&start=0&num=3",
            probe_keys=("count", "positions"))
    # Control: the Netflix call still works from this runner, so a 403 above is
    # about this host/tenant and not about the runner's egress.
    try_get("  CONTROL netflix/netflix",
            "https://explore.jobs.netflix.net/api/apply/v2/jobs"
            "?domain=netflix.com&query=finance&start=0&num=2",
            probe_keys=("count",))


def round7():
    """Round 7 — Microsoft only. Ask the app shell what its Eightfold domain is.

    Round 6's guess (domain=microsoft.com) returned ok=False. Rather than guess
    again, read the config out of the page the SPA boots from — the same
    read-it-off-the-page move that produced dentsu's DAN_GLOBAL after seven
    wrong guesses.
    """
    section("Microsoft — Eightfold config in the app shell")

    def shell():
        r = requests.get("https://jobs.careers.microsoft.com/global/en/search",
                         headers=BROWSER_UA, timeout=T)
        h = r.text
        print(f"  shell -> {r.status_code} len={len(h)}")
        for pat in (r'"domain"\s*:\s*"([^"]{3,40})"',
                    r'domain=([a-z0-9.-]+\.[a-z]{2,})',
                    r'"companyName"\s*:\s*"([^"]{2,40})"',
                    r'apply/v2/[a-z]+', r'([a-z0-9-]+)\.eightfold\.ai'):
            hits = sorted({m.group(1) if m.groups() else m.group(0)
                           for m in re.finditer(pat, h, re.I)})
            if hits:
                print(f"    {pat[:30]}: {hits[:6]}")
    show("shell", shell)

    for label, host, domain in (
            ("careers.microsoft.com domain", "jobs.careers.microsoft.com",
             "careers.microsoft.com"),
            ("microsoft.com domain", "jobs.careers.microsoft.com", "microsoft.com"),
            ("bare host", "careers.microsoft.com", "microsoft.com")):
        try_get(f"  {label}",
                f"https://{host}/api/apply/v2/jobs?domain={domain}&query=finance"
                f"&start=0&num=3", probe_keys=("count", "positions"))

    # Diagnostic only: is the gcsservices failure a cert-chain problem or a
    # block? We would not ship verify=False — this only tells us which it is.
    def gcs_unverified():
        import urllib3
        urllib3.disable_warnings()
        r = requests.get("https://gcsservices.careers.microsoft.com/search/api/v1/"
                         "search?q=finance&l=en_us&pg=1&pgSz=3", headers=BROWSER_UA,
                         timeout=T, verify=False)
        print(f"  gcs verify=False -> {r.status_code} len={len(r.text)}")
    show("gcs-unverified", gcs_unverified)


def round6():
    """Round 6 — exercise the three new configs end-to-end before enabling.

    Rounds 4-5 identified Netflix + Microsoft as Eightfold and read dentsu's
    real Workday site name off its careers page. Nothing gets `enabled: true`
    until the actual adapter returns scoreable records here — the round-1
    SmartRecruiters lesson (a 200 with zero results looked like verification).
    """
    import yaml
    from pathlib import Path
    cos = yaml.safe_load(
        (Path(__file__).resolve().parent.parent / "config" / "companies.yaml")
        .read_text(encoding="utf-8"))["companies"]
    by_name = {c["name"]: c for c in cos}

    for name in ("Netflix", "Microsoft", "Dentsu"):
        section(f"{name} — end-to-end via the real adapter")
        co = by_name[name]
        fn = sources.DIRECT_ADAPTERS[co["ats"]]
        for q in ("financial planning", "finance manager"):
            print(f"  query={q!r}")
            show(name, lambda co=co, fn=fn, q=q: run_adapter(name, fn, co, q))

    section("Google — are titles recoverable from the results HTML?")

    def goog2():
        r = requests.get("https://www.google.com/about/careers/applications/jobs/"
                         "results/", params={"q": "financial planning analysis"},
                         headers=BROWSER_UA, timeout=T)
        h = r.text
        # Titles sit in the anchor text of the job links in the server HTML; if
        # they do not, Google needs a browser and is out of scope for a cron.
        soup = BeautifulSoup(h, "html.parser")
        rows = []
        for a in soup.find_all("a", href=re.compile(r"jobs/results/\d+")):
            t = a.get_text(" ", strip=True)
            if t:
                rows.append((a["href"].split("/")[-1][:28], t[:70]))
        print(f"  anchors with text: {len(rows)}")
        for rid, t in rows[:8]:
            print(f"    {rid} | {t}")
        one = re.search(r"jobs/results/(\d+)", h)
        if one:
            d = requests.get("https://www.google.com/about/careers/applications/"
                             f"jobs/results/{one.group(1)}", headers=BROWSER_UA,
                             timeout=T)
            dd = BeautifulSoup(d.text, "html.parser")
            ld = dd.find("script", {"type": "application/ld+json"})
            print(f"  detail page -> {d.status_code} len={len(d.text)} "
                  f"ld+json={'yes' if ld else 'no'}")
            if ld:
                print(f"    ld head: {ld.string[:200]!r}")
            txt = dd.get_text(" ", strip=True)
            m = FIN_HINT.search(txt)
            print(f"    finance text present: {bool(m)}")
            if m:
                print(f"    ...{txt[max(0, m.start()-120):m.start()+160]!r}")
    show("google", goog2)


def round5():
    """Round 5 — resolve what round 4 left open.

    Round 4 settled two: Netflix is Eightfold (count=16 for a finance query)
    and DoorDash's Greenhouse board is `doordashusa`, not `doordash` (467
    jobs). This round chases the rest: the exact shape of the Eightfold
    payload (does the list carry descriptions, or is a detail call needed?),
    dentsu's Workday site name, Microsoft's SSL failure, and the real careers
    URLs for the holdcos whose pages 404'd.
    """
    section("Netflix Eightfold — full payload shape")

    def nf():
        r = requests.get("https://explore.jobs.netflix.net/api/apply/v2/jobs",
                         params={"domain": "netflix.com", "query": "finance",
                                 "location": "New York", "start": 0, "num": 3},
                         headers=BROWSER_UA, timeout=T)
        pos = (r.json().get("positions") or [])
        print(f"  list -> {r.status_code} positions={len(pos)}")
        if pos:
            p = pos[0]
            print(f"  ALL KEYS: {sorted(p.keys())}")
            for k in ("job_description", "description", "name", "location",
                      "canonical_positon_url", "canonical_position_url",
                      "t_create", "salary_range", "pay_range"):
                if k in p:
                    print(f"    {k}: {str(p[k])[:180]!r}")
            pid = p.get("id")
            try_get("  detail",
                    f"https://explore.jobs.netflix.net/api/apply/v2/jobs/{pid}"
                    f"?domain=netflix.com",
                    probe_keys=("job_description", "name"))
    show("netflix", nf)

    section("dentsu — full Workday URL from the careers page")

    def dentsu():
        r = requests.get("https://www.dentsu.com/careers", headers=BROWSER_UA,
                         timeout=T)
        urls = set(re.findall(r"[a-z0-9-]+\.wd\d+\.myworkdayjobs\.com[^\"'\s<>\\]*",
                              r.text, re.I))
        for u in sorted(urls)[:8]:
            print(f"    {u}")
    show("dentsu", dentsu)
    for site in ("DACareers", "dentsu", "Careers", "External", "dentsucareers",
                 "dentsu_Careers", "DentsuCareers"):
        try_get(f"  wd dentsuaegis/{site}",
                f"https://dentsuaegis.wd3.myworkdayjobs.com/wday/cxs/dentsuaegis/"
                f"{site}/jobs", probe_keys=("total",))

    section("Microsoft — retry after SSLError, alternate hosts")
    for label, url in (
            ("gcs plain", "https://gcsservices.careers.microsoft.com/search/api/v1/"
                          "search?q=finance&l=en_us&pg=1&pgSz=3&o=Relevance&flt=true"),
            ("gcs no-verify-note", "https://gcsservices.careers.microsoft.com/"
                                   "search/api/v1/search?q=finance&l=en_us&pg=1&pgSz=3"),
            ("jobs host api", "https://jobs.careers.microsoft.com/search/api/v1/"
                              "search?q=finance&l=en_us&pg=1&pgSz=3")):
        try_get(label, url, probe_keys=("operationResult.result.totalJobs",))

    section("Google — is the job JSON embedded in the results HTML?")

    def goog():
        r = requests.get("https://www.google.com/about/careers/applications/jobs/"
                         "results/", params={"q": "financial planning analysis",
                                             "location": "New York"},
                         headers=BROWSER_UA, timeout=T)
        h = r.text
        print(f"  results html -> {r.status_code} len={len(h)}")
        for pat, label in ((r"AF_initDataCallback", "AF_initDataCallback"),
                           (r"<script[^>]+application/ld\+json", "ld+json"),
                           (r"jobs/results/(\d+)", "job-id links")):
            print(f"    {label}: {len(re.findall(pat, h))}")
        ids = re.findall(r"jobs/results/(\d+)[-a-z0-9]*", h)[:5]
        print(f"    sample ids: {ids}")
        for m in re.finditer(r'<script type="application/ld\+json">(.{0,400})', h,
                             re.S):
            print(f"    ld+json head: {m.group(1)[:220]!r}")
            break
    show("google", goog)

    section("Apple — csrf token + correct search path")

    def apple():
        s = requests.Session()
        r = s.get("https://jobs.apple.com/en-us/search", headers=BROWSER_UA,
                  timeout=T)
        tok = None
        for pat in (r'"csrfToken"\s*:\s*"([^"]+)"', r'name="csrf_token"[^>]*content="([^"]+)"',
                    r'csrfToken=([A-Za-z0-9+/=_-]+)'):
            m = re.search(pat, r.text)
            if m:
                tok = m.group(1)
                print(f"    csrf via {pat[:24]}: {tok[:28]}...")
                break
        if not tok:
            print("    no csrf token found in the search page")
        hdr = {**BROWSER_UA, "Content-Type": "application/json",
               "X-Apple-CSRF-Token": tok or "", "Referer":
               "https://jobs.apple.com/en-us/search"}
        for path in ("/api/role/search", "/api/v1/jobmodel/search",
                     "/api/search/results"):
            try:
                rr = s.post("https://jobs.apple.com" + path, headers=hdr, timeout=T,
                            json={"query": "finance", "page": 1,
                                  "locale": "en-us", "sort": "relevance"})
                print(f"    POST {path} -> {rr.status_code} len={len(rr.text)}")
            except Exception as e:
                print(f"    POST {path} EXC {type(e).__name__}")
    show("apple", apple)

    section("Uber / Spotify — find the endpoint from the careers page")
    for label, url in (("uber", "https://www.uber.com/us/en/careers/list/"),
                       ("spotify", "https://www.lifeatspotify.com/jobs")):
        def f(label=label, url=url):
            r = requests.get(url, headers=BROWSER_UA, timeout=T)
            print(f"  {label} -> {r.status_code} len={len(r.text)}")
            apis = set(re.findall(r"[\"'](/[a-z0-9/_-]*api[a-z0-9/_-]*)[\"']",
                                  r.text, re.I))
            print(f"    internal api paths: {sorted(apis)[:10]}")
            ext = set(re.findall(r"https://[a-z0-9.-]*(?:api|jobs)[a-z0-9.-]*\.[a-z]{2,}/[a-z0-9/_-]{0,40}",
                                 r.text, re.I))
            print(f"    external api hosts: {sorted(ext)[:8]}")
        show(label, f)
    ats_markers("spotify markers", "https://www.lifeatspotify.com/jobs")

    section("Holdcos — correct careers URLs")
    for label, url in (
            ("publicis alt", "https://www.publicisgroupe.com/en/careers/join-us"),
            ("publicis root", "https://www.publicisgroupe.com/en"),
            ("havas alt", "https://www.havasgroup.com/careers/"),
            ("omnicom alt", "https://www.omnicomgroup.com/"),
            ("wpp jobs", "https://www.wpp.com/en/careers/jobs"),
            ("groupm", "https://www.groupm.com/careers/"),
            ("ogilvy", "https://www.ogilvy.com/careers")):
        ats_markers(label, url)


def round4():
    """Round 4 — one dispatch for every company still dark on the roster.

    Browser-based capture was tried first and is walled off (the in-app pane is
    denied navigation to the API hosts), so this goes back to the Actions
    runner. Candidates come from each vendor's known SPA endpoint shape; the
    finance-hits count tells us whether a 200 actually contains job data rather
    than a shell page.
    """
    section("Microsoft — gcsservices search API")
    ms = ("https://gcsservices.careers.microsoft.com/search/api/v1/search"
          "?q=finance&l=en_us&pg=1&pgSz=5&o=Relevance&flt=true")
    try_get("ms plain", ms,
            probe_keys=("operationResult.result.totalJobs",
                        "operationResult.result.jobs"))
    try_get("ms +NY", ms + "&lc=New%20York%2C%20New%20York%2C%20United%20States",
            probe_keys=("operationResult.result.totalJobs",
                        "operationResult.result.jobs"))

    section("Netflix — Eightfold")
    try_get("netflix eightfold",
            "https://explore.jobs.netflix.net/api/apply/v2/jobs?domain=netflix.com"
            "&query=finance&location=New%20York&start=0&num=5",
            probe_keys=("count", "positions"))

    section("Uber")
    try_post("uber loadSearchJobsResults",
             "https://www.uber.com/api/loadSearchJobsResults?localeCode=en",
             ua={**BROWSER_UA, "Content-Type": "application/json",
                 "x-csrf-token": "x"},
             json={"params": {"location": [{"country": "USA", "region": "NY"}]},
                   "page": 0, "limit": 5, "query": "finance"},
             probe_keys=("data.results", "data.totalResults"))

    section("Spotify")
    try_get("spotify appspot api",
            "https://api-dot-new-spotifyjobs-com.appspot.com/wp-json/animus/v1/job/"
            "?c=finance&l=new-york", probe_keys=("result",))
    try_get("lifeatspotify api", "https://www.lifeatspotify.com/api/jobs")

    section("Apple")
    try_get("apple search page", "https://jobs.apple.com/en-us/search?location=new-york-state-NY",
            want_json=False)
    try_post("apple role search", "https://jobs.apple.com/api/role/search",
             ua={**BROWSER_UA, "Content-Type": "application/json"},
             json={"query": "finance", "filters": {"postingpostLocation":
                   ["postLocation-USANY"]}, "page": 1},
             probe_keys=("res.totalRecords", "res.searchResults"))

    section("Google")
    try_get("google results html",
            "https://www.google.com/about/careers/applications/jobs/results/"
            "?q=finance&location=New%20York", want_json=False)
    try_get("google api v3 jobs",
            "https://www.google.com/about/careers/applications/api/v3/search/"
            "?q=finance&location=New+York")

    section("DoorDash / Intuit — find the real ATS")
    for tok in ("doordash", "doordashusa", "doordashcareers", "doordashinc"):
        try_get(f"gh {tok}",
                f"https://boards-api.greenhouse.io/v1/boards/{tok}/jobs",
                probe_keys=("jobs",))
    ats_markers("doordash careers", "https://careersatdoordash.com/")
    ats_markers("intuit careers", "https://www.intuit.com/careers/")

    section("Advertising holdcos — SmartRecruiters tokens + ATS markers")
    for tok in ("PublicisGroupe", "PublicisGroupeGlobal", "Publicis", "PublicisSapient",
                "HavasGroup", "Havas", "dentsu", "dentsuinternational",
                "DentsuAegisNetwork", "Omnicom", "WPP"):
        try_get(f"sr {tok}",
                f"https://api.smartrecruiters.com/v1/companies/{tok}/postings?limit=3",
                probe_keys=("totalFound",))
    for label, url in (("publicis", "https://www.publicisgroupe.com/en/careers"),
                       ("havas", "https://havas.com/careers/"),
                       ("dentsu", "https://www.dentsu.com/careers"),
                       ("omnicom", "https://www.omnicomgroup.com/careers/"),
                       ("wpp", "https://www.wpp.com/careers")):
        ats_markers(label, url)


def round1():
    """Round 1 — fingerprint the guessed endpoints in one dispatch.

    Everything here is a guess-then-verify config candidate: Workday tenants,
    Greenhouse board tokens, one SmartRecruiters token, and the Google careers
    API that unifier-jobs never used (it watched Google with a generic_page
    keyword check, which is useless on a board where every posting says
    "finance"). Batched deliberately — one dispatch, not one per company.
    """
    section("round 1a — Workday tenant guesses")
    for host, tenant, site in [
        ("adobe.wd5.myworkdayjobs.com", "adobe", "external_experienced"),
        ("adobe.wd5.myworkdayjobs.com", "adobe", "AdobeCareers"),
        ("salesforce.wd12.myworkdayjobs.com", "salesforce", "External_Career_Site"),
        ("salesforce.wd1.myworkdayjobs.com", "salesforce", "External_Career_Site"),
        ("intuit.wd1.myworkdayjobs.com", "intuit", "intuitcareers"),
        ("intuit.wd1.myworkdayjobs.com", "intuit", "IntuitExternalCareerSite"),
        ("paypal.wd1.myworkdayjobs.com", "paypal", "jobs"),
        ("paypal.wd1.myworkdayjobs.com", "paypal", "PayPalCareers"),
    ]:
        cxs(host, tenant, site)

    section("round 1b — Greenhouse board tokens")
    for board in ("airbnb", "pinterest", "stripe", "datadog", "doordash",
                  "block", "spotify"):
        greenhouse(board)

    section("round 1c — SmartRecruiters tokens")
    for company in ("PublicisGroupe", "Publicis", "Havas", "dentsu"):
        smartrecruiters(company)

    section("round 1d — Google careers API shape")
    for url in ("https://careers.google.com/api/v3/search/?q=finance",
                "https://www.google.com/about/careers/applications/api/v3/"
                "search/?q=finance"):
        show(url, lambda u=url: get(u, ua=ADAPTER_UA))

    section("round 1e — already-enabled adapters, FP&A query end-to-end")
    show("amazon", lambda: run_adapter(
        "amazon", sources.fetch_amazon_jobs, {"name": "Amazon"}))
    show("nvidia", lambda: run_adapter("nvidia", sources.fetch_workday, {
        "name": "NVIDIA", "workday_host": "nvidia.wd5.myworkdayjobs.com",
        "workday_tenant": "nvidia", "workday_site": "NVIDIAExternalCareerSite"}))
    show("accenture", lambda: run_adapter("accenture", sources.fetch_workday, {
        "name": "Accenture", "workday_host": "accenture.wd103.myworkdayjobs.com",
        "workday_tenant": "accenture", "workday_site": "AccentureCareers"}))
    show("meta", lambda: run_adapter("meta", sources.fetch_meta_graphql,
                                     {"name": "Meta"}))
    show("oracle", lambda: run_adapter("oracle", sources.fetch_oracle_orc, {
        "name": "Oracle",
        "url": "https://eeho.fa.us2.oraclecloud.com/hcmRestApi/resources/latest/"
               "recruitingCEJobRequisitions",
        "site_number": "CX_45001", "search_query": "financial planning"}))


if __name__ == "__main__":
    main()
