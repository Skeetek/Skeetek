#!/usr/bin/env python3
"""Render a self-hosted GitHub stats card as SVG.

Avoids depending on third-party stats services (the public github-readme-stats
instance is frequently paused/rate-limited). Runs in CI and writes dist/stats.svg.
"""
import json
import os
import sys
import urllib.error
import urllib.request
from xml.sax.saxutils import escape

USER = os.environ.get("GH_USER") or sys.exit("GH_USER not set")
TOKEN = os.environ.get("GH_TOKEN") or sys.exit("GH_TOKEN not set")
OUT = os.environ.get("OUT", "dist/stats.svg")

QUERY = """
query($login: String!) {
  user(login: $login) {
    followers { totalCount }
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
    }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false) {
      totalCount
      nodes {
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}
"""


def fetch():
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": USER}}).encode(),
        headers={
            "Authorization": f"bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": f"{USER}-profile-stats",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        payload = json.load(r)
    if "errors" in payload:
        sys.exit(f"GraphQL errors: {payload['errors']}")
    user = (payload.get("data") or {}).get("user")
    if not user:
        sys.exit("no user in GraphQL response")
    return user


def human(n):
    if n >= 1000:
        return f"{n/1000:.1f}".rstrip("0").rstrip(".") + "k"
    return str(n)


def build(user):
    contrib = user["contributionsCollection"]
    repos = user["repositories"]["nodes"]

    stars = sum(r["stargazerCount"] for r in repos)
    stats = [
        ("COMMITS",   human(contrib["totalCommitContributions"]),        "#22d3ee"),
        ("PULL REQS", human(contrib["totalPullRequestContributions"]),   "#a855f7"),
        ("REPOS",     human(user["repositories"]["totalCount"]),         "#4ade80"),
        ("STARS",     human(stars),                                      "#eab308"),
    ]

    # aggregate language bytes across all owned, non-fork repos
    totals, colors = {}, {}
    for r in repos:
        for e in r["languages"]["edges"]:
            name = e["node"]["name"]
            totals[name] = totals.get(name, 0) + e["size"]
            colors[name] = e["node"]["color"] or "#94a3b8"
    top = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)[:5]
    grand = sum(totals.values()) or 1

    W, H = 840, 252
    p = []
    p.append(
        f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
        f'role="img" aria-label="GitHub statistics for {escape(USER)}">'
    )
    p.append("""<defs><style>
    .h  { font-family: "SF Mono", Consolas, "Courier New", monospace; font-size: 13px; letter-spacing: 2.5px; fill: #64748b; }
    .k  { font-family: "SF Mono", Consolas, "Courier New", monospace; font-size: 11px; letter-spacing: 1.6px; fill: #64748b; }
    .v  { font-family: Arial, Helvetica, sans-serif; font-weight: 800; font-size: 27px; fill: #e2e8f0; }
    .l  { font-family: "SF Mono", Consolas, "Courier New", monospace; font-size: 13px; fill: #e2e8f0; }
    .pc { font-family: "SF Mono", Consolas, "Courier New", monospace; font-size: 12px; fill: #94a3b8; }
    @keyframes breathe { 0%,100% { opacity:.18 } 50% { opacity:.5 } }
    @keyframes drift   { 0%,100% { transform: translate(0,0) } 50% { transform: translate(20px,-12px) } }
    @keyframes drift2  { 0%,100% { transform: translate(0,0) } 50% { transform: translate(-16px,10px) } }
    .gl { animation: breathe 3.6s ease-in-out infinite; }
    .o1 { animation: drift 15s ease-in-out infinite; }
    .o2 { animation: drift2 18s ease-in-out infinite; }
    </style>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#0a0e17"/><stop offset="55%" stop-color="#0d1220"/><stop offset="100%" stop-color="#0a0f1c"/>
    </linearGradient>
    <radialGradient id="gA" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#22d3ee" stop-opacity=".13"/><stop offset="100%" stop-color="#22d3ee" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="gB" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#a855f7" stop-opacity=".15"/><stop offset="100%" stop-color="#a855f7" stop-opacity="0"/>
    </radialGradient>
    <clipPath id="cc"><rect width="840" height="252" rx="22"/></clipPath>
    </defs>""")

    p.append('<g clip-path="url(#cc)">')
    p.append(f'<rect width="{W}" height="{H}" fill="url(#bg)"/>')
    p.append('<circle class="o1" cx="60" cy="10" r="170" fill="url(#gA)"/>')
    p.append(f'<circle class="o2" cx="790" cy="{H}" r="190" fill="url(#gB)"/>')
    p.append(f'<rect width="{W}" height="{H}" rx="22" fill="none" stroke="#94a3b8" stroke-opacity=".13" stroke-width="1.5"/>')

    # ── left: stat tiles ──
    p.append('<rect x="26" y="30" width="3" height="18" rx="1.5" fill="#22d3ee"/>')
    p.append('<text class="h" x="40" y="44">ACTIVITY</text>')
    tw, th, gx, gy = 186, 74, 17, 14
    for i, (label, value, color) in enumerate(stats):
        x = 26 + (i % 2) * (tw + gx)
        y = 62 + (i // 2) * (th + gy)
        p.append(f'<g transform="translate({x},{y})">')
        p.append(f'<rect class="gl" width="{tw}" height="{th}" rx="14" fill="none" stroke="{color}" stroke-width="2" opacity=".3"/>')
        p.append(f'<rect width="{tw}" height="{th}" rx="14" fill="#ffffff" fill-opacity=".04" stroke="{color}" stroke-opacity=".4"/>')
        p.append(f'<circle cx="20" cy="22" r="4" fill="{color}"/>')
        p.append(f'<text class="k" x="32" y="26">{escape(label)}</text>')
        p.append(f'<text class="v" x="20" y="58">{escape(value)}</text>')
        p.append("</g>")

    # ── right: top languages ──
    p.append('<rect x="440" y="30" width="3" height="18" rx="1.5" fill="#a855f7"/>')
    p.append('<text class="h" x="454" y="44">TOP LANGUAGES</text>')
    bx0, bx1 = 566, 772
    for i, (name, size) in enumerate(top):
        y = 70 + i * 32
        pct = size / grand * 100
        col = colors[name]
        disp = name if len(name) <= 11 else name[:10] + "…"
        p.append(f'<text class="l" x="440" y="{y + 4}">{escape(disp)}</text>')
        p.append(f'<rect x="{bx0}" y="{y - 4}" width="{bx1 - bx0}" height="7" rx="3.5" fill="#ffffff" fill-opacity=".07"/>')
        w = max(4, round((bx1 - bx0) * pct / 100))
        p.append(f'<rect x="{bx0}" y="{y - 4}" width="{w}" height="7" rx="3.5" fill="{col}"/>')
        p.append(f'<text class="pc" x="814" y="{y + 4}" text-anchor="end">{pct:.1f}%</text>')

    if not top:
        p.append('<text class="pc" x="440" y="80">no public language data</text>')

    p.append("</g></svg>")
    return "\n".join(p)


def main():
    try:
        user = fetch()
    except urllib.error.HTTPError as e:
        sys.exit(f"GitHub API HTTP {e.code}: {e.read()[:300]!r}")
    svg = build(user)
    os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"wrote {OUT} ({len(svg)} bytes)")


if __name__ == "__main__":
    main()
