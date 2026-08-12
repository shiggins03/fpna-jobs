"""Qualification gates, location scope, comp extraction, and derived scoring.

Two kinds of value live in here and they must not be confused:

  VERBATIM   — title, location, posted date, comp string, description. Quoted
               from the source or None. `extract_stated_comp` quotes the
               posting's own sentence; it never computes a number.
  DERIVED    — fit score, FP&A transition score, seniority band, function
               areas, gap flags, recommendation. Computed from term lists in
               config/roles.yaml, always rendered with a "derived" marker in
               the UI. See CLAUDE.md rule 1.

The US-scope regexes are carried over unchanged from unifier-jobs, where both
directions are covered by test_filters (a missed foreign metro puts
out-of-scope jobs on the board; an over-broad pattern silently deletes real US
jobs, which is worse).
"""
import re

NON_US = re.compile(
    r"\b(india|united kingdom|\buk\b|england|scotland|wales|"
    r"dubai|abu dhabi|uae|saudi|riyadh|qatar|doha|"
    # country names only — city names like Cairo/Jordan collide with US towns
    r"egypt|\boman\b|muscat|kuwait|bahrain|amman|lithuania|vilnius|"
    r"canada|toronto|vancouver|ontario|australia|sydney|melbourne|singapore|philippines|"
    r"malaysia|hyderabad|bangalore|bengaluru|chennai|mumbai|pune|noida|gurgaon|delhi|"
    r"ireland|germany|poland|romania|mexico|\bmx\b|brazil|colombia|"
    r"argentina|buenos aires|chile|peru|santiago|"
    r"kolkata|calcutta|gurugram|ahmedabad|jaipur|coimbatore|kochi|cochin|"
    r"trivandrum|thiruvananthapuram|mysuru|mysore|nagpur|indore|chandigarh|"
    r"vadodara|surat|bhubaneswar|visakhapatnam|madurai|lucknow|thane|"
    r"navi mumbai|\bgoa\b|karnataka|maharashtra|telangana|tamil nadu|kerala|"
    r"gujarat|haryana|uttar pradesh|west bengal|andhra pradesh|"
    r"sri lanka|colombo|bangladesh|dhaka|nepal|kathmandu|pakistan|karachi|lahore|"
    r"vietnam|viet nam|hanoi|ho chi minh|indonesia|jakarta|thailand|bangkok|"
    r"kuala lumpur|manila|quezon city|makati|taguig|cebu|"
    r"shanghai|beijing|shenzhen|guangzhou|hong kong|taiwan|taipei|"
    r"japan|tokyo|osaka|south korea|seoul|"
    r"turkey|turkiye|istanbul|ankara|ukraine|kyiv|kiev|lviv|belarus|minsk|"
    r"bulgaria|serbia|croatia|zagreb|czech|czechia|slovakia|bratislava|"
    r"hungary|budapest|bucharest|estonia|tallinn|latvia|riga|slovenia|"
    r"portugal|porto|spain|barcelona|netherlands|belgium|"
    r"switzerland|zurich|austria|sweden|norway|denmark|finland|"
    r"morocco|casablanca|tunisia|nigeria|kenya|nairobi|ghana|"
    r"south africa|johannesburg|cape town|durban|pretoria|"
    r"new zealand|auckland|israel|tel aviv|jerusalem|"
    r"costa rica|guatemala|ecuador|uruguay|paraguay|bolivia|"
    r"venezuela|dominican republic|honduras|el salvador|nicaragua|"
    r"puerto vallarta|guadalajara|monterrey|tijuana|queretaro|"
    r"bogota|medellin|lima peru|sao paulo|rio de janeiro|"
    r"emea|apac|latam)\b", re.I)

