"""Static dashboard generator -> docs/index.html (served by GitHub Pages).

Card layout, not a spreadsheet: the source spec asked for eighteen columns,
which is unreadable on a phone and this board is shared by link.

Layout priorities, in order: (1) the job title is what you scan for, so it is
the loudest thing on the card — not the company; (2) fit and pivot are why this
board exists, so they sit in a fixed score column at a size you can read at a
glance rather than buried in a footnote; (3) everything else is support and is
sized accordingly.

Every factual value is the source's verbatim text and absent fields say
"Not listed". The scores, level, gap flags and recommendation are DERIVED and
say so on hover and in the About panel.
"""
import html
import re
from pathlib import Path

from .filters import city_rank, comp_sort_value
from .models import norm

DOCS = Path(__file__).resolve().parent.parent / "docs"
TIER_ORDER = {"A": 0, "B": 1, "C": 2}
CAT_LABEL = {"bigtech": "Big Tech", "tech": "Tech", "advertising": "Advertising"}
SEV_LABEL = {"green": "GREEN", "yellow": "YELLOW", "red": "RED"}
REC_CLASS = {"Strong Apply": "rec-strong", "Apply": "rec-apply",
             "Stretch Apply": "rec-stretch", "Skip": "rec-skip"}

CSS = """
:root{
  --bg:#f6f6f4; --card:#fff; --text:#16181c; --muted:#6b7280; --faint:#9aa0aa;
  --line:#e4e4e0; --line-soft:#eeeeea; --accent:#0b4a86; --accent-soft:#eaf2fb;
  --good:#127c4f; --good-soft:#e6f4ec; --warn:#8a5a00; --warn-soft:#fdf3d9;
  --bad:#a02c2c; --bad-soft:#fbeaea; --star:#7a5200; --star-soft:#fbf0d2;
  --shadow:0 1px 2px rgba(16,24,40,.04),0 1px 3px rgba(16,24,40,.06);
}
@media(prefers-color-scheme:dark){:root{
  --bg:#141416; --card:#1e1f22; --text:#eceef1; --muted:#9ba1ab; --faint:#767c86;
  --line:#32343a; --line-soft:#2a2c31; --accent:#7fb4ec; --accent-soft:#152a41;
  --good:#5fc78f; --good-soft:#123024; --warn:#e0b44c; --warn-soft:#332608;
  --bad:#ef8b8b; --bad-soft:#3a1c1c; --star:#efc76a; --star-soft:#332608;
  --shadow:none;
}}
*{box-sizing:border-box}
body{margin:0;padding:20px 16px 48px;background:var(--bg);color:var(--text);
  font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif;
  -webkit-font-smoothing:antialiased}
main{max-width:880px;margin:0 auto}
a{color:var(--accent)}

/* ---- header ---- */
header{margin-bottom:22px}
h1{font-size:21px;line-height:1.25;letter-spacing:-.01em;margin:0 0 8px;
  font-weight:650}
.stats{display:flex;flex-wrap:wrap;gap:6px 14px;align-items:baseline;
  font-size:13px;color:var(--muted)}
.stats b{color:var(--text);font-weight:600}
.ghost{font:inherit;background:none;border:1px solid var(--line);
  border-radius:999px;color:var(--muted);cursor:pointer;padding:2px 10px}
.ghost:hover{color:var(--text);border-color:var(--muted)}
.warn-box{margin:14px 0 0;padding:10px 13px;border-radius:8px;font-size:13px;
  background:var(--warn-soft);color:var(--warn);border:1px solid transparent}

/* ---- sections ---- */
section{margin-top:30px}
h2{font-size:13px;font-weight:650;letter-spacing:.05em;text-transform:uppercase;
  color:var(--muted);margin:0 0 4px;padding-bottom:8px;
  border-bottom:1px solid var(--line)}
h2 .n{color:var(--faint);font-weight:500}
.hint{font-size:13px;color:var(--muted);margin:10px 0 14px;max-width:62ch}
details.fold{margin-top:8px}
details.fold>summary{font-size:13px;font-weight:650;letter-spacing:.05em;
  text-transform:uppercase;color:var(--muted);cursor:pointer;padding-bottom:8px;
  border-bottom:1px solid var(--line);list-style:none}
details.fold>summary::-webkit-details-marker{display:none}
details.fold>summary::before{content:"▸ ";color:var(--faint)}
details.fold[open]>summary::before{content:"▾ "}
details.fold>summary:hover{color:var(--text)}

/* ---- card ---- */
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;
  padding:16px 18px;margin-top:12px;box-shadow:var(--shadow)}
.card.applied{opacity:.6}
.top{display:flex;gap:18px;align-items:flex-start}
.body{min-width:0;flex:1}
.title{font-size:16.5px;font-weight:620;line-height:1.3;margin:0 0 4px;
  letter-spacing:-.005em}
.title a{text-decoration:none}
.title a:hover{text-decoration:underline}
.org{font-size:14px;color:var(--text);margin-bottom:9px}
.org .co{font-weight:600}
.org .sep{color:var(--faint);margin:0 6px}
.org .loc{color:var(--muted)}
.tags{display:flex;flex-wrap:wrap;gap:5px;margin-bottom:10px}
.tag{font-size:11px;font-weight:600;letter-spacing:.02em;border-radius:5px;
  padding:2px 7px;background:var(--accent-soft);color:var(--accent);
  white-space:nowrap}
.tag.q{background:transparent;color:var(--muted);border:1px solid var(--line);
  font-weight:500}
.tag.star{background:var(--star-soft);color:var(--star)}
.tag.new{background:var(--good-soft);color:var(--good)}
.pay{font-size:14px;margin-bottom:3px}
.pay b{font-weight:620}
.pay .none{color:var(--faint);font-weight:400}
.pay .sub{color:var(--muted);font-size:13px}
.when{font-size:12.5px;color:var(--faint)}

/* ---- score column ---- */
.score{flex:0 0 96px;text-align:right;display:flex;flex-direction:column;
  align-items:flex-end;gap:5px}
.fit{display:flex;align-items:baseline;gap:4px;line-height:1}
.fit b{font-size:29px;font-weight:640;letter-spacing:-.02em}
.fit span{font-size:11px;color:var(--faint);text-transform:uppercase;
  letter-spacing:.06em}
.f-hi b{color:var(--good)}.f-mid b{color:var(--accent)}
.f-low b{color:var(--warn)}.f-min b{color:var(--faint)}
.pivot{font-size:12.5px;color:var(--muted);white-space:nowrap}
.pivot b{color:var(--text);font-weight:620}
.rec{font-size:11px;font-weight:650;border-radius:999px;padding:2px 9px;
  white-space:nowrap}
.rec-strong{background:var(--good-soft);color:var(--good)}
.rec-apply{background:var(--accent-soft);color:var(--accent)}
.rec-stretch{background:var(--warn-soft);color:var(--warn)}
.rec-skip{background:var(--line-soft);color:var(--muted)}
.gap{font-size:11.5px;white-space:nowrap;color:var(--muted)}
.gap .g-green{color:var(--good)}.gap .g-yellow{color:var(--warn)}
.gap .g-red{color:var(--bad)}

/* ---- card footer ---- */
.foot{display:flex;flex-wrap:wrap;gap:8px 16px;align-items:center;
  margin-top:13px;padding-top:11px;border-top:1px solid var(--line-soft);
  font-size:12.5px}
.foot details{display:inline}
.foot summary{cursor:pointer;color:var(--muted);list-style:none;
  display:inline-block}
.foot summary::-webkit-details-marker{display:none}
.foot summary:hover{color:var(--text)}
.foot .spacer{flex:1}
.act{font:inherit;font-size:12.5px;background:none;border:1px solid var(--line);
  border-radius:999px;color:var(--muted);cursor:pointer;padding:2px 10px}
.act:hover{color:var(--text);border-color:var(--muted)}
.panel{flex-basis:100%;margin:0}
.analysis{font-size:13.5px;line-height:1.6;margin:10px 0 0;
  padding:12px 14px;background:var(--bg);border-radius:8px}
.analysis p{margin:0 0 7px}.analysis p:last-child{margin:0}
.analysis .lbl{font-weight:650;color:var(--text)}
.analysis .lbl+span{color:var(--muted)}
pre.desc{white-space:pre-wrap;font:13px/1.6 inherit;color:var(--muted);
  max-height:340px;overflow-y:auto;margin:10px 0 0;padding:12px 14px;
  background:var(--bg);border-radius:8px}

/* ---- gone / roster / about ---- */
.gone .title a{color:var(--faint)}
.gone .org .co{color:var(--muted)}
.roster{font-size:13px;line-height:1.9}
.roster b{font-size:11px;text-transform:uppercase;letter-spacing:.05em;
  color:var(--muted);font-weight:650}
.on{color:var(--text)}
.off{color:var(--faint);text-decoration:underline dotted;
  text-underline-offset:3px;cursor:help}
.about{font-size:13px;line-height:1.65;color:var(--muted);max-width:70ch}
.about p{margin:0 0 9px}
.about b{color:var(--text);font-weight:620}
footer{margin-top:34px;padding-top:16px;border-top:1px solid var(--line)}

@media(max-width:620px){
  body{padding:16px 12px 40px}
  .card{padding:14px}
  .top{flex-direction:column-reverse;gap:10px}
  .score{flex-direction:row;align-items:center;flex-wrap:wrap;gap:8px;
    text-align:left;flex-basis:auto;width:100%}
  .fit b{font-size:24px}
  h1{font-size:19px}
}
"""

