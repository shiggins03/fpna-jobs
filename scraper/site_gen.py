"""Static dashboard generator -> docs/index.html (served by GitHub Pages).

Card layout, not a spreadsheet: the source spec asked for eighteen columns,
which is unreadable on a phone and this board is shared by link. Every factual
value is the source's verbatim text and absent fields say "Not listed"; the
scores, level, gap flags and recommendation are DERIVED and marked as such
(title attribute on the score row plus the footer note).
"""
import html
from pathlib import Path

from .filters import city_rank, comp_sort_value
from .models import norm

DOCS = Path(__file__).resolve().parent.parent / "docs"
TIER_ORDER = {"A": 0, "B": 1, "C": 2}
CAT_LABEL = {"bigtech": "Big Tech", "tech": "Tech", "advertising": "Advertising"}
SEV_LABEL = {"green": "GREEN", "yellow": "YELLOW", "red": "RED"}

CSS = """
:root{--bg:#f7f7f5;--card:#fff;--text:#1a1a1a;--muted:#666;--line:#e2e2de;
--accent:#0c447c;--badge:#e6f1fb;--warn-bg:#faeeda;--warn-text:#633806;
--new:#1d9e75;--gone:#999;--star:#8a5a00;--star-bg:#fdf3d7;
--green:#1d7a4f;--yellow:#8a6100;--red:#a52a2a}
@media(prefers-color-scheme:dark){:root{--bg:#171715;--card:#22221f;--text:#eee;
--muted:#9a9a94;--line:#3a3a36;--accent:#85b7eb;--badge:#0c2c4c;
--warn-bg:#3a2c10;--warn-text:#fac775;--star:#f0c869;--star-bg:#3a2c10;
--green:#5ec48f;--yellow:#e0b44c;--red:#e88}
*{box-sizing:border-box}body{margin:0;padding:16px;background:var(--bg);
color:var(--text);font:16px/1.5 system-ui,-apple-system,sans-serif}
main{max-width:860px;margin:0 auto}h1{font-size:22px;margin:0 0 4px}
.sub{color:var(--muted);font-size:13px;margin-bottom:16px}
.warn{background:var(--warn-bg);color:var(--warn-text);border-radius:8px;
padding:10px 14px;font-size:14px;margin-bottom:16px}
h2{font-size:17px;margin:24px 0 10px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;
padding:14px 16px;margin-bottom:10px}
.card.applied{opacity:.72}
.co{font-weight:600}.badge{display:inline-block;font-size:11px;font-weight:600;
background:var(--badge);color:var(--accent);border-radius:4px;padding:1px 6px;
margin-left:6px;vertical-align:1px;white-space:nowrap}
.badge.new{background:transparent;color:var(--new);border:1px solid var(--new)}
.badge.star{background:var(--star-bg);color:var(--star)}
.badge.plain{background:transparent;color:var(--muted);
border:1px solid var(--line);font-weight:500}
.title a{color:var(--accent);text-decoration:none;font-size:17px}
.title a:hover{text-decoration:underline}
.meta{color:var(--muted);font-size:13px;margin-top:4px}
.comp{font-size:14px;margin-top:4px}
.scores{font-size:13px;margin-top:6px;padding-top:6px;
border-top:1px dashed var(--line);color:var(--muted)}
.scores b{color:var(--text)}
.sev-green{color:var(--green);font-weight:600}
.sev-yellow{color:var(--yellow);font-weight:600}
.sev-red{color:var(--red);font-weight:600}
.acts{margin-top:8px;font-size:13px}
.acts button{font:inherit;color:var(--muted);background:none;cursor:pointer;
border:1px solid var(--line);border-radius:6px;padding:2px 8px;margin-right:6px}
.acts button:hover{color:var(--text)}
details{margin-top:8px;font-size:14px}summary{cursor:pointer;color:var(--muted)}
details pre{white-space:pre-wrap;font:13px/1.5 inherit;color:var(--text);
max-height:400px;overflow-y:auto;background:none;margin:8px 0 0}
.analysis{font-size:13.5px;margin-top:8px}
.analysis p{margin:6px 0}.analysis .lbl{font-weight:600;color:var(--text)}
section details.fold>summary{font-size:15px;color:var(--text);font-weight:600}
.gone .title a{color:var(--gone)}.gone .co{color:var(--gone)}
footer{color:var(--muted);font-size:12px;margin:24px 0}
.on{color:var(--text)}.off{color:var(--muted);opacity:.65}
@media(max-width:600px){body{padding:10px}.badge{margin-left:4px}}
"""