# Cities that name both a foreign metro and a US town (Cairo IL, Athens GA,
# Moscow ID...). Non-US ONLY when the location carries no US marker.
AMBIGUOUS_CITY = re.compile(r"\b(cairo|athens|moscow|lima|dublin|london|"
                            r"manchester|birmingham|naples|odessa|versailles|"
                            r"china|greece|italy|panama city|belgrade|warsaw|"
                            r"aberdeen|wellington|glasgow|bristol|oxford|"
                            r"amsterdam|vienna|berlin|geneva|paris|rome|milan|"
                            r"florence|hamburg|lisbon|madrid|prague|toledo|"
                            r"stockholm|belfast|sofia|st petersburg)\b",
                            re.I)
US_MARKER = re.compile(
    r"\b(united states|u\.?s\.?a?|remote|"
    r"al|ak|az|ar|ca|co|ct|de|fl|ga|hi|id|il|in|ia|ks|ky|la|me|md|ma|mi|mn|"
    r"ms|mo|mt|ne|nv|nh|nj|nm|ny|nc|nd|oh|ok|or|pa|ri|sc|sd|tn|tx|ut|vt|va|"
    r"wa|wv|wi|wy|dc|"
    r"alabama|alaska|arizona|arkansas|california|colorado|connecticut|"
    r"delaware|florida|georgia|hawaii|idaho|illinois|indiana|iowa|kansas|"
    r"kentucky|louisiana|maine|maryland|massachusetts|michigan|minnesota|"
    r"mississippi|missouri|montana|nebraska|nevada|ohio|oklahoma|oregon|"
    r"pennsylvania|tennessee|texas|utah|vermont|virginia|washington|"
    r"wisconsin|wyoming)\b", re.I)

COMP_RE = re.compile(
    r"(?:salary|pay|compensation|range|rate)[^.\n]{0,80}?"
    r"(\$[\d,]+(?:\.\d+)?(?:\s*[-–to]+\s*\$?[\d,]+(?:\.\d+)?)?"
    r"(?:\s*(?:/|per\s*)?(?:year|yr|hour|hr|annum|annually|hourly))?"
    r"[^.\n]{0,120}?(?:bonus|equity)?[^.\n]{0,40})", re.I)
# The dash class must cover em-dash and minus, and the separator must tolerate
# newlines: Airbnb renders its range as "Pay Range\n$168,000\n—\n$206,000 USD",
# which the hyphen/en-dash-only pattern missed entirely on 2026-08-10 — the card
# said "Not listed" while the posting stated a range.
DOLLAR_RANGE_RE = re.compile(
    r"\$[\d,]{4,}(?:\.\d+)?\s*(?:[-–—−]|to)\s*\$?[\d,]{4,}(?:\.\d+)?"
    r"(?:\s*(?:/|per\s*)?(?:year|yr|hour|hr|annum|annually|hourly))?"
    r"(?:\s*usd)?", re.I)
# Amazon states pay with NO dollar sign, one line per metro, at the end of
# preferred_qualifications:
#     USA, NY, New York - 104,900.00 - 179,500.00 USD annually
#     USA, TX, Irving - 95,400.00 - 163,200.00 USD annually
# Every $-anchored pattern above is blind to that, which is why those cards read
# "Not listed" while the posting plainly showed a range (owner caught it
# 2026-08-11). Matched per LINE so the quote keeps the employer's own metro
# label, and the New York line is preferred when several are listed — choosing
# between stated lines, never composing a figure.
PLAIN_USD_RANGE_RE = re.compile(
    r"[\d,]{5,}(?:\.\d{2})?\s*(?:[-–—−]|to)\s*[\d,]{5,}(?:\.\d{2})?\s*USD", re.I)
NY_LINE_RE = re.compile(r"(new york|,\s*ny\b|\bny\s*[-,])", re.I)
SALARY_NUM_RE = re.compile(r"\$?([\d,]+(?:\.\d+)?)\s*([kK])?")