# Applied / hidden ticks live only in the viewer's browser: this is a public
# repo shared by link, so one person's tracking must never be committed or
# visible to anyone else. Per-device by design — stated in the About panel so a
# tick that doesn't follow you to your phone isn't a surprise. Job ids hash
# company|title|location, so a tick survives the daily re-fetch.
JS = """
(function(){
  var AK='fpna-applied-v1', HK='fpna-hidden-v1';
  function load(k){try{return JSON.parse(localStorage.getItem(k))||{}}catch(e){return {}}}
  function save(k,v){try{localStorage.setItem(k,JSON.stringify(v))}catch(e){}}
  var applied=load(AK), hidden=load(HK);
  function paint(){
    var nh=0;
    document.querySelectorAll('.card[data-id]').forEach(function(c){
      var id=c.getAttribute('data-id');
      if(hidden[id]){c.style.display='none';nh++;return}
      c.style.display='';
      var on=!!applied[id];
      c.classList.toggle('applied',on);
      var b=c.querySelector('.applied-tag');
      if(b){b.textContent = on ? ('applied '+applied[id]) : '';
            b.style.display = on ? '' : 'none';}
      var btn=c.querySelector('.btn-applied');
      if(btn) btn.textContent = on ? 'undo applied' : 'mark applied';
    });
    var n=document.getElementById('hidden-note');
    if(n) n.textContent = nh ? (nh+' hidden on this device') : '';
    var r=document.getElementById('unhide');
    if(r) r.style.display = nh ? '' : 'none';
  }
  document.addEventListener('click',function(e){
    var t=e.target, card=t.closest ? t.closest('.card') : null;
    if(t.classList.contains('btn-applied') && card){
      var id=card.getAttribute('data-id');
      if(applied[id]) delete applied[id];
      else applied[id]=new Date().toISOString().slice(0,10);
      save(AK,applied); paint();
    } else if(t.classList.contains('btn-hide') && card){
      hidden[card.getAttribute('data-id')]=1; save(HK,hidden); paint();
    } else if(t.id==='unhide'){
      hidden={}; save(HK,hidden); paint();
    }
  });
  paint();
})();
"""


