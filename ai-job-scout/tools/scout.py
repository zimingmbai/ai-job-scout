#!/usr/bin/env python3
"""Find AI and innovation roles in Singapore and update data/jobs.json and data/runs.json.

    python3 tools/scout.py                       fetch, merge, write, print a summary
    python3 tools/scout.py --linkedin FILE        also merge roles read from LinkedIn alert emails
    python3 tools/scout.py --dry-run              fetch and print, write nothing
    python3 tools/scout.py --mark-emailed sent    record in the last run whether the email went (sent|draft|none)
"""
import argparse
import datetime
import json
import pathlib
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
JOBS = ROOT / "data" / "jobs.json"
RUNS = ROOT / "data" / "runs.json"
CONFIG = ROOT / "config.json"
SGT = datetime.timezone(datetime.timedelta(hours=8))
UA = "MGMT6110-ai-job-scout (class exercise; one run a day)"


def now():
    return datetime.datetime.now(SGT).replace(microsecond=0)


def load(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def save(path, data):
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    json.loads(text)
    path.write_text(text, encoding="utf-8")


def get_json(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def explain(err):
    if isinstance(err, urllib.error.HTTPError):
        if err.code == 403:
            return "HTTP 403: blocked. Add this host under Custom network access in the routine's environment."
        return "HTTP %s" % err.code
    text = str(getattr(err, "reason", err))
    if "403" in text or "Tunnel" in text:
        return "blocked by the cloud network (403). Add this host under Custom network access."
    return text[:160]


def word_pattern(words):
    parts = []
    for w in words:
        w = w.strip()
        if not w:
            continue
        tail = r"(?![A-Za-z])" if len(w) <= 3 else ""
        parts.append(r"(?<![A-Za-z])" + re.escape(w) + tail)
    return re.compile("|".join(parts), re.I) if parts else None


def matches(pattern, title):
    if not pattern:
        return []
    seen = []
    for m in pattern.finditer(title):
        hit = m.group(0)
        if hit.lower() not in [s.lower() for s in seen]:
            seen.append(hit)
    return seen


def level_of(title):
    t = title.lower()
    if re.search(r"\b(intern|internship|graduate|trainee|associate)\b", t):
        return "Entry"
    if re.search(r"\b(senior|sr\.?|lead|principal|head|director|vp|vice president|chief)\b", t):
        return "Senior"
    if re.search(r"\bmanager\b", t):
        return "Mid"
    return "Not stated"


def money(lo, hi, period):
    if not lo and not hi:
        return None
    per = {"Monthly": "a month", "Annually": "a year", "Yearly": "a year", "Hourly": "an hour"}.get(period or "", "")
    fmt = lambda v: "S$" + format(int(v), ",")
    if lo and hi and lo != hi:
        text = "%s to %s" % (fmt(lo), fmt(hi))
    else:
        text = fmt(lo or hi)
    return (text + " " + per).strip()


def from_mcf(term, checked, errors):
    url = ("https://api.mycareersfuture.gov.sg/v2/jobs?search=%s&limit=40&page=0&sortBy=new_posting_date"
           % urllib.parse.quote(term))
    try:
        data = get_json(url)
    except Exception as err:
        errors.append("MyCareersFuture '%s': %s" % (term, explain(err)))
        checked.append({"source": "MyCareersFuture", "query": term, "results": 0})
        return []
    rows = []
    for r in data.get("results", []):
        sal = r.get("salary") or {}
        meta = r.get("metadata") or {}
        rows.append({
            "id": "mcf-" + str(r.get("uuid")),
            "title": (r.get("title") or "").strip(),
            "company": ((r.get("postedCompany") or {}).get("name") or "").strip(),
            "location": "Singapore",
            "source": "MyCareersFuture",
            "url": meta.get("jobDetailsUrl") or "",
            "posted": meta.get("newPostingDate"),
            "salary": money(sal.get("minimum"), sal.get("maximum"), ((sal.get("type") or {}).get("salaryType"))),
        })
    checked.append({"source": "MyCareersFuture", "query": term, "results": len(rows)})
    return rows


def from_greenhouse(board, place, checked, errors):
    try:
        data = get_json("https://boards-api.greenhouse.io/v1/boards/%s/jobs" % urllib.parse.quote(board))
    except Exception as err:
        errors.append("Greenhouse '%s': %s" % (board, explain(err)))
        checked.append({"source": "Company site", "query": "greenhouse:" + board, "results": 0})
        return []
    rows = []
    for j in data.get("jobs", []):
        loc = ((j.get("location") or {}).get("name") or "")
        if place.lower() not in loc.lower():
            continue
        rows.append({
            "id": "gh-%s-%s" % (board, j.get("id")),
            "title": (j.get("title") or "").strip(),
            "company": (j.get("company_name") or board.title()).strip(),
            "location": loc,
            "source": "Company site",
            "url": j.get("absolute_url") or "",
            "posted": (j.get("first_published") or j.get("updated_at") or "")[:10] or None,
            "salary": None,
        })
    checked.append({"source": "Company site", "query": "greenhouse:" + board, "results": len(rows)})
    return rows


def from_lever(board, place, checked, errors):
    try:
        data = get_json("https://api.lever.co/v0/postings/%s?mode=json" % urllib.parse.quote(board))
    except Exception as err:
        errors.append("Lever '%s': %s" % (board, explain(err)))
        checked.append({"source": "Company site", "query": "lever:" + board, "results": 0})
        return []
    rows = []
    for p in data if isinstance(data, list) else []:
        cat = p.get("categories") or {}
        places = " ".join([cat.get("location") or ""] + list(cat.get("allLocations") or []))
        if place.lower() not in places.lower():
            continue
        created = p.get("createdAt")
        posted = (datetime.datetime.fromtimestamp(created / 1000, SGT).date().isoformat() if created else None)
        rows.append({
            "id": "lv-%s-%s" % (board, p.get("id")),
            "title": (p.get("text") or "").strip(),
            "company": board.title(),
            "location": cat.get("location") or place,
            "source": "Company site",
            "url": p.get("hostedUrl") or "",
            "posted": posted,
            "salary": None,
        })
    checked.append({"source": "Company site", "query": "lever:" + board, "results": len(rows)})
    return rows


def from_linkedin_file(path, checked, errors):
    try:
        items = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except Exception as err:
        errors.append("LinkedIn alert file: %s" % err)
        return []
    rows = []
    for it in items if isinstance(items, list) else []:
        link = (it.get("url") or "").strip()
        num = re.search(r"(\d{6,})", link)
        rows.append({
            "id": "li-" + (num.group(1) if num else re.sub(r"\W+", "-", (it.get("title", "") + it.get("company", "")).lower())[:60]),
            "title": (it.get("title") or "").strip(),
            "company": (it.get("company") or "").strip(),
            "location": (it.get("location") or "Singapore").strip(),
            "source": "LinkedIn",
            "url": link,
            "posted": it.get("posted"),
            "salary": None,
        })
    checked.append({"source": "LinkedIn (job alert emails)", "query": "alerts", "results": len(rows)})
    return rows


def from_manual_file(path, checked, errors):
    try:
        items = json.loads(path.read_text(encoding="utf-8"))
    except Exception as err:
        errors.append("data/manual_roles.json: %s" % err)
        return []
    rows = []
    for it in items if isinstance(items, list) else []:
        title = (it.get("title") or "").strip()
        rows.append({
            "id": "man-" + re.sub(r"[^a-z0-9]+", "-", (title + " " + (it.get("company") or "")).lower()).strip("-")[:70],
            "title": title,
            "company": (it.get("company") or "").strip(),
            "location": (it.get("location") or "Singapore").strip(),
            "source": "Added by hand",
            "url": (it.get("url") or "").strip(),
            "posted": it.get("posted"),
            "salary": None,
        })
    checked.append({"source": "Added by hand", "query": "data/manual_roles.json", "results": len(rows)})
    return rows


def run(args):
    cfg = load(CONFIG, {})
    place = cfg.get("company_location_word", "Singapore")
    ai_rx = word_pattern(cfg.get("ai_title_words", []))
    inn_rx = word_pattern(cfg.get("innovation_title_words", []))
    checked, errors, rows = [], [], []

    for term in cfg.get("mycareersfuture_terms", []):
        rows += from_mcf(term, checked, errors)
    for board in cfg.get("greenhouse_boards", []):
        rows += from_greenhouse(board, place, checked, errors)
    for board in cfg.get("lever_boards", []):
        rows += from_lever(board, place, checked, errors)
    if args.linkedin:
        rows += from_linkedin_file(args.linkedin, checked, errors)
    manual = ROOT / "data" / "manual_roles.json"
    if manual.exists():
        rows += from_manual_file(manual, checked, errors)

    counted = {}
    for r in rows:
        if not r["title"] or not r["url"].startswith(("https://", "http://")):
            continue
        ai, inn = matches(ai_rx, r["title"]), matches(inn_rx, r["title"])
        if not ai and not inn:
            continue
        r["track"] = "AI and innovation" if ai and inn else ("AI" if ai else "Innovation")
        r["level"] = level_of(r["title"])
        r["why"] = "title has " + " and ".join('"%s"' % w for w in (ai + inn)[:3])
        counted.setdefault(r["id"], r)

    t = now()
    stamp = t.isoformat()
    jobs_doc = load(JOBS, {"meta": {}, "jobs": []})
    runs_doc = load(RUNS, {"runs": []})
    known = {j["id"]: j for j in jobs_doc.get("jobs", [])}
    new = []
    for jid, r in counted.items():
        if jid in known:
            known[jid]["last_seen"] = stamp
        else:
            r["first_seen"] = r["last_seen"] = stamp
            known[jid] = r
            new.append(r)

    keep_days = int(cfg.get("forget_after_days", 45))
    cutoff = t - datetime.timedelta(days=keep_days)
    kept = [j for j in known.values()
            if datetime.datetime.fromisoformat(j.get("last_seen", stamp)) >= cutoff]
    kept.sort(key=lambda j: (j.get("first_seen", ""), j.get("posted") or ""), reverse=True)

    note = "; ".join(errors) if errors else "All sources answered."
    if args.linkedin is None and cfg.get("read_linkedin_alert_emails"):
        note += " No LinkedIn alert file this run."
    entry = {"run_at": stamp, "checked": checked, "found": len(counted), "new": len(new),
             "kept": len(kept), "emailed": False, "note": note}

    summary = {"run_at": stamp, "found": len(counted), "new_count": len(new), "kept": len(kept),
               "errors": errors, "checked": checked,
               "new": [{k: r[k] for k in ("title", "company", "source", "url", "track", "level")}
                       for r in sorted(new, key=lambda r: r.get("posted") or "", reverse=True)]}
    if args.dry_run:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    jobs_doc.setdefault("meta", {})["updated_at"] = stamp
    jobs_doc["jobs"] = kept
    runs_doc.setdefault("runs", []).append(entry)
    save(JOBS, jobs_doc)
    save(RUNS, runs_doc)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def mark_emailed(state):
    runs_doc = load(RUNS, {"runs": []})
    if not runs_doc.get("runs"):
        print("No run to mark.")
        return 1
    last = runs_doc["runs"][-1]
    last["emailed"] = state == "sent"
    if state == "draft":
        last["note"] = (last.get("note", "") + " Email saved as a draft (sending was not allowed).").strip()
    save(RUNS, runs_doc)
    print("Marked the last run: emailed=%s" % last["emailed"])
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--linkedin", help="JSON list of roles read from LinkedIn alert emails")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--mark-emailed", choices=["sent", "draft", "none"])
    a = ap.parse_args()
    sys.exit(mark_emailed(a.mark_emailed) if a.mark_emailed else run(a))