# Bonus/equity are shown separately from base per the owner's spec, so we look
# for whether the posting MENTIONS them — never for a number to add up.
BONUS_RE = re.compile(r"\b(annual bonus|bonus target|target bonus|incentive plan|"
                      r"annual incentive|performance bonus|variable pay|"
                      r"short-term incentive|sti\b)", re.I)
EQUITY_RE = re.compile(r"\b(equity|rsu|rsus|restricted stock|stock options|"
                       r"stock award|long-term incentive|lti\b|espp)", re.I)

# "Senior Finance Manager" / "Sr. Director, FP&A" carry their level across a
# word, so plain substring matching on "senior manager" misses them.
SENIOR_MGR_RE = re.compile(r"\b(?:senior|sr\.?)\b[^,;|]{0,24}\bmanager\b", re.I)
SENIOR_DIR_RE = re.compile(r"\b(?:senior|sr\.?)\b[^,;|]{0,24}\bdirector\b", re.I)

LEVEL_RANK = {"cfo": 8, "svp": 7, "vp": 6, "senior_director": 5,
              "director": 4, "senior_manager": 3, "manager": 2}
LEVEL_LABEL = {"cfo": "CFO", "svp": "SVP", "vp": "VP", "senior_director": "Senior Director",
               "director": "Director", "senior_manager": "Senior Manager",
               "manager": "Manager"}
# How much of the seniority component each level earns. Director/Senior
# Director sit at the top because they are the owner's stated target; VP is not
# scored higher than Director since an under-qualified VP application is worth
# less than a well-matched Director one. SVP/CFO are damped for the same
# reason they are not the goal — see the spec's "don't recommend an SVP Client
# Finance role simply because the title is senior".
LEVEL_WEIGHT = {"cfo": 0.70, "svp": 0.80, "vp": 0.95, "senior_director": 1.0,
                "director": 1.0, "senior_manager": 0.75, "manager": 0.55}
SEVERITY_ORDER = {"green": 0, "yellow": 1, "red": 2}


def _words(text):
    return (text or "").casefold()


def _hit(term, text):
    """Substring match, but word-anchored for short/ambiguous tokens so 'sql'
    doesn't fire inside 'nosql-ish' prose and 'lead' doesn't match 'leadership'."""
    t = term.casefold()
    if len(t) <= 4 or " " not in t:
        return re.search(rf"(?<![\w&]){re.escape(t)}(?![\w&])", text) is not None
    return t in text


# ---------------------------------------------------------------- scope ----

def is_non_us(location):
    if not location:
        return False
    if NON_US.search(location):
        return True
    return bool(AMBIGUOUS_CITY.search(location)
                and not US_MARKER.search(location))


def location_scope(location, cities):
    """nyc | nyc_metro | remote | unknown | other.

    "unknown" is in scope on purpose: Workday and Google publish "4 Locations"
    for reqs that often include New York, and dropping those would silently
    lose real jobs. Only a location that clearly names somewhere else is out.
    """
    if not location:
        return "unknown"
    low = location.casefold()
    for m in cities["metros"]:
        if any(term in low for term in m["match"]):
            return "nyc" if m["rank"] == 1 else "nyc_metro"
    if any(re.search(p, low, re.I) for p in cities.get("remote_patterns", [])):
        if any(re.search(p, low, re.I)
               for p in cities.get("remote_excluded_patterns", [])):
            return "other"
        return "remote"
    # fullmatch, not search: "Nashville, TN, United States" is Tennessee, not an
    # unspecified US location. Searching for 'united states' inside the string
    # put out-of-scope roles on the board on 2026-08-10.
    if any(re.fullmatch(p, low.strip(), re.I)
           for p in cities.get("unknown_patterns", [])):
        return "unknown"
    return "other"


