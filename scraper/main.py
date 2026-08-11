"""Daily pipeline: fetch → qualify → dedup → expire → score → publish.
Run from repo root: python -m scraper.main"""
import datetime as dt
import re
from pathlib import Path

import yaml

from . import models, sources, site_gen
from .filters import (blocklisted, city_rank, excluded, extract_stated_comp,
                      function_hits, is_non_us, location_scope, qualifies,
                      score_job, seniority_level)

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config"
BOARD_MAX_AGE_DAYS = 90
GONE_AFTER_MISSES_DIRECT = 2
GONE_AFTER_MISSES_BOARD = 7
LONG_POSTED_DAYS = 90


def load_yaml(name):
    return yaml.safe_load((CONFIG / name).read_text(encoding="utf-8"))


def parse_date(s):
    """Best-effort parse of machine dates for classification only (age cutoffs,
    long-posted flag). Unparseable human strings ('Posted 3 Days Ago') -> None;
    display always shows the verbatim string regardless."""
    if not s:
        return None
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", str(s))
    if m:
        try:
            return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    return None


def roster_match(company, roster_norms):
    c = models.norm(company)
    if not c:
        return None
    for rn, entry in roster_norms.items():
        if rn in c or c in rn:
            return entry
    return None


def queries_for(co, kw):
    """Which search strings to send to one employer.

    Greenhouse gets a single empty query on purpose: its adapter downloads the
    whole board and filters client-side, so one request plus our own
    qualification gates beats five requests for the same payload.
    """
    if co.get("search_queries"):
        return co["search_queries"]
    if co.get("search_query"):
        return [co["search_query"]]
    if co["ats"] == "greenhouse":
        return [""]
    return kw["queries"]


