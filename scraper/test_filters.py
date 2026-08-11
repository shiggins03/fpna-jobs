"""Assertions for the qualification gates and derived scoring.
Run from repo root: python -m scraper.test_filters

Both directions matter, the same way they do in unifier-jobs: a gate that is
too loose fills the board with accounting roles, and one that is too tight
silently deletes real jobs — which is worse, because nothing on the dashboard
shows you what you lost. Add a case for every term list you change.
"""
from pathlib import Path

import yaml

from .filters import (excluded, fit_score, function_hits, gap_flags, is_non_us,
                      is_remote, location_scope, pivot_score, qualifies,
                      score_job, seniority_level, comp_sort_value,
                      function_areas, transferable_hits, demote_hits)

CONFIG = Path(__file__).resolve().parent.parent / "config"
KW = yaml.safe_load((CONFIG / "keywords.yaml").read_text(encoding="utf-8"))
ROLES = yaml.safe_load((CONFIG / "roles.yaml").read_text(encoding="utf-8"))
CITIES = yaml.safe_load((CONFIG / "cities.yaml").read_text(encoding="utf-8"))

FPNA_BODY = """
Own the annual operating plan and long-range plan for the Ads business unit.
Partner with senior leadership on headcount and opex planning, build driver-based
financial models, run monthly variance analysis against the operating plan, and
present the monthly business review to the CFO. You will own the P&L for the
segment and develop KPIs for the leadership team.
"""
CLIENT_FINANCE_BODY = """
Manage client profitability and client billing across the agency portfolio,
oversee revenue recognition under ASC 606, review unbilled balances, and support
scope of work pricing for the account teams. Monthly forecasting of client
revenue is required.
"""
ACCOUNTING_BODY = """
Lead the monthly close, prepare journal entries, maintain internal controls and
support the annual audit. Some budgeting exposure.
"""
SQL_BODY = FPNA_BODY + """
Requirements: advanced SQL required, you will write SQL daily against our
Snowflake data warehouse and build Looker dashboards.
"""

fails = []


def check(label, got, want):
    if got != want:
        fails.append(f"{label}: got {got!r}, want {want!r}")


def check_true(label, got):
    if not got:
        fails.append(f"{label}: expected truthy, got {got!r}")


# ---- exclusions -----------------------------------------------------------
# The owner's current job must never come back as a recommendation.
check("exclude SVP Client Finance",
      bool(excluded("SVP, Client Finance", KW)), True)
check("exclude Commercial Finance Director",
      bool(excluded("Director, Commercial Finance", KW)), True)
check("exclude Controller", bool(excluded("Assistant Controller", KW)), True)
check("exclude Tax Director", bool(excluded("Director, Tax", KW)), True)
check("keep Director FP&A", excluded("Director, FP&A", KW), None)
check("keep Strategic Finance Director",
      excluded("Director, Strategic Finance", KW), None)
# "financial analysis" must not trip the "accounting"/"analyst" exclusions
check("keep Manager Financial Planning & Analysis",
      excluded("Manager, Financial Planning & Analysis", KW), None)

# ---- seniority ------------------------------------------------------------
check("senior finance manager", seniority_level("Senior Finance Manager", KW),
      "senior_manager")
check("sr. director", seniority_level("Sr. Director, Strategic Finance", KW),
      "senior_director")
check("plain director", seniority_level("Director, FP&A", KW), "director")
check("finance manager", seniority_level("Finance Manager, Ads", KW), "manager")
check("vp finance", seniority_level("VP Finance", KW), "vp")
check("head of fp&a", seniority_level("Head of FP&A", KW), "vp")
# below the floor
check("financial analyst", seniority_level("Senior Financial Analyst", KW), None)
check("associate", seniority_level("Finance Associate", KW), None)
# no level word at all -> manager, never dropped (leveling often lives in body)
check("no level word", seniority_level("Business Finance, Ads", KW), "manager")

# ---- location scope -------------------------------------------------------
check("nyc", location_scope("New York, NY", CITIES), "nyc")
check("brooklyn", location_scope("Brooklyn, NY", CITIES), "nyc")
check("nyc metro", location_scope("Jersey City, NJ", CITIES), "nyc_metro")
check("stamford", location_scope("Stamford, CT", CITIES), "nyc_metro")
check("remote", location_scope("Remote - United States", CITIES), "remote")
check("seattle out", location_scope("Seattle, WA", CITIES), "other")
check("austin out", location_scope("Austin, TX", CITIES), "other")
check("multi unknown", location_scope("4 Locations", CITIES), "unknown")
check("none unknown", location_scope(None, CITIES), "unknown")
check("us only unknown", location_scope("United States", CITIES), "unknown")
# non-US scope is a separate, earlier gate
check("india non-us", is_non_us("Bengaluru, India"), True)
check("greece ny is us", is_non_us("Greece, NY"), False)
check("london non-us", is_non_us("London"), True)

