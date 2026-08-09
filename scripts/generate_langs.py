#!/usr/bin/env python3
"""Fetch per-repo language bytes via the GitHub GraphQL API (stdlib only) and
render langs.svg in the shared visual language.
"""
import json
import os
import sys
import urllib.request

from svg_theme import DIM, INK, RULE, esc, svg_close, svg_open

API_URL = "https://api.github.com/graphql"

QUERY = """
query($login: String!) {
  user(login: $login) {
    repositories(privacy: PUBLIC, first: 100, ownerAffiliations: [OWNER], isFork: false) {
      nodes {
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}
"""


def graphql(token: str, login: str) -> dict:
    body = json.dumps({"query": QUERY, "variables": {"login": login}}).encode()
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


def main():
    token = os.environ["GITHUB_TOKEN"]
    login = os.environ["GH_LOGIN"]

    data = graphql(token, login)

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

    with open(os.path.join(out_dir, "langs.svg"), "w") as f:
        f.write(build_langs_svg(languages))

    print(f"languages={[l['name'] for l in languages]}", file=sys.stderr)


if __name__ == "__main__":
    main()