# Applied / hidden ticks live only in the viewer's browser: this is a public
# repo shared by link, so one person's tracking must never be committed or
# visible to anyone else. Per-device by design — stated in the footer so a tick
# that doesn't follow you to your phone isn't a surprise. Job ids hash
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
      var b=c.querySelector('.applied-badge');
      if(b) b.textContent = on ? ('applied '+applied[id]) : '';
      if(b) b.style.display = on ? '' : 'none';
      var btn=c.querySelector('.btn-applied');
      if(btn) btn.textContent = on ? 'undo applied' : 'mark applied';
    });
    var n=document.getElementById('hidden-note');
    if(n) n.textContent = nh ? (nh+' hidden on this device') : '';
    var r=document.getElementById('unhide');
    if(r) r.style.display = nh ? '' : 'none';
  }
  document.addEventListener('click',function(e){
    var t=e.target;
    if(t.classList.contains('btn-applied')){
      var id=t.closest('.card').getAttribute('data-id');
      if(applied[id]) delete applied[id];
      else applied[id]=new Date().toISOString().slice(0,10);
      save(AK,applied); paint();
    } else if(t.classList.contains('btn-hide')){
      var id2=t.closest('.card').getAttribute('data-id');
      hidden[id2]=1; save(HK,hidden); paint();
    } else if(t.id==='unhide'){
      hidden={}; save(HK,hidden); paint();
    }
  });
  paint();
})();
"""


def esc(s):
    return html.escape(str(s)) if s else ""


def _badges(j, prestige, roles):
    out = []
    if prestige:
        out.append(f'<span class="badge">Tier {esc(prestige)}</span>')
    cat = CAT_LABEL.get(j.get("category"))
    if cat:
        out.append(f'<span class="badge plain">{esc(cat)}</span>')
    if "new" in j["flags"]:
        out.append('<span class="badge new">new</span>')
    star = (j.get("pivot", 0) >= roles["bands"]["pivot_star"]
            and j.get("fit", 0) >= roles["bands"]["best"])
    if star:
        out.append('<span class="badge star" title="This role would add the most '
                   'new corporate FP&amp;A scope of anything on the board">'
                   '&#11088; HIGH-VALUE FP&amp;A PIVOT</span>')
    if j.get("remote"):
        out.append('<span class="badge plain" title="the posting states remote '
                   'eligibility">remote</span>')
    if j.get("level_label"):
        out.append(f'<span class="badge plain" title="seniority band derived from '
                   f'the title, not stated by the employer">'
                   f'{esc(j["level_label"])}</span>')
    if "long-posted" in j["flags"]:
        out.append('<span class="badge plain">long-posted</span>')
    if "manual" in j["flags"]:
        out.append('<span class="badge plain" title="added by hand from a direct '
                   'link — this employer blocks automated access">manual</span>')
    if j["kind"] == "board":
        out.append('<span class="badge plain" title="found on an aggregator; the '
                   'employer\'s own posting has not been resolved yet">'
                   'board find</span>')
    out.append('<span class="badge new applied-badge" style="display:none"></span>')
    return "".join(out)


def _card(j, prestige, roles, narrate):
    comp = esc(j.get("comp")) or '<span style="color:var(--muted)">Not listed</span>'
    extras = j.get("extras") or {}
    extra_bits = []
    if extras.get("bonus"):
        extra_bits.append("bonus mentioned")
    if extras.get("equity"):
        extra_bits.append("equity/RSUs mentioned")
    if j.get("comp_multi"):
        extra_bits.append("posting states several location ranges — "
                          "this may not be the New York one")
    extra_txt = (f' <span style="color:var(--muted)">&middot; '
                 f'{esc(", ".join(extra_bits))}</span>' if extra_bits else "")
    posted = esc(j.get("posted_date")) or "Not listed"
    loc = esc(j.get("location")) or "Not listed"
    if j.get("scope") == "unknown":
        loc += ('<span class="badge plain" title="the posting does not name a '
                'specific city — kept because multi-location reqs often include '
                'New York">not specific</span>')
    sev = j.get("gap_severity", "green")
    n = narrate(j)
    analysis = (
        f'<div class="analysis">'
        f'<p><span class="lbl">Why this matches:</span> {esc(n["why"])}</p>'
        f'<p><span class="lbl">What this would add:</span> {esc(n["learn"])}</p>'
        f'<p><span class="lbl">Gaps:</span> {esc(n["gaps"])}</p>'
        f'<p><span class="lbl">Career value:</span> {esc(n["value"])}</p>'
        + (f'<p><span class="lbl">FP&amp;A areas in the posting:</span> '
           f'{esc(", ".join(n["areas"]))}</p>' if n["areas"] else "")
        + '</div>')
    desc = ""
    if j.get("description"):
        desc = (f"<details><summary>Job description (verbatim)</summary>"
                f"<pre>{esc(j['description'])}</pre></details>")
    gone = ""
    if j["status"] == "gone":
        gone = f' &mdash; no longer listed as of {esc(j["gone_date"])}'
    return f"""<div class="card{' gone' if j['status'] == 'gone' else ''}" data-id="{esc(j['id'])}">