def esc(s):
    return html.escape(str(s)) if s else ""


def _posted(value):
    """Trim a machine timestamp to its date. Greenhouse returns
    "2026-03-26T15:58:01-04:00", which is the same fact as "2026-03-26" but
    reads like debug output next to Amazon's "July 30, 2026". Formatting only —
    human date strings are left exactly as the employer wrote them.
    """
    s = str(value or "")
    m = re.match(r"(\d{4}-\d{2}-\d{2})T", s)
    return m.group(1) if m else (s or None)


def _tags(j, prestige, roles):
    """Badges, ordered by how much they change a decision. Kept few and short:
    a five-badge pile on the company line was the worst part of the first
    layout, so tier and category are merged and the pivot badge is abbreviated
    with the full phrase on hover."""
    out = []
    if "new" in j["flags"]:
        out.append('<span class="tag new">new</span>')
    if (j.get("pivot", 0) >= roles["bands"]["pivot_star"]
            and j.get("fit", 0) >= roles["bands"]["best"]):
        out.append('<span class="tag star" title="HIGH-VALUE FP&amp;A PIVOT — of '
                   'everything on the board, this role would add the most new '
                   'corporate FP&amp;A scope">&#11088; top pivot</span>')
    brand = " · ".join(x for x in (f"Tier {prestige}" if prestige else None,
                                   CAT_LABEL.get(j.get("category"))) if x)
    if brand:
        out.append(f'<span class="tag q">{esc(brand)}</span>')
    if j.get("level_label"):
        out.append(f'<span class="tag q" title="seniority band derived from the '
                   f'title — not stated by the employer">'
                   f'{esc(j["level_label"])}</span>')
    elif j.get("level_stated") is False:
        out.append('<span class="tag q" title="the title names no level (e.g. '
                   '&quot;Principal, Strategic Finance&quot;) — scored as Manager, '
                   'but the real level may be higher; check the posting">'
                   'level not stated</span>')
    if j.get("remote"):
        out.append('<span class="tag q" title="the posting states remote '
                   'eligibility">remote</span>')
    if j.get("scope") == "unknown":
        out.append('<span class="tag q" title="the posting names no specific '
                   'city — kept because multi-location reqs often include New '
                   'York">city not stated</span>')
    if "long-posted" in j["flags"]:
        out.append('<span class="tag q" title="posted more than 90 days ago">'
                   'long-posted</span>')
    if "manual" in j["flags"]:
        out.append('<span class="tag q" title="added by hand from a direct link '
                   '— this employer blocks automated access">manual</span>')
    if j["kind"] == "board":
        out.append('<span class="tag q" title="found on an aggregator; the '
                   'employer\'s own posting is not resolved yet">board</span>')
    out.append('<span class="tag new applied-tag" style="display:none"></span>')
    return f'<div class="tags">{"".join(out)}</div>'