def run():
    today = dt.date.today().isoformat()
    companies = load_yaml("companies.yaml")["companies"]
    kw = load_yaml("keywords.yaml")
    bl = load_yaml("blocklist.yaml")
    cities = load_yaml("cities.yaml")
    roles = load_yaml("roles.yaml")
    tier_of = {models.norm(c["name"]): c.get("tier") for c in companies}
    cat_of = {models.norm(c["name"]): c.get("category") for c in companies}

    store = models.load_jobs()
    baseline = not store
    # Scope is a hard rule, so it applies to the WHOLE store rather than only
    # today's fetch: when the filter is tightened, already-stored postings that
    # are now out of scope leave immediately instead of lingering two runs and
    # then being mislabelled "no longer listed" — they are still listed, just
    # not for us.
    dropped_scope = [k for k, j in store.items()
                     if is_non_us(j.get("location"))
                     or location_scope(j.get("location"), cities) == "other"]
    for k in dropped_scope:
        del store[k]
    for j in store.values():
        j["flags"] = [f for f in j["flags"] if f != "new"]

    triage = models.load_json(models.TRIAGE, [])
    triage_keys = {(t.get("company"), t.get("url")) for t in triage}
    health = models.load_json(models.HEALTH, {})
    roster_norms = {models.norm(c["name"]): c for c in companies}
    skipped = {}  # reason -> count, printed at the end of the run

    def note_skip(reason):
        key = re.sub(r":.*", "", reason)
        skipped[key] = skipped.get(key, 0) + 1

    def record_health(name, count, ok, inventory=None):
        h = health.setdefault(name, {"counts": [], "fail_streak": 0})
        if ok:
            h["counts"] = (h["counts"] + [count])[-5:]
            h["fail_streak"] = 0
        else:
            h["fail_streak"] += 1
        if inventory is not None:
            h["inventory"] = inventory  # source's total visible jobs (aliveness)
        h["last_run"] = today

    def add_triage(company, url, note, source):
        if (company, url) not in triage_keys:
            triage.append({"company": company, "url": url, "note": note,
                           "source": source, "first_seen": today})
            triage_keys.add((company, url))

    seen_this_run = {}  # source name -> set of job ids seen
    sources_ok = set()

    # ---- direct monitors ----
    for co in companies:
        if not co.get("enabled"):
            continue
        adapter = sources.DIRECT_ADAPTERS.get(co["ats"])
        if not adapter:
            continue
        src = f"{co['ats']}:{co['name']}"
        # One employer, several queries: merge on URL before doing any work, so
        # a posting matching three of the queries is processed once.
        merged, ok_any, inventory = {}, False, None
        for query in queries_for(co, kw):
            records, ok, inv = adapter(co, query)
            ok_any = ok_any or ok
            if inv is not None:
                inventory = inv
            for r in records:
                key = r.get("url") or (r.get("company"), r.get("title"))
                merged.setdefault(key, r)
        if ok_any:
            sources_ok.add(src)
        listings = 0
        for r in merged.values():
            if r.get("triage"):
                add_triage(r["company"], r["url"], r["note"], src)
                listings += 1
                continue
            ok_job, reason = qualifies(r.get("title"), r.get("description"),
                                       r.get("location"), kw, cities)
            if not ok_job:
                note_skip(reason)
                # The employer's own search matched but we couldn't read the
                # posting text — can't judge it, so a human should look rather
                # than it vanishing silently. Guarded by a title-only check:
                # Meta's search returns five fuzzy hits per query with no
                # description at all ("Planning Lead", "Capacity Strategy &
                # Planning Manager" for a financial-planning query, probe round
                # 1), and without this guard every one of them would land in
                # the triage queue on every single run.
                if (r.get("search_matched") and "planning/analysis" in reason
                        and function_hits(r.get("title"), None, kw)
                        and seniority_level(r.get("title"), kw)
                        and not excluded(r.get("title"), kw)):
                    add_triage(r["company"], r["url"],
                               f"employer search matched but posting text "
                               f"unavailable — verify: {r.get('title')}", src)
                continue
            comp = r.get("comp") or extract_stated_comp(r.get("description"))
            job = models.make_job(
                source=src, kind="direct", company=r["company"], title=r["title"],
                location=r.get("location"), url=r["url"],
                posted_date=r.get("posted_date"), comp=comp,
                description=r.get("description"), tier=1, today=today)
            _merge(store, job, today, baseline)
            seen_this_run.setdefault(src, set()).add(job["id"])
            listings += 1
        record_health(src, listings, ok_any, inventory)

    # ---- manually seeded postings ----
    # Escape hatch for employers whose sites refuse automated clients. Fields
    # are human-copied verbatim per rule 1, so they are trusted as-is; the
    # qualification gates still apply.
    for r in (load_yaml("seed_jobs.yaml") or {}).get("jobs") or []:
        if not (r.get("url") and r.get("company") and r.get("title")):
            continue
        src = f"seed:{r['company']}"
        sources_ok.add(src)
        ok_job, reason = qualifies(r.get("title"), r.get("description"),
                                   r.get("location"), kw, cities)
        if not ok_job:
            print(f"  seed skipped ({reason}): {r['company']} — {r['title']}")
            continue
        job = models.make_job(
            source=src, kind="direct", company=r["company"], title=r["title"],
            location=r.get("location"), url=r["url"],
            posted_date=r.get("posted_date"), comp=r.get("comp"),
            description=r.get("description"), tier=1, today=today)
        job["flags"].append("manual")
        _merge(store, job, today, baseline)
        seen_this_run.setdefault(src, set()).add(job["id"])
        record_health(src, 1, True)

    # ---- discovery boards ----
    # Discovery only (rule 4): a board hit becomes a triage entry so the
    # employer can be fingerprinted and monitored directly next run.
    board_batches = [("jsearch", sources.fetch_jsearch(kw["queries"])),
                     ("adzuna", sources.fetch_adzuna(kw["queries"])),
                     ("jooble", sources.fetch_jooble(kw["queries"]))]
    for name, (records, ok) in board_batches:
        if ok is None:
            continue  # no API key configured; silently skipped
        if ok:
            sources_ok.add(name)
        kept = 0
        # Aggregators syndicate one posting once per city. Job ids hash
        # location, so those would land as distinct cards — collapse on
        # company+title and keep the best-ranked location.
        seen_ct, deduped = {}, []
        for r in records:
            k = (models.norm(r.get("company")), models.norm(r.get("title")))
            prev = seen_ct.get(k)
            if prev is None:
                seen_ct[k] = len(deduped)
                deduped.append(r)
            elif (city_rank(r.get("location"), cities)
                  < city_rank(deduped[prev].get("location"), cities)):
                deduped[prev] = r  # nearer metro wins
        if len(deduped) != len(records):
            print(f"  {name}: collapsed {len(records)} -> {len(deduped)} "
                  f"(same job listed per-city)")
        for r in deduped:
            company, title = r.get("company"), r.get("title")
            if not (company and title and r.get("url")):
                continue
            country = (r.get("country") or "").upper()
            if country and country not in ("US", "USA", "UNITED STATES"):
                continue
            reason = blocklisted(company, title, bl)
            if reason:
                models.append_quarantine({"company": company, "title": title,
                                          "url": r["url"], "reason": reason,
                                          "source": name, "date": today})
                continue
            ok_job, why = qualifies(title, r.get("description"),
                                    r.get("location"), kw, cities)
            if not ok_job:
                note_skip(why)
                continue
            posted = parse_date(r.get("posted_date"))
            if posted and (dt.date.today() - posted).days > BOARD_MAX_AGE_DAYS:
                continue
            entry = roster_match(company, roster_norms)
            if entry and entry.get("enabled"):
                continue  # direct monitor is authoritative; drop board copy
            if entry:
                add_triage(company, r["url"],
                           "roster company not yet fingerprinted — verify ATS endpoint",
                           name)
            else:
                add_triage(company, r["url"],
                           "unknown employer — find direct posting, propose tier", name)
            comp = r.get("comp") or extract_stated_comp(r.get("description"))
            job = models.make_job(
                source=name, kind="board", company=company, title=title,
                location=r.get("location"), url=r["url"],
                posted_date=r.get("posted_date"), comp=comp,
                description=r.get("description"), tier=1, today=today)
            _merge(store, job, today, baseline)
            seen_this_run.setdefault(name, set()).add(job["id"])
            kept += 1
        record_health(name, kept, ok)

    # ---- expiry ----
    for j in store.values():
        if j["status"] != "active":
            continue
        src = j["source"]
        ran = src in sources_ok
        seen = j["id"] in seen_this_run.get(src, set())
        if ran and not seen:
            j["miss_count"] += 1
            limit = (GONE_AFTER_MISSES_DIRECT if j["kind"] == "direct"
                     else GONE_AFTER_MISSES_BOARD)
            if j["miss_count"] >= limit:
                j["status"] = "gone"
                j["gone_date"] = today
        posted = parse_date(j.get("posted_date"))
        if posted:
            age = (dt.date.today() - posted).days
            if age > LONG_POSTED_DAYS and "long-posted" not in j["flags"]:
                j["flags"].append("long-posted")
            if j["kind"] == "board" and age > BOARD_MAX_AGE_DAYS + 30:
                j["status"] = "gone"
                j["gone_date"] = j["gone_date"] or today

    # ---- derived scoring ----
    # Recomputed for the WHOLE store every run, not just today's fetch:
    # otherwise tuning roles.yaml never reaches the jobs already stored, and a
    # source that fails for a day would leave its jobs unscored.
    for j in store.values():
        score_job(j, kw, roles, cities, tier=tier_of.get(models.norm(j["company"])))
        j["category"] = cat_of.get(models.norm(j["company"]))

    # ---- health warnings ----
    warnings = []
    for name, h in health.items():
        if name.startswith("_"):
            continue
        if h.get("fail_streak", 0) >= 3:
            warnings.append(f"{name}: fetch failing ({h['fail_streak']} runs)")
        elif h.get("inventory") == 0:
            warnings.append(f"{name}: source reports 0 total jobs — monitor may be "
                            f"blind or endpoint changed")
        elif len(h.get("counts", [])) >= 3 and all(c == 0 for c in h["counts"][-3:]) \
                and any(c > 0 for c in h["counts"][:-3]):
            warnings.append(f"{name}: zero results for 3+ runs (was returning data)")
    health["_warnings"] = warnings

    models.save_jobs(store)
    models.save_json(models.TRIAGE, triage)
    models.save_json(models.HEALTH, health)
    # feed.json is a small machine-readable index of the same board. Nothing
    # consumes it today (this build has no MCP artifact — the Pages dashboard
    # is the product), but it is the seam to add one later without touching
    # the pipeline. Descriptions are deliberately excluded to keep it small.
    models.save_json(models.DATA / "feed.json", {
        "updated": today,
        "warnings": warnings,
        "roster": [{"name": c["name"], "tier": c["tier"], "ats": c["ats"],
                    "category": c.get("category"),
                    "enabled": bool(c.get("enabled")), "note": c.get("note")}
                   for c in companies],
        "triage": [t for t in triage if not t.get("status")],
        "jobs": [{k: j.get(k) for k in
                  ("id", "kind", "company", "category", "title", "location", "url",
                   "posted_date", "comp", "status", "gone_date", "flags", "fit",
                   "pivot", "level", "level_label", "gap_severity", "scope",
                   "remote", "recommendation", "below_comp")}
                 for j in sorted(store.values(),
                                 key=lambda x: (x["status"] != "active",
                                                -(x.get("fit") or 0)))],
    })
    site_gen.generate(store, companies, cities, roles, warnings, today)

    active = sum(1 for j in store.values() if j["status"] == "active")
    new = sum(1 for j in store.values() if "new" in j["flags"])
    best = sum(1 for j in store.values()
               if j["status"] == "active" and (j.get("fit") or 0) >= roles["bands"]["best"])
    print(f"run complete: {active} active listings ({best} at fit "
          f"{roles['bands']['best']}+), {new} new, {len(triage)} in triage queue, "
          f"{len(warnings)} health warnings"
          + (f", {len(dropped_scope)} dropped as out-of-scope" if dropped_scope else "")
          + (" [baseline run]" if baseline else ""))
    if skipped:
        top = sorted(skipped.items(), key=lambda kv: -kv[1])[:6]
        print("  filtered out: " + ", ".join(f"{k} ({n})" for k, n in top))


def _merge(store, job, today, baseline):
    old = store.get(job["id"])
    if old:
        old["last_seen"] = today
        old["miss_count"] = 0
        if old["status"] == "gone":
            old["status"] = "active"
            old["gone_date"] = None
        if old["kind"] == "board" and job["kind"] == "direct":
            keep_first_seen = old["first_seen"]
            store[job["id"]] = job
            job["first_seen"] = keep_first_seen
            return
        for f in ("posted_date", "comp", "description", "url", "location"):
            if job.get(f):
                old[f] = job[f]
    else:
        if not baseline:
            job["flags"].append("new")
        store[job["id"]] = job


if __name__ == "__main__":
    run()