def is_remote(location, description, cities):
    """Stated remote only — never inferred. Checks the location field first,
    then the description, because Workday often says "New York, NY" in the
    location and "this role is remote-eligible" in the body."""
    excl = cities.get("remote_excluded_patterns", [])
    body_pats = cities.get("remote_body_patterns") or cities.get("remote_patterns", [])
    # Loose wording is fine in the location FIELD ("Remote - US"), but a long
    # description needs an explicit statement that the role itself is remote,
    # or "our remote-first culture" would qualify every posting at the company.
    for text, pats in ((location, cities.get("remote_patterns", [])),
                       (description, body_pats)):
        low = _words(text)
        if not low:
            continue
        if any(re.search(rf"\b{p}\b", low, re.I) for p in pats):
            if any(re.search(pe, low, re.I) for pe in excl):
                return False
            return True
    return False


def city_rank(location, cities):
    if not location:
        return cities["other_us_rank"]
    low = location.casefold()
    for m in cities["metros"]:
        if any(term in low for term in m["match"]):
            return m["rank"]
    if any(re.search(p, low, re.I) for p in cities.get("remote_patterns", [])):
        return cities["remote_rank"]
    return cities["other_us_rank"]


def blocklisted(company, title, bl):
    c = _words(company)
    for b in bl.get("companies", []):
        if b.casefold() in c:
            return f"blocklisted company: {b}"
    t = _words(title)
    for p in bl.get("title_patterns", []):
        if p.casefold() in t:
            return f"title pattern: {p}"
    return None


# ------------------------------------------------------------------ comp ----

def extract_stated_comp(description):
    """The posting's own compensation text, quoted. Internal whitespace is
    collapsed so a range split across newlines reads as one line; no word is
    changed, added or inferred."""
    if not description:
        return None
    for pattern in (COMP_RE, DOLLAR_RANGE_RE):
        m = pattern.search(description)
        if m:
            return re.sub(r"\s+", " ", m.group(0)).strip()
    return _plain_usd_line(description)


def _plain_usd_line(description):
    """Quote a no-dollar-sign "… - 104,900.00 - 179,500.00 USD annually" line.

    Whole lines are returned so the metro label travels with the numbers, and
    the New York line wins when a posting lists several. A line long enough to
    be prose rather than a pay row falls back to just the matched range, so a
    stray sentence can never be presented as the comp field.
    """
    lines = [re.sub(r"\s+", " ", ln).strip()
             for ln in description.splitlines()
             if PLAIN_USD_RANGE_RE.search(ln)]
    if not lines:
        return None
    chosen = next((ln for ln in lines if NY_LINE_RE.search(ln)), lines[0])
    if len(chosen) > 110:
        return PLAIN_USD_RANGE_RE.search(chosen).group(0).strip()
    return chosen


def comp_is_multi_range(description):
    """True when the posting states SEVERAL pay ranges (Accenture lists one per
    metro: California $122,700 to $317,200, Cleveland ..., New York ...).

    We quote the first one, which on its own is misleading — the reader can't
    tell it isn't the New York range. Rather than guess which range applies,
    the card carries a note pointing at the posting. Derived flag, not a comp
    value, so rule 1 holds.
    """
    if not description:
        return False
    found = {re.sub(r"\s+", " ", m.group(0)).strip()
             for m in DOLLAR_RANGE_RE.finditer(description)}
    found |= {re.sub(r"\s+", " ", m.group(0)).strip()
              for m in PLAIN_USD_RANGE_RE.finditer(description)}
    if len(found) <= 1:
        return False
    # Several ranges, but if the one we quoted names New York the reader is not
    # being misled and the warning would just be noise. Amazon's two-line format
    # is exactly this case.
    chosen = extract_stated_comp(description)
    return not (chosen and NY_LINE_RE.search(chosen))


