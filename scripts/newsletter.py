#!/usr/bin/env python3
"""The weekly newsletter: gather the week's events, check an issue's words against the facts, render it.

Usage
  python scripts/newsletter.py week 2026-10-15            # what the editor can pick from (JSON)
  python scripts/newsletter.py render data/newsletter/issues/2026-10-15.json --format html --out issue.html
  python scripts/newsletter.py render data/newsletter/issues/2026-10-15.json --format md
  python scripts/newsletter.py buttondown-draft data/newsletter/issues/2026-10-15.json

An issue file (schemas/newsletter-issue.schema.json) says which events go where, in what layout, with
what words. It holds no event facts of its own: dates, times, prices, venues and ticket links are read
from data/events when the issue is rendered, so the email always shows what the verifier confirmed.

'buttondown-draft' creates a DRAFT in Buttondown (needs BUTTONDOWN_API_KEY). It never sends anything:
a person reads the draft in Buttondown and presses send.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
LONDON = ZoneInfo("Europe/London")
SITE_URL = os.environ.get("BGL_SITE_URL") or "https://fredfesty.github.io/bethnal-green-live/"
SAVE_THE_DATE_DAYS = 42   # how far past the issue's week "save the date" may reach
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
STATUS_LABEL = {"few-left": "Last few tickets", "sold-out": "Sold out", "cancelled": "Cancelled",
                "postponed": "Postponed"}
CATEGORY = {"nights-music": "Nights & music", "arts": "Cinema & arts", "food-drink": "Food & drink",
            "community": "Community"}
SUBCATEGORY = {
    "club-night": "Club night", "gig": "Gig", "dj-bar": "DJ night", "queer-party": "Queer party",
    "cabaret-drag": "Cabaret & drag", "karaoke": "Karaoke", "jazz": "Jazz", "open-mic": "Open mic",
    "folk-acoustic": "Folk & acoustic", "in-store": "In-store gig", "theatre": "Theatre", "comedy": "Comedy",
    "film": "Film", "exhibition": "Exhibition", "dance": "Dance", "performance": "Performance",
    "supper-club": "Supper club", "pop-up": "Pop-up", "tasting": "Tasting", "special-menu": "Special menu",
    "cookery-class": "Cookery class", "food-market": "Food market", "food-festival": "Food festival",
    "opening": "Opening", "quiz": "Quiz", "market": "Market", "fair": "Fair", "workshop": "Workshop",
    "family": "Family", "outdoors": "Outdoors", "sport": "Sport", "volunteering": "Volunteering",
    "open-studios": "Open studios", "tour": "Walk or tour", "talk": "Talk", "festival": "Festival",
}
# Sections that only take one category of event.
SECTION_CATEGORY = {"cinema-and-arts": "arts", "food-and-drink": "food-drink", "community": "community"}


def kind_label(e: dict) -> str:
    sub = e.get("subcategory")
    if sub and sub != "other" and sub in SUBCATEGORY:
        return SUBCATEGORY[sub]
    return "Music" if e.get("category") == "nights-music" else CATEGORY.get(e.get("category"), "Event")


# ---------------------------------------------------------------- loading

def read(p: Path):
    return json.loads(p.read_text(encoding="utf-8").lstrip("﻿"))


def load_events(root: Path | None = None) -> dict[str, dict]:
    """Every published event file, by id (skips _example folders)."""
    base = (root or ROOT) / "data" / "events"
    out: dict[str, dict] = {}
    for p in sorted(base.rglob("*.json")):
        if any(part.startswith("_") for part in p.relative_to(base).parts):
            continue
        try:
            d = read(p)
        except (OSError, ValueError):
            continue
        if isinstance(d, dict) and d.get("id"):
            out[d["id"]] = d
    return out


def load_venue_profiles(root: Path | None = None) -> dict[str, dict]:
    """Checked venue profiles only (same rule as the website): reviewed since its last change, nothing in doubt."""
    out = {}
    for p in sorted(((root or ROOT) / "data" / "venues").glob("*.json")):
        try:
            d = read(p)
        except (OSError, ValueError):
            continue
        rev = d.get("review") or {}
        try:
            fresh = dt.datetime.fromisoformat(rev["checked_at"]) >= dt.datetime.fromisoformat(d["profiled_at"])
        except (KeyError, TypeError, ValueError):
            fresh = False
        if fresh and not d.get("needs_review"):
            out[d["id"]] = d
    return out


def load_issues(root: Path | None = None) -> dict[str, dict]:
    out = {}
    for p in sorted(((root or ROOT) / "data" / "newsletter" / "issues").glob("*.json")):
        try:
            out[p.stem] = read(p)
        except (OSError, ValueError):
            continue
    return out


# ---------------------------------------------------------------- facts, in London time

def has_time(w: str) -> bool:
    return "T" in w


def local(w: str) -> dt.datetime:
    return dt.datetime.fromisoformat(w).astimezone(LONDON)


def event_date(e: dict) -> dt.date:
    w = e["starts_at"]
    return local(w).date() if has_time(w) else dt.date.fromisoformat(w)


def end_date(e: dict) -> dt.date | None:
    w = e.get("ends_at")
    if not w:
        return None
    return local(w).date() if has_time(w) else dt.date.fromisoformat(w)


def last_date(e: dict) -> dt.date:
    return end_date(e) or event_date(e)


def is_run(e: dict) -> bool:
    """An exhibition, theatre run or multi-day menu: ends two or more days after it opens.
    (An overnight club night ends the next day, which is not a run.)"""
    return (last_date(e) - event_date(e)).days >= 2


def on_during(e: dict, frm: dt.date, to: dt.date) -> bool:
    """On at some point between frm and to: a one-off on one of those days, or a run that overlaps them."""
    return event_date(e) <= to and last_date(e) >= frm


def clock(w: str) -> str:
    t = local(w)
    if t.minute == 0 and t.hour == 0:
        return "midnight"
    if t.minute == 0 and t.hour == 12:
        return "noon"
    h = t.hour % 12 or 12
    return f"{h}{'' if t.minute == 0 else f':{t.minute:02d}'}{'am' if t.hour < 12 else 'pm'}"


def time_label(e: dict) -> str:
    s, end = e["starts_at"], e.get("ends_at")
    if not has_time(s):
        return "Time tbc"
    return f"{clock(s)}–{clock(end)}" if end and has_time(end) else clock(s)


def gbp(n: float) -> str:
    return f"£{int(n)}" if float(n).is_integer() else f"£{n:.2f}"


def price_label(p: dict) -> str:
    if not p.get("known"):
        return "Price not listed"
    if p.get("is_free"):
        return "Free"
    lo, hi = p.get("min_gbp"), p.get("max_gbp")
    if lo == 0 and hi:
        return f"Free–{gbp(hi)}"
    if lo is not None and hi is not None and hi != lo:
        return f"{gbp(lo)}–{gbp(hi)}"
    if lo is not None and hi is None:
        return f"From {gbp(lo)}"
    return gbp(lo) if lo is not None else "See tickets"


def short_date(d: dt.date) -> str:
    return f"{d.strftime('%a')} {d.day} {d.strftime('%b')}"


def long_date(d: dt.date) -> str:
    return f"{d.strftime('%A')} {d.day} {d.strftime('%B')}"


def week_label(a: dt.date, b: dt.date) -> str:
    if a.month == b.month:
        return f"{a.day}–{b.day} {b.strftime('%B')}"
    return f"{a.day} {a.strftime('%B')} – {b.day} {b.strftime('%B')}"


def when_label(e: dict) -> str:
    if is_run(e):
        return f"Until {short_date(last_date(e))}" + (f" ({e['run_schedule']})" if e.get("run_schedule") else "")
    return f"{short_date(event_date(e))} · {time_label(e)}"


def details_line(e: dict) -> str:
    return " · ".join([when_label(e), e["venue"]["name"], price_label(e["price"])])


def event_url(e: dict, site_url: str = SITE_URL) -> str:
    return site_url.rstrip("/") + f"/events/{e['id']}.html"


# ---------------------------------------------------------------- checking words against facts

_POUNDS = re.compile(r"£\s?(\d+(?:\.\d{1,2})?)")
_TIME = re.compile(r"\b(\d{1,2})(?:[:.](\d{2}))?\s?(am|pm)\b", re.I)
_WEEKDAY = re.compile(r"\b(" + "|".join(WEEKDAYS) + r")s?\b", re.I)
_FREE = re.compile(r"(?<![-\w])(?<!feel )free(?![-\w])", re.I)
FIRST_HAND = re.compile(
    r"\b(I|we)\s+(went|was at|were at|saw|caught|heard|danced|spent|tried|ate|drank|popped|stumbled|found myself)\b"
    r"|\blast (week|weekend|night|time) I\b|\bI've been (to|going)\b",
    re.I,
)


_PROMO = re.compile(
    r"\b(iconic|legendary|unmissable|epic|vibes?|must[- ]see|world[- ]class|not to be missed|don'?t miss|"
    r"something for everyone)\b", re.I)
_RELATIVE_DAY = re.compile(
    r"\b(tonight|tomorrow|today|yesterday|later this (?:week|month)|(?:this|next)(?: coming)? (?:week|weekend|month|"
    + "|".join(WEEKDAYS) + r"))\b", re.I)
_STATUS_WORDS = re.compile(r"\b(sold[- ]out|selling fast|last (?:few|remaining) tickets|few tickets left|"
                           r"limited tickets|almost gone)\b", re.I)


def style_problems(text: str) -> list[str]:
    """House style for words that sit on the website for weeks: no advert words, no 'tonight', no ticket
    status (the site shows the checked status itself), at most one exclamation mark, no first-hand claims."""
    if not text:
        return []
    errs = []
    for rx, why in ((_PROMO, "is advert language; say what it is instead"),
                    (_RELATIVE_DAY, "depends on the day it's read; name the day or leave it out"),
                    (_STATUS_WORDS, "is ticket status, which changes; the site shows the checked status"),
                    (FIRST_HAND, "claims a first-hand experience")):
        m = rx.search(text)
        if m:
            errs.append(f"'{m.group(0)}' {why}")
    if text.count("!") > 1:
        errs.append("more than one exclamation mark")
    return errs


def price_numbers(e: dict) -> set[float]:
    p = e["price"]
    nums = {float(v) for v in (p.get("min_gbp"), p.get("max_gbp")) if v is not None}
    nums |= {float(m) for m in _POUNDS.findall(p.get("notes") or "")}
    return nums


def event_times(e: dict) -> set[tuple[int, int]]:
    out = {hm for _, hm in _mentioned_times(e.get("run_schedule") or "")}
    out |= {hm for _, hm in _mentioned_times(e["price"].get("notes") or "")}  # "£12 after 10.30pm"
    for w in (e["starts_at"], e.get("ends_at")):
        if w and has_time(w):
            t = local(w)
            out.add((t.hour, t.minute))
    return out


def _mentioned_times(text: str) -> list[tuple[str, tuple[int, int]]]:
    out = []
    for m in _TIME.finditer(text):
        h, mm, ap = int(m.group(1)), int(m.group(2) or 0), m.group(3).lower()
        if not 1 <= h <= 12 or mm > 59:
            continue
        out.append((m.group(0), ((h % 12) + (12 if ap == "pm" else 0), mm)))
    for word, hm in (("midnight", (0, 0)), ("noon", (12, 0)), ("midday", (12, 0))):
        if re.search(rf"\b{word}\b", text, re.I):
            out.append((word, hm))
    return out


def is_free_ish(e: dict) -> bool:
    p = e["price"]
    return bool(p.get("known") and (p.get("is_free") or p.get("min_gbp") == 0))


def fact_problems(text: str, events: list[dict], one_event: bool) -> list[str]:
    """Numbers, times, days and 'free' in our words must match the checked facts.

    Pass the text with event titles and names already taken out (validate.without_names), so a title like
    "Free Party" or "Sunday Service" neither excuses nor trips a check.

    one_event: the text is about a single event (a blurb), so its weekday and 'free' are checked too.
    """
    if not text:
        return []
    errs = []
    prices = set().union(*(price_numbers(e) for e in events)) if events else set()
    for m in _POUNDS.finditer(text):
        if float(m.group(1)) not in prices:
            errs.append(f"says {m.group(0)}, which no checked price says")
    times = set().union(*(event_times(e) for e in events)) if events else set()
    for said, hm in _mentioned_times(text):
        if hm not in times:
            errs.append(f"says '{said}', which isn't a checked start or end time")
    if one_event and events:
        e = events[0]
        if _FREE.search(text) and not is_free_ish(e):
            errs.append("says 'free' but the checked price isn't free")
        if is_run(e):  # open on many days: a weekday is fine if its opening hours mention it, so don't guess
            return errs
        days = {WEEKDAYS[event_date(e).weekday()]}
        end = e.get("ends_at")
        if end and (not has_time(end) or local(end).hour >= 6):  # a night ending at 3am is still the night it began
            days.add(WEEKDAYS[end_date(e).weekday()])
        for m in _WEEKDAY.finditer(text):
            if m.group(1).lower() not in days and not (e.get("recurrence") and m.group(1).lower() in e["recurrence"].lower()):
                errs.append(f"says '{m.group(0)}' but it's on a {WEEKDAYS[event_date(e).weekday()].title()}")
    return errs


# ---------------------------------------------------------------- what the editor picks from

def event_view(e: dict, venues: dict[str, dict], featured_before: dict[str, list[str]] | None = None) -> dict:
    """One event as plain data for a writer: only checked facts, plus the checked venue profile."""
    v = venues.get(e["venue"].get("venue_id") or "")
    return {
        "id": e["id"], "title": e["title"], "date": event_date(e).isoformat(),
        "weekday": event_date(e).strftime("%A"), "time": time_label(e),
        "run": {"until": last_date(e).isoformat(), "opening_hours": e.get("run_schedule")} if is_run(e) else None,
        "venue": e["venue"]["name"], "zone": e["zone"], "type": kind_label(e),
        "category": e["category"], "price": price_label(e["price"]), "price_notes": e["price"].get("notes"),
        "status": e["status"], "lineup": e.get("lineup") or [], "genres": e.get("genres") or [],
        "recurrence": e.get("recurrence"), "age_restriction": e.get("age_restriction"),
        "accessibility": e.get("accessibility"), "worth_the_trip": e.get("worth_the_trip", False),
        "scout_opinion_internal": e.get("editor_note"),
        "listing_blurb": (e.get("listing") or {}).get("blurb"),
        "venue_profile": None if not v else {
            "summary": v.get("summary"), "music": v.get("music"), "crowd": v.get("crowd"),
            "step_free": (v.get("accessibility") or {}).get("step_free"),
        },
        "in_earlier_issues": (featured_before or {}).get(e["id"], []),
    }


def week(issue_date: dt.date, root: Path | None = None) -> dict:
    """Everything the editor needs for one issue, as plain data: only checked facts."""
    events = load_events(root)
    venues = load_venue_profiles(root)
    frm, to = issue_date, issue_date + dt.timedelta(days=6)
    last = to + dt.timedelta(days=SAVE_THE_DATE_DAYS)
    previous = {k: v for k, v in load_issues(root).items() if k < issue_date.isoformat()}
    featured_before = {}
    for k, iss in previous.items():
        for s in iss.get("sections", []):
            for it in s.get("items", []):
                featured_before.setdefault(it["event_id"], []).append(f"{k}: {s['kind']}")

    usable = [e for e in events.values() if not e.get("needs_review") and e["status"] not in ("cancelled", "postponed", "sold-out")]
    this_week = sorted((e for e in usable if on_during(e, frm, to)), key=lambda e: (e["starts_at"], e["title"]))
    later = sorted((e for e in usable if to < event_date(e) <= last), key=lambda e: (e["starts_at"], e["title"]))
    return {
        "issue_id": issue_date.isoformat(),
        "issue_number": len(previous) + 1,
        "covers": {"from": frm.isoformat(), "to": to.isoformat(), "label": week_label(frm, to)},
        "this_week": [event_view(e, venues, featured_before) for e in this_week],
        "save_the_date_window": {"after": to.isoformat(), "until": last.isoformat()},
        "later": [event_view(e, venues, featured_before) for e in later],
        "left_out": [{"id": e["id"], "why": "under review" if e.get("needs_review") else e["status"]}
                     for e in events.values() if e not in usable and on_during(e, frm, last)],
    }


# ---------------------------------------------------------------- rendering

C = {"paper": "#f4f5f1", "plate": "#ffffff", "ink": "#1b1d1b", "muted": "#5a605b", "rule": "#d5d9d1",
     "red": "#d42a1f", "green": "#1d5a39", "tint": "#e3ede6", "amber": "#8a4b00"}
SANS = "'Helvetica Neue',Helvetica,Arial,sans-serif"
NARROW = "'Archivo Narrow','Arial Narrow','Helvetica Neue',Arial,sans-serif"


def esc(s) -> str:
    return html.escape(str(s or ""), quote=True)


def resolve(issue: dict, events: dict[str, dict]) -> list[tuple[dict, list[tuple[dict, dict]]]]:
    out = []
    for s in issue["sections"]:
        items = [(it, events[it["event_id"]]) for it in s["items"] if it["event_id"] in events]
        if items:
            out.append((s, items))
    return out


def _status_badge(e: dict) -> str:
    lab = STATUS_LABEL.get(e["status"])
    if not lab:
        return ""
    col = C["amber"] if e["status"] == "few-left" else C["red"]
    return (f'<span style="display:inline-block;margin-left:6px;padding:1px 6px;border:1.5px solid {col};'
            f'border-radius:4px;color:{col};font:700 12px/1.4 {SANS};white-space:nowrap">{esc(lab)}</span>')


def _links(e: dict, site_url: str, button: bool) -> str:
    more = f'<a href="{esc(event_url(e, site_url))}" style="color:{C["green"]};font-weight:600">How we checked it</a>'
    if not e.get("ticket_url"):
        return f'<p style="margin:10px 0 0;font:15px/1.4 {SANS}">{more}</p>'
    if button:
        return (f'<table role="presentation" cellpadding="0" cellspacing="0" style="margin:14px 0 0"><tr>'
                f'<td style="background:{C["green"]};border-radius:6px">'
                f'<a href="{esc(e["ticket_url"])}" style="display:inline-block;padding:10px 18px;color:#ffffff;'
                f'font:700 15px/1.2 {SANS};text-decoration:none">Tickets &amp; details</a></td>'
                f'<td style="padding-left:14px;font:14px/1.4 {SANS}">{more}</td></tr></table>')
    return (f'<p style="margin:8px 0 0;font:15px/1.4 {SANS}"><a href="{esc(e["ticket_url"])}" '
            f'style="color:{C["green"]};font-weight:700">Tickets</a> &nbsp;·&nbsp; {more}</p>')


def _title(it: dict, e: dict, size: int, site_url: str = SITE_URL) -> str:
    head = it.get("headline")
    link = e.get("ticket_url") or event_url(e, site_url)
    t = (f'<p style="margin:0 0 4px;font:800 {size}px/1.15 {NARROW};color:{C["ink"]}">'
         f'<a href="{esc(link)}" style="color:{C["ink"]};text-decoration:none">{esc(head or e["title"])}</a>'
         f'{_status_badge(e)}</p>')
    if head:
        t += f'<p style="margin:0 0 4px;font:600 14px/1.35 {SANS};color:{C["muted"]}">{esc(e["title"])}</p>'
    return t


def _details(e: dict) -> str:
    return f'<p style="margin:0;font:700 14px/1.4 {SANS};color:{C["ink"]}">{esc(details_line(e))}</p>'


def _blurb(it: dict, size: int = 16) -> str:
    b = it.get("blurb")
    return f'<p style="margin:8px 0 0;font:{size}px/1.55 {SANS};color:{C["ink"]}">{esc(b)}</p>' if b else ""


def _section_html(s: dict, items: list[tuple[dict, dict]], site_url: str) -> str:
    emoji = f"{esc(s['emoji'])} " if s.get("emoji") else ""
    h = (f'<tr><td class="pad" style="padding:34px 28px 6px"><h2 style="margin:0;font:800 25px/1.1 {NARROW};'
         f'color:{C["ink"]};text-transform:uppercase;letter-spacing:.3px">{emoji}{esc(s["heading"])}</h2>'
         f'<div style="height:3px;background:{C["ink"]};margin-top:8px;font-size:0;line-height:0">&nbsp;</div>')
    if s.get("lede"):
        h += f'<p style="margin:10px 0 0;font:16px/1.5 {SANS};color:{C["muted"]}">{esc(s["lede"])}</p>'
    h += "</td></tr>"
    lay = s["layout"]
    if lay == "hero":
        for it, e in items:
            h += (f'<tr><td class="pad" style="padding:14px 28px 0"><table role="presentation" width="100%" '
                  f'cellpadding="0" cellspacing="0" style="background:{C["plate"]};border:2px solid #000;border-radius:8px">'
                  f'<tr><td style="padding:22px 22px 20px">{_title(it, e, 30, site_url)}{_details(e)}{_blurb(it, 17)}'
                  f'{_links(e, site_url, True)}</td></tr></table></td></tr>')
    elif lay == "cards":
        for it, e in items:
            h += (f'<tr><td class="pad" style="padding:12px 28px 0"><table role="presentation" width="100%" '
                  f'cellpadding="0" cellspacing="0" style="background:{C["plate"]};border:1.5px solid #000;border-radius:8px">'
                  f'<tr><td style="padding:16px 18px">{_title(it, e, 21, site_url)}{_details(e)}{_blurb(it)}'
                  f'{_links(e, site_url, False)}</td></tr></table></td></tr>')
    elif lay == "list":
        rows = ""
        for i, (it, e) in enumerate(items):
            top = "" if i == 0 else f"border-top:1px solid {C['rule']};"
            rows += (f'<tr><td style="{top}padding:14px 0">{_title(it, e, 19, site_url)}{_details(e)}{_blurb(it, 15)}'
                     f'{_links(e, site_url, False)}</td></tr>')
        h += (f'<tr><td class="pad" style="padding:4px 28px 0"><table role="presentation" width="100%" '
              f'cellpadding="0" cellspacing="0">{rows}</table></td></tr>')
    else:  # compact
        rows = ""
        for i, (it, e) in enumerate(items):
            top = "" if i == 0 else f"border-top:1px solid {C['rule']};"
            if is_run(e):
                end = last_date(e)
                left, sub = "Until", f"{end.strftime('%a')} {end.day} {end.strftime('%b')}"
            else:
                d = event_date(e)
                left, sub = f"{d.strftime('%a')} {d.day}", time_label(e).split("–")[0]
            rows += (f'<tr><td valign="top" style="{top}padding:10px 12px 10px 0;width:74px;font:800 15px/1.25 {NARROW};'
                     f'color:{C["ink"]};white-space:nowrap">{esc(left)}<br>'
                     f'<span style="font-weight:600;color:{C["muted"]}">{esc(sub)}</span></td>'
                     f'<td valign="top" style="{top}padding:10px 0;font:15px/1.4 {SANS};color:{C["ink"]}">'
                     f'<a href="{esc(e.get("ticket_url") or event_url(e, site_url))}" style="color:{C["ink"]};font-weight:700">'
                     f'{esc(it.get("headline") or e["title"])}</a>{_status_badge(e)}<br>'
                     f'<span style="color:{C["muted"]}">{esc(e["venue"]["name"])} · {esc(price_label(e["price"]))}</span>'
                     f'</td></tr>')
        h += (f'<tr><td class="pad" style="padding:4px 28px 0"><table role="presentation" width="100%" '
              f'cellpadding="0" cellspacing="0">{rows}</table></td></tr>')
    return h


def render_html(issue: dict, events: dict[str, dict], site_url: str = SITE_URL) -> str:
    frm, to = (dt.date.fromisoformat(issue["covers"][k]) for k in ("from", "to"))
    site = site_url.rstrip("/") + "/"
    pre = esc(issue["preheader"]) + "&nbsp;&zwnj;" * 60
    intro = ""
    if issue.get("intro"):
        i = issue["intro"]
        paras = "".join(f'<p style="margin:0 0 14px;font:17px/1.6 Georgia,\'Times New Roman\',serif;color:{C["ink"]}">'
                        f'{esc(p)}</p>' for p in i["paragraphs"])
        ps = (f'<p style="margin:16px 0 0;font:italic 15px/1.5 Georgia,serif;color:{C["muted"]}">PS {esc(i["postscript"])}</p>'
              if i.get("postscript") else "")
        intro = (f'<tr><td class="pad" style="padding:18px 28px 0"><table role="presentation" width="100%" '
                 f'cellpadding="0" cellspacing="0" style="background:{C["plate"]};border-left:4px solid {C["red"]};border-radius:4px">'
                 f'<tr><td style="padding:22px 24px 20px">'
                 f'<p style="margin:0 0 12px;font:800 20px/1.2 {NARROW};color:{C["ink"]}">{esc(i["greeting"])}</p>{paras}'
                 f'<p style="margin:4px 0 0;font:17px/1.5 Georgia,serif;color:{C["ink"]}">{esc(i["sign_off"])}</p>'
                 f'<p style="margin:2px 0 0;font:italic 700 24px/1.3 Georgia,serif;color:{C["red"]}">{esc(i["signed"])}</p>'
                 f'{ps}</td></tr></table></td></tr>')
    body = "".join(_section_html(s, items, site_url) for s, items in resolve(issue, events))
    return f"""<!doctype html>
