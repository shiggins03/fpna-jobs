# fpna-jobs

A daily-refreshed board of **senior corporate FP&A, Strategic Finance and
Business Finance roles in the New York area** (or remote-eligible for New York
residents), aimed at someone moving into corporate FP&A from a commercial /
client finance background.

**Dashboard: https://shiggins03.github.io/fpna-jobs/**

It watches employers' own applicant-tracking systems — not job boards — and
publishes a static page. Nothing to install, nothing to log into.

## What it looks for

| Gate | Rule |
|---|---|
| Function | At least two planning/analysis signals (AOP, budgeting, forecasting, P&L, LRP, OpEx, variance, modeling, business partnering …) |
| Seniority | Manager and above. A big-tech "Finance Manager" is **not** rejected for its title — company leveling beats title wording |
| Location | NYC, NYC metro, or stated remote. Multi-location reqs are kept, not dropped |
| Excluded | Accounting, controller, tax, treasury, AR/AP, billing, revenue accounting — and client/commercial finance, which is the lane this board exists to leave |

Compensation is **not** a gate: a strong role that doesn't post a salary still
appears, marked "Not listed". Roles whose stated range tops out below target
drop to a collapsed section rather than disappearing.

## The two scores

Both are **derived** — computed from term lists in
[`config/roles.yaml`](config/roles.yaml), never claims made by the employer.

- **Fit score (0–100)** — transferability 30%, FP&A learning opportunity 25%,
  compensation 20%, seniority/scope 15%, location 10%.
- **FP&A transition score (1–10)** — how much the role would *expand* the
  resume. 10 means broad corporate planning and P&L ownership; 1 means it is
  effectively another client-finance seat.

Roles scoring 8+ on transition with a strong fit get a
⭐ **HIGH-VALUE FP&A PIVOT** badge. Each card also carries a short analysis:
why it matches, what it would add, gaps (GREEN / YELLOW / RED), career value,
and an apply recommendation.

## Verbatim or "Not listed"

Company, title, location, posted date, compensation text and the job
description are quoted from the employer's posting. Nothing is estimated,
paraphrased, or inferred — including total compensation, which stays unstated
when the posting doesn't state it. See rule 1 in `CLAUDE.md`.

## How it runs

GitHub Actions, daily at 12:30 UTC. The pipeline fetches each employer's ATS,
applies the gates, scores what survives, and regenerates
`docs/index.html`, which GitHub Pages serves. Results are committed to the repo,
so the history is the record of what was posted when.

"Mark applied" and "hide" are stored in your own browser only — never committed,
never shared, and they do not follow you to another device.

## Layout

```
scraper/       fetch → qualify → dedup → expire → score → publish
config/        the entire tuning surface (see the comments in each file)
data/          job store, source health, triage queue
docs/          the generated dashboard — never hand-edit
```

Adapted from a sibling project of the same shape (`unifier-jobs`), which
watches a completely different market. The fetch layer is shared by copy, not
by dependency — the two repos are deliberately independent.