def comp_sort_value(comp):
    """Numeric value for ORDERING and banding only — display always shows the
    verbatim string. Returns the LARGEST figure in the text, i.e. the top of a
    stated range, which is why the score bands below are generous rather than
    treating it as a base salary."""
    if not comp:
        return -1.0
    nums = []
    for num, suffix in SALARY_NUM_RE.findall(comp):
        raw = num.replace(",", "")
        if not raw.replace(".", "").isdigit():
            continue
        n = float(raw)
        if suffix:      # "$141K" means 141,000 — not 141
            n *= 1000
        elif n < 20:    # ignore stray small numbers
            continue
        nums.append(n)
    if not nums:
        return -1.0
    v = max(nums)
    if v < 1000:  # stated hourly rate; annualize for ordering only
        v *= 2080
    return v


# Postings that SAY they state a range without the number being machine-readable.
# Amazon is the case that forced this (2026-08-11): the pay block is rendered
# client-side by a component behind an auth-token call, so the number is absent
# from the search API, from the page HTML, and from every candidate JSON
# endpoint — verified from two networks. The description still carries the
# sentence, so we can tell the reader "the employer posted a range, go look"
# instead of "Compensation not listed", which would be actively misleading.
# This never invents a figure; rule 1 is intact.
COMP_OFFSITE_RE = re.compile(
    r"((base\s+)?(salary|pay|compensation)\s+range[^.\n]{0,60}"
    r"(is\s+)?(listed|shown|provided|posted)\s+below"
    r"|range\s+for\s+this\s+(position|role)[^.\n]{0,40}below"
    r"|compensation\s+reflects\s+the\s+cost\s+of\s+labor)", re.I)


def comp_stated_offsite(description):
    """True when the posting says a range is published but we can't read it."""
    return bool(description and COMP_OFFSITE_RE.search(description))


def comp_extras(description):
    """Whether the posting MENTIONS bonus / equity. Presence only — no amount
    is read or estimated, so the card can show them as separate stated facts."""
    d = description or ""
    return {"bonus": bool(BONUS_RE.search(d)), "equity": bool(EQUITY_RE.search(d))}


# ------------------------------------------------------------- seniority ----

def seniority_level(title, kw):
    """Level key, or None when the title is below the floor.

    Company leveling beats title wording (owner directive), so a bare
    "Manager" is never rejected here — it is scored, and Tier A employers get
    a lift in `fit_score`. Titles with no level word at all fall back to
    `seniority.unknown_as` rather than being dropped, because at Tier A
    companies the leveling often lives in the body, not the title.
    """
    cfg = kw["seniority"]
    t = _words(title)
    if not t:
        return cfg.get("unknown_as", "manager")
    if SENIOR_DIR_RE.search(t):
        return "senior_director"
    if SENIOR_MGR_RE.search(t):
        return "senior_manager"
    for level, terms in cfg["levels"].items():
        if any(_hit(term, t) for term in terms):
            return level
    for term in cfg.get("below_floor", []):
        if _hit(term, t):
            return None
    return cfg.get("unknown_as", "manager")


def level_is_stated(title, kw):
    """Did the TITLE actually name a level, or did we fall back to the default?

    Matters for display, not for scoring: Airbnb's "Principal, Strategic
    Finance" and Stripe's "Finance and Strategy Partner" name no level, so the
    fallback scores them as manager — but rendering a "Manager" badge on them
    states something the employer didn't, and understates both roles. The card
    shows "level not stated" instead.
    """
    cfg = kw["seniority"]
    t = _words(title)
    if not t:
        return False
    if SENIOR_DIR_RE.search(t) or SENIOR_MGR_RE.search(t):
        return True
    return any(_hit(term, t)
               for terms in cfg["levels"].values() for term in terms)


def excluded(title, kw):
    """Reason this title is out of scope, or None. Title-only by design: the
    body of a good FP&A role often mentions accounting or revenue recognition
    in passing, and disqualifying on that would gut the board."""
    t = _words(title)
    for term in kw["exclude"].get("title_terms", []):
        if _hit(term, t):
            return f"excluded title term: {term}"
    return None


# -------------------------------------------------------------- function ----