<html lang="en-GB">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light">
<title>{esc(issue['subject'])}</title>
<style>
  @media (max-width: 620px) {{ .wrap {{ width: 100% !important; }} .pad {{ padding-left: 16px !important; padding-right: 16px !important; }} }}
  a {{ text-underline-offset: 2px; }}
</style>
</head>
<body style="margin:0;padding:0;background:{C['paper']}">
<div style="display:none;max-height:0;overflow:hidden;mso-hide:all">{pre}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{C['paper']}"><tr><td align="center" style="padding:20px 8px 32px">
<table role="presentation" class="wrap" width="600" cellpadding="0" cellspacing="0" style="width:600px;max-width:600px">
<tr><td class="pad" style="padding:8px 28px 0">
  <table role="presentation" cellpadding="0" cellspacing="0" style="background:{C['plate']};border:2px solid #000;border-radius:5px"><tr>
    <td style="padding:7px 13px 6px;font:800 23px/1 {NARROW};text-transform:uppercase;letter-spacing:.3px;color:#000">
      <a href="{esc(site)}" style="color:#000;text-decoration:none">Bethnal Green Live</a>
      <span style="color:{C['red']};font-size:14px;letter-spacing:.6px">&nbsp;E2</span></td></tr></table>
  <p style="margin:14px 0 0;font:700 14px/1.4 {SANS};color:{C['muted']};text-transform:uppercase;letter-spacing:.6px">
    Issue {issue['issue_number']} &nbsp;·&nbsp; What's on {esc(week_label(frm, to))}</p>