<div class="co">{esc(j['company'])}{_badges(j, prestige, roles)}</div>
<div class="title"><a href="{esc(j['url'])}" target="_blank" rel="noopener">{esc(j['title'])}</a></div>
<div class="meta">{loc} &middot; Posted: {posted} &middot; Found: {esc(j['first_seen'])}{gone}</div>
<div class="comp">Comp: {comp}{extra_txt}</div>
<div class="scores" title="Derived from the term lists in config/roles.yaml — not stated by the employer">
Fit <b>{j.get('fit', 0)}</b>/100 &middot; FP&amp;A transition <b>{j.get('pivot', 0)}</b>/10
 &middot; Gaps <span class="sev-{sev}">{SEV_LABEL.get(sev, sev)}</span>
 &middot; <b>{esc(j.get('recommendation'))}</b></div>
<details><summary>Analysis</summary>{analysis}</details>
{desc}
<div class="acts"><button class="btn-applied">mark applied</button>
<button class="btn-hide">hide</button></div>
</div>"""


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
            f'<div class="card"><div class="co">{esc(t["company"])}'
            f'<span class="badge plain" title="{esc(t.get("note"))}">'
            f'not scored</span></div>'
            f'<div class="title"><a href="{esc(t["url"])}" target="_blank" '
            f'rel="noopener">{esc(t["title"])}</a></div>'
            f'<div class="meta">Location: Not listed &middot; Comp: Not listed '
            f'&middot; Found: {esc(t.get("first_seen"))}</div></div>')
    return (f'<section><details class="fold"><summary>Worth a look — not '
            f'scoreable ({len(rows)})</summary>'
            f'<div class="meta">These matched the employer\'s own finance search, '
            f'but their posting text isn\'t machine-readable, so there is no fit '
            f'score and no location or comp to show. Open the link to judge them. '
            f'Mostly Meta, whose job search returns titles only.</div>'
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
        warn_html = f'<div class="warn">&#9888; Source health: {items}</div>'

    def section(title, jobs, fold=False, note=None):
        if not jobs:
            return ""
        cards = "\n".join(_card(j, p_of(j), roles, narrate) for j in jobs)
        sub = f'<div class="meta">{esc(note)}</div>' if note else ""
        if fold:
            return (f'<section><details class="fold"><summary>{esc(title)} '
                    f'({len(jobs)})</summary>{sub}{cards}</details></section>')
        return (f'<section><h2>{esc(title)} ({len(jobs)})</h2>{sub}{cards}</section>')

    def roster_section():
        tiers = {}
        for c in companies:
            tiers.setdefault(c["tier"], []).append(c)
        parts = []
        n_on = sum(1 for c in companies if c.get("enabled"))
        for t in ("A", "B", "C"):
            rows = []
            for c in tiers.get(t, []):
                if c.get("enabled"):
                    rows.append(f'<span class="on">{esc(c["name"])}</span>')
                else:
                    rows.append(f'<span class="off" title="'
                                f'{esc(c.get("note") or "pending fingerprint")}">'
                                f'{esc(c["name"])}</span>')
            if rows:
                parts.append(f'<div class="meta" style="margin-top:6px">'
                             f'<b>Tier {t}:</b> ' + " &middot; ".join(rows) + "</div>")
        return (f'<section><details class="fold"><summary>Monitored companies '
                f'({n_on} live of {len(companies)})</summary><div class="card">'
                + "".join(parts)
                + '<div class="meta" style="margin-top:10px">Greyed = endpoint not '
                  'yet verified (hover for why). Nothing is hidden: a company with '
                  'no live endpoint contributes no jobs, and says so here.</div>'
                  '</div></details></section>')

    new_count = sum(1 for j in active if "new" in j["flags"])
    body = f"""<main>