# ---- remote detection -----------------------------------------------------
check("remote in location", is_remote("Remote, US", None, CITIES), True)
check("remote in body", is_remote("New York, NY",
                                  "This role is remote-eligible.", CITIES), True)
check("hybrid is not remote",
      is_remote("New York, NY", "Hybrid, 3 days in office.", CITIES), False)

# ---- qualification --------------------------------------------------------
ok, why = qualifies("Director, FP&A", FPNA_BODY, "New York, NY", KW, CITIES)
check("fpna role qualifies", ok, True)
ok, why = qualifies("Assistant Controller", ACCOUNTING_BODY, "New York, NY",
                    KW, CITIES)
check("accounting role rejected", ok, False)
ok, why = qualifies("Director, FP&A", FPNA_BODY, "Seattle, WA", KW, CITIES)
check("seattle rejected", ok, False)
ok, why = qualifies("Senior Financial Analyst", FPNA_BODY, "New York, NY",
                    KW, CITIES)
check("analyst rejected", ok, False)
# thin finance-adjacent text must not qualify on a single keyword
ok, why = qualifies("Finance Manager", "Support the team with forecasting.",
                    "New York, NY", KW, CITIES)
check("single signal rejected", ok, False)

# ---- scoring --------------------------------------------------------------
strong = {"title": "Director, FP&A", "description": FPNA_BODY,
          "comp": "$210,000 - $260,000 per year", "location": "New York, NY",
          "flags": [], "id": "x", "company": "Amazon", "first_seen": "2026-08-10"}
weak = {"title": "Finance Director", "description": CLIENT_FINANCE_BODY,
        "comp": "$150,000 - $170,000 per year", "location": "New York, NY",
        "flags": [], "id": "y", "company": "Publicis Groupe",
        "first_seen": "2026-08-10"}
score_job(strong, KW, ROLES, CITIES, tier="A")
score_job(weak, KW, ROLES, CITIES, tier="C")
check_true("strong pivot high", strong["pivot"] >= 8)
check_true("weak pivot low", weak["pivot"] <= 5)
check_true("strong outranks weak", strong["fit"] > weak["fit"] + 15)
check_true("strong is best band", strong["fit"] >= ROLES["bands"]["best"])
check("strong recommendation", strong["recommendation"], "Strong Apply")
check("weak flagged below comp", weak["below_comp"], True)

# Unknown comp must score NEUTRAL, not zero — an unpriced strong role stays on
# the board per the owner's spec.
nocomp = dict(strong, comp=None, id="z")
score_job(nocomp, KW, ROLES, CITIES, tier="A")
check_true("unknown comp still qualifies well",
           nocomp["fit"] >= ROLES["bands"]["stretch"])

# A Tier A "Manager" must not be penalised for its title (owner directive).
mgr_a = dict(strong, title="Finance Manager", id="m1")
mgr_c = dict(strong, title="Finance Manager", id="m2", company="Havas")
score_job(mgr_a, KW, ROLES, CITIES, tier="A")
score_job(mgr_c, KW, ROLES, CITIES, tier="C")
check_true("tier A manager lifted", mgr_a["fit"] > mgr_c["fit"])

# ---- gaps -----------------------------------------------------------------
gaps = gap_flags("Director, FP&A", SQL_BODY, ROLES)
check_true("sql gap detected", any(g["key"] == "sql" for g in gaps))
check("sql gap is red",
      next(g["severity"] for g in gaps if g["key"] == "sql"), "red")
# one incidental mention must NOT raise a red flag
one_sql = gap_flags("Director, FP&A", FPNA_BODY + " SQL a plus.", ROLES)
check("single sql mention ignored",
      any(g["key"] == "sql" for g in one_sql), False)

# ---- comp parsing ---------------------------------------------------------
check("range top", comp_sort_value("$190,000 - $240,000"), 240000.0)
check("k suffix", comp_sort_value("$200K-$250K"), 250000.0)
check("no comp", comp_sort_value(None), -1.0)

if fails:
    print(f"FAIL ({len(fails)})")
    for f in fails:
        print("  -", f)
    raise SystemExit(1)
print("all filter assertions pass")