def _card(j, prestige, roles, narrate):
    fit = j.get("fit") or 0
    fit_cls = ("f-hi" if fit >= 85 else "f-mid" if fit >= 75
               else "f-low" if fit >= 60 else "f-min")
    sev = j.get("gap_severity", "green")
    rec = j.get("recommendation") or ""

    comp = j.get("comp")
    pay = (f"<b>{esc(comp)}</b>" if comp
           else '<span class="none">Compensation not listed</span>')
    extras = j.get("extras") or {}
    bits = []
    if extras.get("bonus"):
        bits.append("bonus mentioned")
    if extras.get("equity"):
        bits.append("equity/RSUs mentioned")
    if j.get("comp_multi"):
        bits.append("several location ranges stated — may not be the NY one")
    if bits:
        pay += f' <span class="sub">&middot; {esc(", ".join(bits))}</span>'

    when = f'Posted {esc(_posted(j.get("posted_date"))) or "date not listed"}'
    when += f' &middot; found {esc(j["first_seen"])}'
    if j["status"] == "gone":
        when += f' &middot; no longer listed as of {esc(j["gone_date"])}'

    n = narrate(j)
    analysis = (
        '<div class="analysis">'
        f'<p><span class="lbl">Why this matches:</span> <span>{esc(n["why"])}</span></p>'
        f'<p><span class="lbl">What it would add:</span> <span>{esc(n["learn"])}</span></p>'
        f'<p><span class="lbl">Gaps:</span> <span>{esc(n["gaps"])}</span></p>'
        f'<p><span class="lbl">Career value:</span> <span>{esc(n["value"])}</span></p>'
        + (f'<p><span class="lbl">FP&amp;A areas named in the posting:</span> '
           f'<span>{esc(", ".join(n["areas"]))}</span></p>' if n["areas"] else "")
        + '</div>')
    desc = ""
    if j.get("description"):
        desc = ('<details class="panel"><summary>Job description</summary>'
                f'<pre class="desc">{esc(j["description"])}</pre></details>')

    return f"""<article class="card{' gone' if j['status'] == 'gone' else ''}" data-id="{esc(j['id'])}">
<div class="top">
  <div class="body">
    <h3 class="title"><a href="{esc(j['url'])}" target="_blank" rel="noopener">{esc(j['title'])}</a></h3>
    <div class="org"><span class="co">{esc(j['company'])}</span><span class="sep">&middot;</span><span class="loc">{esc(j.get('location')) or 'Location not listed'}</span></div>
    {_tags(j, prestige, roles)}
    <div class="pay">{pay}</div>
    <div class="when">{when}</div>
  </div>
  <div class="score" title="Derived from the term lists in config/roles.yaml — not stated by the employer">
    <div class="fit {fit_cls}"><b>{fit}</b><span>fit</span></div>
    <div class="pivot">pivot <b>{j.get('pivot', 0)}</b>/10</div>
    <div class="rec {REC_CLASS.get(rec, 'rec-skip')}">{esc(rec)}</div>
    <div class="gap"><span class="g-{sev}">&#9679;</span> {SEV_LABEL.get(sev, sev)} gaps</div>
  </div>
</div>
<div class="foot">
  <details class="panel"><summary>Analysis</summary>{analysis}</details>
  {desc}
  <span class="spacer"></span>
  <button class="act btn-applied">mark applied</button>
  <button class="act btn-hide">hide</button>
</div>
</article>"""