<h1>FP&amp;A / Strategic Finance job watch</h1>
<div class="sub">Updated {esc(today)} &middot; {len(active)} live roles
 &middot; {len(best)} at fit {bands['best']}+ &middot; {new_count} new this run
 &middot; <span id="hidden-note"></span>
 <button id="unhide" style="display:none;font:inherit;background:none;
 border:1px solid var(--line);border-radius:6px;cursor:pointer;
 color:var(--muted);padding:1px 6px">unhide all</button></div>
{warn_html}
{section(f"Best matches — fit {bands['best']}+", best)}
{section("Stretch roles — credible but not a clean match", stretch, fold=True,
         note="Fit " + str(bands["stretch"]) + "-" + str(bands["best"] - 1)
              + ": worth a look where the FP&A transition score is high.")}
{section("Lower fit", low, fold=True,
         note="Passed the function, seniority and location gates but scores low "
              "— kept visible rather than deleted so the filter can be judged.")}
{section("Below comp target", below, fold=True,
         note="Stated comp tops out under the target. Kept because a posted "
              "range is not the whole package.")}
{_triage_section(triage)}
{section("No longer listed", gone, fold=True)}
{roster_section()}
<footer>
Company, title, location, posted date, compensation and description are shown
<b>verbatim</b> from the employer's posting; anything the posting doesn't state
says "Not listed" &mdash; nothing is estimated or paraphrased.
Fit score, FP&amp;A transition score, seniority band, gap flags and the
recommendation are <b>derived</b> from the term lists in
<code>config/roles.yaml</code> and are not claims made by the employer.
Sorted by fit, then company tier, then stated comp, then distance from NYC.
&ldquo;Mark applied&rdquo; and &ldquo;hide&rdquo; are stored in this browser only
&mdash; they are not committed to the repo, not shared, and do not follow you to
another device.
</footer>
</main>"""

    DOCS.mkdir(exist_ok=True)
    page = ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            "<meta name=\"robots\" content=\"noindex\">"
            "<title>FP&amp;A / Strategic Finance job watch</title>"
            f"<style>{CSS}</style></head>"
            f"<body>{body}<script>{JS}</script></body></html>")
    (DOCS / "index.html").write_text(page, encoding="utf-8")