def function_hits(title, body, kw):
    """Which of the qualifying planning/analysis terms the posting uses."""
    text = f"{_words(title)}\n{_words(body)}"
    return [t for t in kw["require"]["terms"] if _hit(t, text)]


def title_finance_hits(title, kw):
    """Whether the TITLE places the role in finance.

    Necessary because sales and marketing postings are full of forecasting,
    KPIs, P&L and business partnering: on the first live run the planning-term
    gate alone admitted "Manager, Mid-Market Sales" and "Marketing Operations
    Lead". Checked on the title only — a finance role announces itself there.
    """
    t = _words(title)
    return [x for x in kw["require"].get("title_terms", []) if _hit(x, t)]


def function_areas(title, body, roles):
    """Distinct FP&A capability areas the posting covers (keys of
    roles.functions). Breadth across areas is what the transition score
    rewards — nine mentions of forecasting is still one area."""
    text = f"{_words(title)}\n{_words(body)}"
    out = []
    for key, spec in (roles.get("functions") or {}).items():
        if any(_hit(t, text) for t in spec.get("terms", [])):
            out.append(key)
    return out


def transferable_hits(title, body, roles):
    """Which parts of the owner's existing experience the posting asks for."""
    text = f"{_words(title)}\n{_words(body)}"
    return [k for k, terms in (roles.get("transferable") or {}).items()
            if any(_hit(t, text) for t in terms)]


def demote_hits(title, body, kw):
    """Agency/client-finance signals — the posting leaning back toward what the
    owner already does. Not disqualifying, but it pulls the transition score
    down, which is the whole point of that score."""
    text = f"{_words(title)}\n{_words(body)}"
    return [t for t in kw["exclude"].get("body_demote", []) if _hit(t, text)]


def gap_flags(title, body, roles):
    """Requirements the owner does not clearly have.

    `gap_min_hits` guards against one incidental mention creating a scary red
    flag: SQL named once in a "nice to have" list is not a SQL-first analytics
    role. Returns dicts so the UI can show label + severity together.
    """
    text = f"{_words(title)}\n{_words(body)}"
    mins = roles.get("gap_min_hits") or {}
    out = []
    for key, spec in (roles.get("gaps") or {}).items():
        hits = sum(1 for t in spec.get("terms", []) if _hit(t, text))
        sev = spec.get("severity", "yellow")
        if hits >= mins.get(sev, 1):
            out.append({"key": key, "label": spec.get("label", key),
                        "severity": sev, "hits": hits})
    out.sort(key=lambda g: -SEVERITY_ORDER.get(g["severity"], 1))
    return out


def worst_severity(gaps):
    if not gaps:
        return "green"
    return max((g["severity"] for g in gaps),
               key=lambda s: SEVERITY_ORDER.get(s, 1))


# ------------------------------------------------------------ qualifying ----

def qualifies(title, body, location, kw, cities):
    """(ok, reason_when_not). The three gates from keywords.yaml's header.
    Comp is deliberately NOT a gate — an otherwise strong role with no posted
    salary must still appear (owner's spec)."""
    reason = excluded(title, kw)
    if reason:
        return False, reason
    if is_non_us(location):
        return False, "outside US scope"
    scope = location_scope(location, cities)
    if scope == "other" and not is_remote(location, body, cities):
        # A posting whose LOCATION field names another city can still be
        # remote-eligible — big tech routinely lists a home office on a role
        # open to US-remote, and the owner said remote is acceptable. Dropping
        # on the location field alone was silently discarding those, and
        # location was the second-largest filter bucket (3,477 in one run).
        # The body still has to SAY remote; nothing is inferred from the field.
        return False, f"outside NYC/remote scope: {location}"
    if seniority_level(title, kw) is None:
        return False, "below seniority floor"
    if len(title_finance_hits(title, kw)) < kw["require"].get("min_title_hits", 1):
        return False, "title is not a finance role"
    hits = function_hits(title, body, kw)
    if len(hits) < kw["require"].get("min_hits", 2):
        return False, f"only {len(hits)} planning/analysis signal(s)"
    return True, None


