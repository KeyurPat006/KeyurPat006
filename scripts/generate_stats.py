#!/usr/bin/env python3
"""Fetch contribution/language data via the GitHub GraphQL API (stdlib only) and
render stats.svg, streak.svg, langs.svg, year.svg in the shared visual language.
"""
import json
import math
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

from svg_theme import DIM, INK, RAMP, RULE, esc, ramp_index, svg_close, svg_open

API_URL = "https://api.github.com/graphql"

QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays { date contributionCount }
        }
      }
    }
    repositories(privacy: PUBLIC, first: 100, ownerAffiliations: [OWNER], isFork: false) {
      nodes {
        name
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}
"""


def graphql(token: str, login: str, dt_from: str, dt_to: str) -> dict:
    body = json.dumps(
        {"query": QUERY, "variables": {"login": login, "from": dt_from, "to": dt_to}}
    ).encode()
    req = urllib.request.Request(
        API_URL,
        data=body,
        headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "profile-stats-script",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.loads(resp.read())
    if "errors" in payload:
        raise SystemExit(f"GraphQL error: {payload['errors']}")
    return payload["data"]["user"]


def utc_window(now: datetime) -> tuple[str, str]:
    today = now.date()
    start = datetime.combine(today - timedelta(days=364), datetime.min.time(), tzinfo=timezone.utc)
    end = datetime.combine(today, datetime.max.time().replace(microsecond=0), tzinfo=timezone.utc)
    return start.isoformat().replace("+00:00", "Z"), end.isoformat().replace("+00:00", "Z")


def compute_streaks(days: list[dict], today_str: str) -> dict:
    current = 0
    i = len(days) - 1
    if i >= 0 and days[i]["date"] == today_str and days[i]["contributionCount"] == 0:
        i -= 1
    current_end = days[i]["date"] if i >= 0 else None
    while i >= 0 and days[i]["contributionCount"] > 0:
        current += 1
        i -= 1
    current_start = days[i + 1]["date"] if current else None

    longest = 0
    longest_start = longest_end = None
    run = 0
    run_start = None
    for d in days:
        if d["contributionCount"] > 0:
            if run == 0:
                run_start = d["date"]
            run += 1
            if run > longest:
                longest = run
                longest_start = run_start
                longest_end = d["date"]
        else:
            run = 0

    return {
        "current": current,
        "current_start": current_start,
        "current_end": current_end,
        "longest": longest,
        "longest_start": longest_start,
        "longest_end": longest_end,
    }


def fmt_range(a: str, b: str) -> str:
    if not a or not b:
        return ""
    da = datetime.strptime(a, "%Y-%m-%d")
    db = datetime.strptime(b, "%Y-%m-%d")
    if da.year == db.year:
        return f"{da:%b %-d} – {db:%b %-d, %Y}"
    return f"{da:%b %-d, %Y} – {db:%b %-d, %Y}"


def build_stats_svg(total: int, weekly: list[int]) -> str:
    w, h = 480.0, 150.0
    pad = 20.0
    s = [svg_open(w, h, font_subset="basic")]
    s.append(f'<text x="{pad}" y="46" font-size="34" font-weight="700" fill="{INK}">{total:,}</text>')
    s.append(f'<text x="{pad}" y="66" font-size="12" fill="{DIM}">contributions in the last year</text>')

    chart_x, chart_y, chart_w, chart_h = pad, 88.0, w - 2 * pad, 42.0
    vmax = max(weekly) if weekly and max(weekly) > 0 else 1
    n = len(weekly)
    step = chart_w / max(n - 1, 1)
    pts = []
    for i, v in enumerate(weekly):
        x = chart_x + i * step
        y = chart_y + chart_h - (v / vmax) * chart_h
        pts.append((x, y))
    poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area = f"{chart_x:.1f},{chart_y + chart_h:.1f} " + poly + f" {chart_x + chart_w:.1f},{chart_y + chart_h:.1f}"
    s.append(f'<polygon points="{area}" fill="{INK}" opacity="0.08"/>')
    s.append(f'<polyline points="{poly}" fill="none" stroke="{INK}" stroke-width="1.4"/>')
    s.append(
        f'<line x1="{chart_x}" y1="{chart_y + chart_h}" x2="{chart_x + chart_w}" '
        f'y2="{chart_y + chart_h}" stroke="{RULE}" stroke-width="1"/>'
    )
    s.append(f'<text x="{chart_x}" y="{chart_y + chart_h + 16}" font-size="10" fill="{DIM}">52 weeks ago</text>')
    s.append(
        f'<text x="{chart_x + chart_w}" y="{chart_y + chart_h + 16}" font-size="10" '
        f'fill="{DIM}" text-anchor="end">this week</text>'
    )
    s.append(svg_close())
    return "".join(s)


def build_streak_svg(streaks: dict) -> str:
    w, h = 480.0, 120.0
    pad = 20.0
    s = [svg_open(w, h, font_subset="basic")]

    def block(x, label, value, subrange):
        out = [f'<text x="{x}" y="40" font-size="30" font-weight="700" fill="{INK}">{value}</text>']
        out.append(f'<text x="{x}" y="58" font-size="12" fill="{DIM}">{esc(label)}</text>')
        if subrange:
            out.append(f'<text x="{x}" y="76" font-size="10" fill="{DIM}">{esc(subrange)}</text>')
        return "".join(out)

    s.append(block(pad, "day current streak", streaks["current"], fmt_range(streaks["current_start"], streaks["current_end"])))
    mid = w / 2 + 10
    s.append(f'<line x1="{w/2}" y1="20" x2="{w/2}" y2="90" stroke="{RULE}" stroke-width="1"/>')
    s.append(block(mid, "day longest streak", streaks["longest"], fmt_range(streaks["longest_start"], streaks["longest_end"])))
    s.append(svg_close())
    return "".join(s)


def build_langs_svg(languages: list[dict]) -> str:
    w = 480.0
    row_h = 28.0
    pad = 20.0
    top = languages[:6]
    h = pad * 2 + row_h * len(top)
    total_bytes = sum(l["bytes"] for l in top) or 1
    s = [svg_open(w, h, font_subset="basic")]
    bar_x = pad + 110
    bar_w = w - bar_x - pad - 50
    for i, lang in enumerate(top):
        y = pad + i * row_h
        frac = lang["bytes"] / total_bytes
        s.append(f'<text x="{pad}" y="{y+14}" font-size="12" fill="{INK}">{esc(lang["name"])}</text>')
        s.append(f'<rect x="{bar_x}" y="{y+4}" width="{bar_w}" height="10" fill="{RULE}"/>')
        s.append(f'<rect x="{bar_x}" y="{y+4}" width="{bar_w*frac:.1f}" height="10" fill="{lang["color"] or INK}"/>')
        pct = frac * 100
        s.append(
            f'<text x="{w-pad}" y="{y+14}" font-size="11" fill="{DIM}" text-anchor="end">'
            f'{pct:.1f}% · {lang["repos"]} repo{"s" if lang["repos"] != 1 else ""}</text>'
        )
    s.append(svg_close())
    return "".join(s)


def build_year_svg(days: list[dict]) -> str:
    weeks: list[list[dict]] = []
    cur: list[dict] = []
    for d in days:
        dow = datetime.strptime(d["date"], "%Y-%m-%d").weekday()  # Mon=0..Sun=6
        dow = (dow + 1) % 7  # convert to Sun=0..Sat=6 to match GitHub's grid
        if dow == 0 and cur:
            weeks.append(cur)
            cur = []
        cur.append(d)
    if cur:
        weeks.append(cur)

    counts = [d["contributionCount"] for d in days]
    vmax = max(counts) if counts else 1
    vmax = max(vmax, 1)

    char_w, row_h = 8.0, 10.0
    pad = 16.0
    w = pad * 2 + len(weeks) * char_w
    h = pad * 2 + 7 * row_h
    s = [svg_open(w, h, font_subset="ramp")]
    s.append(f'<style>text{{font-size:9px; fill:{INK};}}</style>')
    for wi, week in enumerate(weeks):
        for d in week:
            dow = datetime.strptime(d["date"], "%Y-%m-%d").weekday()
            dow = (dow + 1) % 7
            idx = ramp_index(d["contributionCount"], vmax)
            ch = RAMP[idx]
            x = pad + wi * char_w
            y = pad + dow * row_h + row_h * 0.8
            s.append(f'<text x="{x:.1f}" y="{y:.1f}">{esc(ch)}</text>')
    s.append(svg_close())
    return "".join(s)


def main():
    token = os.environ["GITHUB_TOKEN"]
    login = os.environ["GH_LOGIN"]

    now = datetime.now(timezone.utc)
    dt_from, dt_to = utc_window(now)
    today_str = now.date().isoformat()

    data = graphql(token, login, dt_from, dt_to)

    calendar = data["contributionsCollection"]["contributionCalendar"]
    total = calendar["totalContributions"]
    weeks_raw = calendar["weeks"]
    weekly_totals = [sum(d["contributionCount"] for d in wk["contributionDays"]) for wk in weeks_raw]
    days = [d for wk in weeks_raw for d in wk["contributionDays"]]
    days.sort(key=lambda d: d["date"])

    streaks = compute_streaks(days, today_str)

    lang_agg: dict[str, dict] = {}
    for repo in data["repositories"]["nodes"]:
        seen_in_repo = set()
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            entry = lang_agg.setdefault(name, {"name": name, "bytes": 0, "color": edge["node"]["color"], "repos": 0})
            entry["bytes"] += edge["size"]
            if name not in seen_in_repo:
                entry["repos"] += 1
                seen_in_repo.add(name)
    languages = sorted(lang_agg.values(), key=lambda l: l["bytes"], reverse=True)

    out_dir = os.path.join(os.path.dirname(__file__), "..", "assets")
    os.makedirs(out_dir, exist_ok=True)

    with open(os.path.join(out_dir, "stats.svg"), "w") as f:
        f.write(build_stats_svg(total, weekly_totals))
    with open(os.path.join(out_dir, "streak.svg"), "w") as f:
        f.write(build_streak_svg(streaks))
    with open(os.path.join(out_dir, "langs.svg"), "w") as f:
        f.write(build_langs_svg(languages))
    with open(os.path.join(out_dir, "year.svg"), "w") as f:
        f.write(build_year_svg(days))

    print(f"total={total} current_streak={streaks['current']} longest_streak={streaks['longest']}", file=sys.stderr)


if __name__ == "__main__":
    main()