def _triage_section(triage):
    """Postings the employer's own search matched, whose text we can't read.

    Meta is the case that forced this: its search returns titles with no
    description at all, and those titles are exactly the target roles
    ("Director, Corporate Finance", "Director, Infrastructure Finance"). They
    can't be scored without body text, but burying them in a JSON file while
    the dashboard shows ten jobs would be the worst outcome. Title and link are
    verbatim; nothing else is claimed.
    """
    rows = [t for t in (triage or []) if t.get("title") and t.get("url")]
    if not rows:
        return ""
    cards = []
    for t in rows:
        cards.append(
            '<article class="card"><div class="top"><div class="body">'
            f'<h3 class="title"><a href="{esc(t["url"])}" target="_blank" '
            f'rel="noopener">{esc(t["title"])}</a></h3>'
            f'<div class="org"><span class="co">{esc(t["company"])}</span>'
            f'<span class="sep">&middot;</span>'
            f'<span class="loc">Location not listed</span></div>'
            f'<div class="tags"><span class="tag q" '
            f'title="{esc(t.get("note"))}">not scoreable</span></div>'
            '<div class="pay"><span class="none">Compensation not listed</span></div>'
            f'<div class="when">Found {esc(t.get("first_seen"))}</div>'
            '</div></div></article>')
    return (f'<section><details class="fold"><summary>Worth a look &mdash; not '
            f'scoreable <span class="n">({len(rows)})</span></summary>'
            f'<p class="hint">These matched the employer\'s own finance search, '
            f'but the posting text isn\'t machine-readable, so there is no fit '
            f'score and no location or compensation to show. Open the link to '
            f'judge them. Mostly Meta, whose job search returns titles only.</p>'
            f'{"".join(cards)}</details></section>')