# --------------------------------------------------------------- scoring ----

def pivot_score(areas, demotes, roles):
    """FP&A Transition Score, 1-10: how much this role would EXPAND the resume.

    10 = broad corporate FP&A / P&L / planning-cycle ownership.
    1  = effectively another client-finance, billing or revenue-rec seat.
    Core areas count 1.5 because breadth into planning and P&L is the point;
    each agency-side signal costs half a point.
    """
    core = {"corporate_fpna", "planning_cycle", "pl_ownership", "opex_headcount",
            "strategic_finance", "business_unit_finance"}
    weighted = sum(1.5 if a in core else 1.0 for a in areas)
    ceiling = 7.5
    raw = 1.0 + 9.0 * min(weighted, ceiling) / ceiling
    raw -= 0.5 * len(demotes)
    return int(max(1, min(10, round(raw))))


def _comp_component(comp, kw, weight):
    """Unknown scores neutral (half), never zero: the owner's spec says an
    unpriced strong role stays on the board, so it must not be scored as if it
    paid badly."""
    v = comp_sort_value(comp)
    cfg = kw.get("comp") or {}
    target = cfg.get("target_base", 190000)
    floor = cfg.get("hard_floor", 150000)
    if v < 0:
        return weight * 0.5
    if v >= 250000:
        return weight
    if v >= 200000:
        return weight * 0.85
    if v >= target:
        return weight * 0.65
    if v >= floor:
        return weight * 0.30
    return weight * 0.10


def fit_score(*, title, body, comp, location, level, tier, areas, transferables,
              pivot, kw, roles, cities):
    w = roles["weights"]
    n_transfer = len(transferables)
    score = min(n_transfer, 6) / 6.0 * w["transferability"]
    score += pivot / 10.0 * w["fpna_opportunity"]
    score += _comp_component(comp, kw, w["compensation"])

    lw = LEVEL_WEIGHT.get(level, 0.55)
    # Owner directive: a Tier A company calling this level "Manager" is not a
    # demotion. Lift Manager/Senior Manager at Tier A rather than ranking them
    # by title wording.
    if tier == "A" and level in ("manager", "senior_manager"):
        lw = min(1.0, lw + 0.20)
    score += lw * w["seniority"]

    scope = location_scope(location, cities)
    loc_w = {"nyc": 1.0, "nyc_metro": 0.9, "remote": 0.8,
             "unknown": 0.5, "other": 0.0}.get(scope, 0.5)
    score += loc_w * w["location"]
    return int(round(score))


def recommendation(fit, pivot, severity, roles):
    b = roles["bands"]
    if fit >= 85 and pivot >= 7 and severity != "red":
        return "Strong Apply"
    if fit >= b["best"]:
        return "Apply"
    if fit >= b["stretch"]:
        return "Stretch Apply"
    return "Skip"