</td></tr>
{intro}
{body}
<tr><td class="pad" style="padding:36px 28px 0">
  <div style="height:1px;background:{C['rule']};font-size:0;line-height:0">&nbsp;</div>
  <p style="margin:16px 0 0;font:14px/1.55 {SANS};color:{C['muted']}">Every listing here was checked word for word against the
  venue's or ticket seller's own page before it went in. Plans change, so check the ticket page before you head out.</p>
  <p style="margin:10px 0 0;font:14px/1.55 {SANS};color:{C['muted']}">
    <a href="{esc(site)}index.html" style="color:{C['green']}">Everything on this month</a> &nbsp;·&nbsp;
    <a href="{esc(site)}calendar.html#feeds" style="color:{C['green']}">Add it to your calendar</a> &nbsp;·&nbsp;
    <a href="{esc(site)}newsletter.html" style="color:{C['green']}">Past issues</a></p>
</td></tr>
</table>
</td></tr></table>
</body>
</html>
"""


def render_markdown(issue: dict, events: dict[str, dict], site_url: str = SITE_URL) -> str:
    frm, to = (dt.date.fromisoformat(issue["covers"][k]) for k in ("from", "to"))
    out = [f"**Bethnal Green Live E2** · Issue {issue['issue_number']} · What's on {week_label(frm, to)}", ""]
    out += [f"**Subject:** {issue['subject']}  ", f"**Preview line:** {issue['preheader']}", ""]
    if issue.get("intro"):
        i = issue["intro"]
        out += [f"**{i['greeting']}**", ""] + [p + "\n" for p in i["paragraphs"]]
        out += [i["sign_off"], f"*{i['signed']}*", ""]
        if i.get("postscript"):
            out += [f"PS {i['postscript']}", ""]
    else:
        out += ["*(Fred's letter hasn't been written yet.)*", ""]
    for s, items in resolve(issue, events):
        out += [f"## {(s.get('emoji') or '') + ' ' if s.get('emoji') else ''}{s['heading']}", ""]
        if s.get("lede"):
            out += [f"*{s['lede']}*", ""]
        for it, e in items:
            status = f" — **{STATUS_LABEL[e['status']]}**" if e["status"] in STATUS_LABEL else ""
            link = e.get("ticket_url") or event_url(e, site_url)
            if s["layout"] == "compact":
                out.append(f"- **{when_label(e).replace(' · ', ', ')}** [{it.get('headline') or e['title']}]({link})"
                           f" · {e['venue']['name']} · {price_label(e['price'])}{status}")
                continue
            out += [f"### [{it.get('headline') or e['title']}]({link}){status}"]
            if it.get("headline"):
                out.append(f"*{e['title']}*  ")
            out += [f"**{details_line(e)}**", ""]
            if it.get("blurb"):
                out += [it["blurb"], ""]
            out += [f"[How we checked it]({event_url(e, site_url)})", ""]
        out.append("")
    out += ["---", "", "Every listing here was checked word for word against the venue's or ticket seller's own page "
            "before it went in. Plans change, so check the ticket page before you head out."]
    return "\n".join(out).rstrip() + "\n"


# ---------------------------------------------------------------- Buttondown (drafts only)

def buttondown_draft(issue: dict, events: dict[str, dict], api_key: str, site_url: str = SITE_URL) -> dict:
    body = "<!-- buttondown-editor-mode: fancy -->\n" + render_html(issue, events, site_url)
    req = urllib.request.Request(
        "https://api.buttondown.com/v1/emails",
        data=json.dumps({"subject": issue["subject"], "body": body, "description": issue["preheader"],
                         "status": "draft", "metadata": {"bgl_issue": issue["id"]}}).encode(),
        headers={"Authorization": f"Token {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode() or "{}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("week", help="the events an issue can use, as JSON")
    w.add_argument("issue_date", type=dt.date.fromisoformat)
    r = sub.add_parser("render", help="render an issue")
    r.add_argument("issue", type=Path)
    r.add_argument("--format", choices=["html", "md"], default="html")
    r.add_argument("--out", type=Path)
    b = sub.add_parser("buttondown-draft", help="create a draft in Buttondown (never sends)")
    b.add_argument("issue", type=Path)
    args = ap.parse_args(argv)

    if args.cmd == "week":
        print(json.dumps(week(args.issue_date), indent=2, ensure_ascii=False))
        return 0
    issue, events = read(args.issue), load_events()
    if args.cmd == "render":
        text = render_html(issue, events) if args.format == "html" else render_markdown(issue, events)
        if args.out:
            args.out.write_text(text, encoding="utf-8")
            print(f"wrote {args.out}")
        else:
            sys.stdout.write(text)
        return 0
    key = os.environ.get("BUTTONDOWN_API_KEY")
    if not key:
        print("BUTTONDOWN_API_KEY is not set; nothing sent to Buttondown.")
        return 0
    if not issue.get("intro"):
        print("This issue has no editor's letter yet; not creating a draft.")
        return 1
    try:
        res = buttondown_draft(issue, events, key)
    except urllib.error.HTTPError as e:
        print(f"Buttondown said {e.code}: {e.read().decode(errors='replace')[:500]}")
        return 1
    print(f"Draft created in Buttondown: {res.get('id', '(no id returned)')} — open Buttondown to read and send it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