def generate(store, companies, cities, roles, warnings, today, triage=None):
    from .filters import narrative
    prestige = {norm(c["name"]): c["tier"] for c in companies}

    def p_of(j):
        return prestige.get(norm(j["company"]))

    def narrate(j):
        return narrative(j, roles)

    def sort_key(j):
        # Fit leads — this board exists to rank, not to list. Company tier
        # breaks ties (two equally-fitting roles: the better-paying brand
        # first), then stated comp, then how close the metro is.
        return (-(j.get("fit") or 0),
                TIER_ORDER.get(p_of(j), 3),
                -comp_sort_value(j.get("comp")),
                city_rank(j.get("location"), cities),
                norm(j["company"]))

    bands = roles["bands"]
    active = [j for j in store.values() if j["status"] == "active"]
    below = sorted((j for j in active if j.get("below_comp")), key=sort_key)
    rest = [j for j in active if not j.get("below_comp")]
    best = sorted((j for j in rest if (j.get("fit") or 0) >= bands["best"]),
                  key=sort_key)
    stretch = sorted((j for j in rest
                      if bands["stretch"] <= (j.get("fit") or 0) < bands["best"]),
                     key=sort_key)
    low = sorted((j for j in rest if (j.get("fit") or 0) < bands["stretch"]),
                 key=sort_key)
    gone = sorted((j for j in store.values() if j["status"] == "gone"),
                  key=lambda j: j.get("gone_date") or "", reverse=True)[:25]

    warn_html = ""
    if warnings:
        items = "<br>".join(esc(w) for w in warnings)
        warn_html = f'<div class="warn-box">&#9888; Source health: {items}</div>'

    def section(title, jobs, fold=False, hint=None):
        if not jobs:
            return ""
        cards = "\n".join(_card(j, p_of(j), roles, narrate) for j in jobs)
        h = f'<p class="hint">{esc(hint)}</p>' if hint else ""
        if fold:
            return (f'<section><details class="fold"><summary>{esc(title)} '
                    f'<span class="n">({len(jobs)})</span></summary>{h}{cards}'
                    f'</details></section>')
        return (f'<section><h2>{esc(title)} <span class="n">({len(jobs)})</span>'
                f'</h2>{h}{cards}</section>')

    def roster_section():
        tiers = {}
        for c in companies:
            tiers.setdefault(c["tier"], []).append(c)
        parts = []
        n_on = sum(1 for c in companies if c.get("enabled"))
        for t in ("A", "B", "C"):
            rows = []
            for c in tiers.get(t, []):
                cls = "on" if c.get("enabled") else "off"
                title = "" if c.get("enabled") else (
                    f' title="{esc(c.get("note") or "endpoint not yet verified")}"')
                rows.append(f'<span class="{cls}"{title}>{esc(c["name"])}</span>')
            if rows:
                parts.append(f'<div><b>Tier {t}</b> &nbsp;'
                             + " &middot; ".join(rows) + "</div>")
        return (f'<section><details class="fold"><summary>Monitored companies '
                f'<span class="n">({n_on} live of {len(companies)})</span>'
                f'</summary><div class="card"><div class="roster">'
                + "".join(parts)
                + '</div><p class="hint" style="margin-bottom:0">Dotted = endpoint '
                  'not verified yet; hover for why. Nothing is hidden — a company '
                  'with no live endpoint contributes no jobs and says so here.'
                  '</p></div></details></section>')

    new_count = sum(1 for j in active if "new" in j["flags"])
    body = f"""<main>
<header>
<h1>FP&amp;A &amp; Strategic Finance job watch</h1>
<div class="stats">
  <span><b>{len(active)}</b> live roles</span>
  <span><b>{len(best)}</b> at fit {bands['best']}+</span>
  <span><b>{new_count}</b> new this run</span>
  <span>updated {esc(today)}</span>
  <span id="hidden-note"></span>
  <button id="unhide" class="ghost" style="display:none">unhide all</button>
</div>
{warn_html}
</header>
{section(f"Best matches — fit {bands['best']} and above", best)}
{section("Stretch roles", stretch, fold=True,
         hint="Fit " + str(bands["stretch"]) + "–" + str(bands["best"] - 1)
              + ". Credible but not a clean match — worth a look where the "
                "pivot score is high.")}
{section("Lower fit", low, fold=True,
         hint="Cleared the function, seniority and location gates but score low. "
              "Kept visible rather than deleted, so the filter can be judged.")}
{section("Below compensation target", below, fold=True,
         hint="Stated range tops out under target. Kept because a posted base "
              "range is not the whole package.")}
{_triage_section(triage)}
{section("No longer listed", gone, fold=True)}
{roster_section()}
<footer><details class="fold"><summary>About this board</summary>
<div class="about">
<p><b>Verbatim or nothing.</b> Company, title, location, posted date,
compensation text and job description are quoted from the employer's posting.
Anything the posting doesn't state says "not listed" — no estimates, no
paraphrasing, and no guessed total compensation.</p>
<p><b>The two scores are derived.</b> Fit (0–100) weighs transferable
experience 30%, FP&amp;A learning opportunity 25%, compensation 20%,
seniority 15%, location 10%. Pivot (1–10) is how much the role would expand
the resume: 10 is broad corporate planning and P&amp;L ownership, 1 is
effectively another client-finance seat. Both come from term lists in
<code>config/roles.yaml</code> — they are not claims made by the employer.
Cards are sorted by fit, then company tier, then stated compensation, then
distance from New York.</p>
<p><b>What's excluded.</b> Accounting, controller, tax, treasury, AR/AP,
billing and revenue accounting roles; anything below Manager; and client or
commercial finance, which is the lane this board exists to leave. A big-tech
"Finance Manager" is <i>not</i> filtered out — company leveling matters more
than title wording.</p>
<p><b>Applied and hidden</b> are saved in this browser only. They are never
committed to the repository, never shared, and do not follow you to another
device.</p>
</div></details></footer>
</main>"""

    DOCS.mkdir(exist_ok=True)
    page = ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            "<meta name=\"robots\" content=\"noindex\">"
            "<title>FP&amp;A &amp; Strategic Finance job watch</title>"
            f"<style>{CSS}</style></head>"
            f"<body>{body}<script>{JS}</script></body></html>")
    (DOCS / "index.html").write_text(page, encoding="utf-8")