def score_job(job, kw, roles, cities, tier=None):
    """Compute every derived field for one stored job, in place.

    Called for the WHOLE store every run (not just today's fetch) so that
    tuning roles.yaml reaches jobs already stored — the same reasoning as the
    role classifier in unifier-jobs.
    """
    title, body = job.get("title"), job.get("description")
    areas = function_areas(title, body, roles)
    transferables = transferable_hits(title, body, roles)
    demotes = demote_hits(title, body, kw)
    gaps = gap_flags(title, body, roles)
    level = seniority_level(title, kw) or "manager"
    pivot = pivot_score(areas, demotes, roles)
    fit = fit_score(title=title, body=body, comp=job.get("comp"),
                    location=job.get("location"), level=level, tier=tier,
                    areas=areas, transferables=transferables, pivot=pivot,
                    kw=kw, roles=roles, cities=cities)
    severity = worst_severity(gaps)
    job["areas"] = areas
    job["transferables"] = transferables
    job["demotes"] = demotes
    job["gaps"] = gaps
    job["gap_severity"] = severity
    job["level"] = level
    job["level_stated"] = level_is_stated(title, kw)
    job["level_label"] = (LEVEL_LABEL.get(level, level) if job["level_stated"]
                          else None)
    job["pivot"] = pivot
    job["fit"] = fit
    job["recommendation"] = recommendation(fit, pivot, severity, roles)
    job["scope"] = location_scope(job.get("location"), cities)
    job["remote"] = is_remote(job.get("location"), body, cities)
    if job["scope"] == "other" and job["remote"]:
        # It cleared the gate on stated remote eligibility, so it must score as
        # remote too — leaving it "other" would zero the location component of
        # a role we deliberately kept.
        job["scope"] = "remote"
    job["extras"] = comp_extras(body)
    job["comp_offsite"] = (not job.get("comp")) and comp_stated_offsite(body)
    # The page-derived flag has to survive here: when comp came from the
    # employer's posting page, `body` (the ATS description) has no range in it
    # at all, so recomputing from body alone would silently clear the warning.
    job["comp_multi"] = comp_is_multi_range(body) or bool(job.get("comp_multi_page"))
    job["below_comp"] = 0 <= comp_sort_value(job.get("comp")) < (
        kw.get("comp") or {}).get("hard_floor", 150000)
    return job


# ------------------------------------------------------------- narrative ----
# Template sentences assembled from the DERIVED term hits above. Deliberately
# not prose-generated: the same posting must read the same way on every run,
# and every clause has to be traceable to a term the posting actually uses.

def narrative(job, roles):
    fn = roles.get("functions") or {}
    tr_labels = {
        "revenue_forecasting": "revenue forecasting", "variance": "variance analysis",
        "scenario": "scenario modeling", "margin": "margin and profitability analysis",
        "reporting": "financial reporting", "exec": "executive/CFO reporting",
        "modeling": "financial modeling", "budgeting": "annual budgeting",
        "headcount": "staffing and headcount analysis", "pricing": "pricing models",
        "systems": "finance systems (SAP / Hyperion / Dynamics)",
        "leadership": "leading a finance team", "close": "close and working capital",
    }
    have = [tr_labels.get(k, k) for k in job.get("transferables", [])]
    areas = [fn.get(k, {}).get("label", k) for k in job.get("areas", [])]
    core = {"corporate_fpna", "planning_cycle", "pl_ownership", "opex_headcount",
            "strategic_finance", "business_unit_finance"}
    new_areas = [fn.get(k, {}).get("label", k)
                 for k in job.get("areas", []) if k in core]

    why = ("The posting asks for " + ", ".join(have[:5]) + "."
           if have else "No direct overlap with the profile's stated experience "
                        "was detected in the posting text.")
    learn = ("Would add " + ", ".join(new_areas) + " to the resume."
             if new_areas else
             "No new core FP&A area detected — this looks adjacent to existing "
             "experience rather than an expansion.")
    if job.get("demotes"):
        learn += (" Note: the posting also mentions "
                  + ", ".join(job["demotes"][:3])
                  + ", which overlaps existing client-finance work.")
    gaps = job.get("gaps") or []
    gap_text = ("; ".join(f"{g['label']} ({g['severity'].upper()})" for g in gaps)
                if gaps else "No stated requirement outside the profile.")

    pivot = job.get("pivot", 1)
    if pivot >= 8:
        value = ("High: broad planning and P&L exposure here is the kind of scope "
                 "that reads as Director-level FP&A on a future application.")
    elif pivot >= 5:
        value = ("Moderate: adds real FP&A surface area, but not full corporate "
                 "planning ownership.")
    else:
        value = ("Low: mostly repeats existing commercial/client finance scope — "
                 "would not materially change the resume.")
    return {"why": why, "learn": learn, "gaps": gap_text, "value": value,
            "areas": areas}
