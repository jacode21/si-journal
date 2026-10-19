#!/usr/bin/env python3
"""SI Journal static site generator.

Reads:  brand/site.json            (name, tagline, disclaimer, base_url ...)
        brand/about.md             (optional About page body)
        issues/YYYY-MM-DD/         (one folder per issue)
            lead-essay.md          required; frontmatter: title, dek, date, issue, author, status
            briefs.md              optional
            primer.md              optional
            signal.md              optional (else a "## Signal to watch" section in lead-essay.md)
            disclaimer.md          optional (else a "## Disclaimer" section in lead-essay.md, else site default)
Writes: docs/  (served by GitHub Pages from main:/docs)

Ignored: research/, stories/, primers/, curriculum.md, anything else.
"""
import datetime as dt
import email.utils
import hashlib
import html
import json
import math
import random
import re
import shutil
import sys
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parent
import os
OUT = Path(os.environ.get("SI_OUT", ROOT / "docs"))
ISSUES = Path(os.environ.get("SI_ISSUES", ROOT / "issues"))
BRAND = ROOT / "brand"
ASSETS = ROOT / "site" / "assets"
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

INK = "#1F1A15"
ACCENT_DEFAULT = "#A8482A"
OLIVE = "#5E6B3A"


# ---------------------------------------------------------------- helpers
def load_site():
    site = json.loads((BRAND / "site.json").read_text(encoding="utf-8"))
    site.setdefault("accent", ACCENT_DEFAULT)
    site["base_url"] = site.get("base_url", "/").rstrip("/") + "/"
    return site


def parse_frontmatter(text):
    meta, body = {}, text
    if text.startswith("---"):
        parts = text.split("\n")
        end = None
        for i in range(1, len(parts)):
            if parts[i].strip() == "---":
                end = i
                break
        if end:
            for line in parts[1:end]:
                if ":" in line and not line.lstrip().startswith("#"):
                    k, v = line.split(":", 1)
                    v = v.strip()
                    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
                        v = v[1:-1]
                    meta[k.strip().lower()] = v
            body = "\n".join(parts[end + 1:])
    return meta, body.strip("\n")


TAGLINE_RE = re.compile(r"<p>(?:<(em|strong)>)?\s*(?:Tags?|Topics?)\s*:\s*([^<]{1,120}?)\s*(?:</\1>)?</p>", re.I)


def md(text):
    out = markdown.markdown(
        text, extensions=["extra", "smarty", "sane_lists", "toc"], output_format="html5"
    )
    # "Tags: AI, Energy" lines inside briefs/signal become quiet mono labels
    return TAGLINE_RE.sub(lambda m: '<p class="inline-tags" data-pagefind-ignore><span class="visually-hidden">Topics: </span>'
                          + " ".join("[" + esc(t.strip()) + "]" for t in m.group(2).split(",") if t.strip()) + "</p>", out)


def esc(s):
    return html.escape(str(s or ""), quote=True)


def read(path):
    return path.read_text(encoding="utf-8") if path.exists() else None


SECTION_PATTERNS = {
    "signal": re.compile(r"^signal to watch", re.I),
    "disclaimer": re.compile(r"^(disclaimer|not investment advice|important( note)?|disclosures?)", re.I),
    "primer": re.compile(r"^(the )?(si primer|si 101)", re.I),
    "briefs": re.compile(r"^(the )?briefs?$", re.I),
    "horizon": re.compile(r"^(what (this|it) (looks|could look|might look) like )?by (19|20)\d\d\b", re.I),
    "short": re.compile(r"^(the )?short version|^tl;?dr", re.I),
}


def split_sections(body):
    """Pull '## Signal to watch' / '## Disclaimer' etc. out of a markdown body."""
    lines = body.split("\n")
    found, keep, cur, buf = {}, [], None, []
    in_fence = False

    def flush():
        if cur:
            found[cur[0]] = (cur[1], "\n".join(buf).strip())

    for line in lines:
        if line.strip().startswith("```"):
            in_fence = not in_fence
        m = re.match(r"^(#{1,2})\s+(.*?)\s*#*\s*$", line) if not in_fence else None
        if m:
            heading = re.sub(r"[*_:]", "", m.group(2)).strip()
            key = next((k for k, p in SECTION_PATTERNS.items() if p.match(heading)), None)
            if key:
                flush()
                cur, buf = (key, m.group(2).strip(" *_")), []
                continue
            elif cur:
                flush()
                cur, buf = None, []
        if cur and cur[0] == "short" and line.strip() and not re.match(r"^\s*(?:[-*+]|\d+[.)])\s+|^\s{2,}\S", line) \
                and any(re.match(r"^\s*(?:[-*+]|\d+[.)])\s+", x) for x in buf):
            flush()  # the short version ends where the bullet list ends
            cur, buf = None, []
        if cur:
            buf.append(line)
        else:
            keep.append(line)
    flush()
    return "\n".join(keep).strip(), found


def strip_leading_h1(body):
    m = re.match(r"^\s*#\s+(.+?)\s*\n", body + "\n")
    if m:
        return m.group(1).strip(), body[m.end():].strip()
    return None, body


def parse_tags(v):
    v = v.strip().strip("[]")
    return [t.strip().strip("\"'") for t in v.split(",") if t.strip().strip("\"'")]


def tags_html(tags, filter_attr=False):
    if not tags:
        return ""
    attr = ' data-pagefind-filter="topic"' if filter_attr else ""
    return '<ul class="tags" aria-label="Topics" data-pagefind-ignore>' + "".join(f"<li{attr}>{esc(t)}</li>" for t in tags) + "</ul>"


def long_date(d):
    return f"{d:%A}, {d:%B} {d.day}, {d.year}"


# ---------------------------------------------------------------- motif
def motif_svg(seed_text, accent, size=200, title=None):
    """Deterministic ink-and-botanical sprig seeded by the issue date."""
    rnd = random.Random(int(hashlib.sha256(seed_text.encode()).hexdigest(), 16))
    W = H = 200
    f = lambda x: f"{x:.1f}"
    parts = []
    # faint wash + ensō arc
    cx, cy, r = 100 + rnd.uniform(-12, 12), 104 + rnd.uniform(-10, 10), rnd.uniform(62, 78)
    parts.append(f'<circle cx="{f(cx)}" cy="{f(cy)}" r="{f(r*0.92)}" fill="{accent}" opacity="0.07"/>')
    a0 = rnd.uniform(0, 2 * math.pi)
    sweep = rnd.uniform(1.55, 1.85) * math.pi
    pts = []
    for i in range(41):
        t = a0 + sweep * i / 40
        rr = r * (1 + 0.035 * math.sin(i * 0.7 + a0))
        pts.append((cx + rr * math.cos(t), cy + rr * math.sin(t)))
    d = "M" + " L".join(f"{f(x)} {f(y)}" for x, y in pts)
    parts.append(f'<path d="{d}" fill="none" stroke="{INK}" stroke-width="{f(rnd.uniform(1.1,1.8))}" stroke-linecap="round" opacity="0.55"/>')

    # stem: cubic bezier from base to tip
    x0, y0 = 100 + rnd.uniform(-18, 18), 184
    x3, y3 = 100 + rnd.uniform(-30, 30), 26 + rnd.uniform(0, 14)
    x1, y1 = x0 + rnd.uniform(-45, 45), 140
    x2, y2 = x3 + rnd.uniform(-45, 45), 70

    def bez(t):
        u = 1 - t
        x = u**3*x0 + 3*u*u*t*x1 + 3*u*t*t*x2 + t**3*x3
        y = u**3*y0 + 3*u*u*t*y1 + 3*u*t*t*y2 + t**3*y3
        dx = 3*u*u*(x1-x0) + 6*u*t*(x2-x1) + 3*t*t*(x3-x2)
        dy = 3*u*u*(y1-y0) + 6*u*t*(y2-y1) + 3*t*t*(y3-y2)
        return x, y, math.atan2(dy, dx)

    parts.append(f'<path d="M{f(x0)} {f(y0)} C{f(x1)} {f(y1)} {f(x2)} {f(y2)} {f(x3)} {f(y3)}" fill="none" stroke="{INK}" stroke-width="1.6" stroke-linecap="round"/>')

    n = rnd.randint(5, 9)
    side = rnd.choice([-1, 1])
    for i in range(n):
        t = 0.18 + 0.74 * i / max(n - 1, 1) + rnd.uniform(-0.03, 0.03)
        px, py, ang = bez(min(t, 0.97))
        side = -side if rnd.random() < 0.85 else side
        la = ang + side * math.radians(rnd.uniform(32, 62))
        L = rnd.uniform(22, 40) * (1.1 - 0.45 * t)
        Wd = L * rnd.uniform(0.26, 0.4)
        tx, ty = px + L*math.cos(la), py + L*math.sin(la)
        mx, my = px + 0.5*L*math.cos(la), py + 0.5*L*math.sin(la)
        nx, ny = -math.sin(la), math.cos(la)
        c1 = (mx + Wd*nx, my + Wd*ny)
        c2 = (mx - Wd*nx, my - Wd*ny)
        fill = accent
        op = rnd.uniform(0.28, 0.6)
        parts.append(
            f'<path d="M{f(px)} {f(py)} Q{f(c1[0])} {f(c1[1])} {f(tx)} {f(ty)} Q{f(c2[0])} {f(c2[1])} {f(px)} {f(py)}Z" '
            f'fill="{fill}" fill-opacity="{op:.2f}" stroke="{INK}" stroke-width="0.9" stroke-linejoin="round"/>'
        )
        parts.append(f'<path d="M{f(px)} {f(py)} L{f(mx + 0.4*L*math.cos(la))} {f(my + 0.4*L*math.sin(la))}" stroke="{INK}" stroke-width="0.6" opacity="0.7"/>')

    # berries / seed heads near the tip
    tx, ty, _ = bez(1.0)
    for _ in range(rnd.randint(3, 7)):
        a = rnd.uniform(-math.pi, 0)
        dd = rnd.uniform(4, 16)
        parts.append(f'<circle cx="{f(tx + dd*math.cos(a))}" cy="{f(ty + dd*math.sin(a))}" r="{f(rnd.uniform(1.4,3.4))}" fill="{accent}" opacity="0.85"/>')
    # ink spatter
    for _ in range(rnd.randint(4, 9)):
        parts.append(f'<circle cx="{f(rnd.uniform(20,180))}" cy="{f(rnd.uniform(20,185))}" r="{f(rnd.uniform(0.5,1.6))}" fill="{INK}" opacity="{rnd.uniform(0.25,0.6):.2f}"/>')

    label = esc(title or f"Botanical ink mark for {seed_text}")
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{size}" height="{size}" '
            f'role="img" aria-label="{label}"><title>{label}</title>' + "".join(parts) + "</svg>")


def fig(site, seed, accent, size, label):
    """Generative mark, only when brand/site.json sets "ornament": true."""
    if not site.get("ornament"):
        return ""
    return f'<figure class="motif">{motif_svg(seed, accent, size, label)}</figure>'


def mini(site, seed):
    if not site.get("ornament"):
        return ""
    return f'<span class="mini" aria-hidden="true">{motif_svg(seed, site["accent"], 56)}</span>'


# ---------------------------------------------------------------- issues
TOPICS = ["AI", "Compute", "Energy", "Bio", "Space", "Quantum", "Robotics", "Policy"]


def trace_svg(seed_text, accent, label, year=None, draw=True, compact=False):
    """Signature hero: a signal trace that keeps closing on a dashed asymptote.
    Seeded by headline + date, so every issue draws its own line. Scale shows the decade ahead."""
    rnd = random.Random(int(hashlib.sha256(seed_text.encode()).hexdigest(), 16))
    W, H, top, bot = (1000, 56, 8, 50) if compact else (1000, 120, 18, 108)
    amp_k = 0.5 if compact else 1.0
    n = 300
    spike = rnd.randint(int(n * 0.58), int(n * 0.86))
    rate = rnd.uniform(2.6, 3.6)
    f1, f2, ph = rnd.uniform(0.05, 0.11), rnd.uniform(0.32, 0.55), rnd.uniform(0, 6.3)
    pts = []
    for k in range(n + 1):
        t = k / n
        x = W * t
        env = 1 - math.exp(-rate * t)                      # always closer, never there
        base = bot - (bot - top - 5) * env
        noise = (3.4 * math.sin(k * f2 + ph) + 2.2 * math.sin(k * f1 * 3.1 + ph * 2)) * (1 - 0.6 * env) + rnd.gauss(0, 1.0)
        y = base + noise * 0.9 * amp_k
        dist = abs(k - spike)
        if dist < 7:
            y += (-1) ** k * (30 - dist * 4.0) * rnd.uniform(0.8, 1.0) * amp_k
        pts.append(f"{x:.1f},{max(2, min(H - 2, y)):.1f}")
    sx = W * spike / n
    sy = float(pts[spike].split(",")[1])
    svg = (f'<svg class="trace{" draw" if draw else ""}" viewBox="0 0 {W} {H}" role="img" aria-label="{esc(label)}">'
           f'<line x1="0" y1="{top}" x2="{W}" y2="{top}" stroke="currentColor" stroke-width="1" stroke-dasharray="2 5" opacity=".55" vector-effect="non-scaling-stroke"/>'
           f'<polyline pathLength="1" points="{" ".join(pts)}" fill="none" stroke="currentColor" vector-effect="non-scaling-stroke" stroke-linejoin="round" stroke-linecap="round"/>'
           f'<circle class="halo" cx="{sx:.1f}" cy="{sy:.1f}" r="7" vector-effect="non-scaling-stroke"/>'
           f'<circle class="spike" cx="{sx:.1f}" cy="{sy:.1f}" r="2.6"/></svg>')
    if year:
        y0 = int(year)
        svg += ('<div class="scale" aria-hidden="true">' + "".join(f"<span>{y0 + k}</span>" if k in (0, 5, 10) else "<span></span>" for k in range(11)) + "</div>")
    return f'<div class="hero-trace{" compact" if compact else ""}">{svg}</div>'


STATUS_ALIASES = {"approved": "approved", "approve": "approved", "published": "approved", "publish": "approved",
                  "review": "review", "in review": "review", "draft": "draft"}


def issue_status(d, meta):
    """issues/<date>/status (one word) wins over frontmatter `status:`; default is draft."""
    f = d / "status"
    raw = (f.read_text(encoding="utf-8").strip().split() or [""])[0] if f.exists() else meta.get("status", "draft")
    return STATUS_ALIASES.get(raw.strip().lower(), "draft")


def review_token(slug):
    secret_file = ROOT / ".review-secret"
    if not secret_file.exists():
        import secrets
        secret_file.write_text(secrets.token_hex(16))
    return hashlib.sha256((secret_file.read_text().strip() + slug).encode()).hexdigest()[:10]


def load_issues():
    issues = []
    if not ISSUES.exists():
        return issues
    for d in sorted(ISSUES.iterdir()):
        if not (d.is_dir() and (DATE_RE.match(d.name) or d.name.startswith("example-"))):
            continue
        single = (d / "issue.md").exists() and (d / "issue.md").read_text(encoding="utf-8").strip() != ""
        lead_txt = read(d / "issue.md") if single else read(d / "lead-essay.md")
        if not lead_txt or not lead_txt.strip():
            continue  # issue not written yet
        meta, body = parse_frontmatter(lead_txt)
        status = issue_status(d, meta)
        if status not in ("review", "approved"):
            print(f"  skip: {d.name} is {status}", file=sys.stderr)
            continue
        h1, body = strip_leading_h1(body)
        m_dek = re.match(r"^\s*([_*])([^\n]+?)\1\s*(\n\s*\n|$)", body)
        norm = lambda s: re.sub(r"\W+", "", (s or "").lower())
        if m_dek and (meta.get("dek") or meta.get("summary")) and norm(m_dek.group(2)) == norm(meta.get("dek") or meta.get("summary")):
            body = body[m_dek.end():]  # the italic standfirst repeats the frontmatter dek: show it once
        elif not (meta.get("dek") or meta.get("summary")):
            if m_dek:  # a lone italic line right under the headline is the dek
                meta["dek"] = m_dek.group(2).strip()
                body = body[m_dek.end():]
        body, extracted = split_sections(body)
        date = dt.date.fromisoformat(meta.get("date", d.name)[:10])
        issue = {
            "slug": d.name,
            "status": status,
            "example": d.name.startswith("example-") or meta.get("example", "").lower() in ("true", "yes"),
            "date": date,
            "title": meta.get("title") or meta.get("headline") or h1 or meta.get("subject") or f"Issue of {long_date(date)}",
            "dek": meta.get("dek") or meta.get("summary") or meta.get("preview") or "",
            "author": meta.get("author", ""),
            "number": meta.get("issue") or meta.get("number"),
            "lead_html": md(body),
            "tags": parse_tags(meta.get("tags") or meta.get("topics") or ""),
            "words": len(re.findall(r"\w+", body)),
            "sections": [],
        }

        def part(fname, key, default_title):
            txt = None if single else read(d / fname)
            if txt and txt.strip():
                m, b = parse_frontmatter(txt)
                h, b = strip_leading_h1(b)
                b2, ex = split_sections(b)
                # a briefs/primer file may itself carry a signal/disclaimer tail
                for k, v in ex.items():
                    if k != key:
                        extracted.setdefault(k, v)
                    else:
                        b2 = (b2 + "\n\n" + v[1]).strip()
                return m.get("title") or h or default_title, b2
            if key in extracted:
                t, b = extracted.pop(key)
                t = re.sub(r"^(the )?(si primer|si 101|briefs?|signal to watch)\s*[:·—–-]?\s*", "", t or "", flags=re.I)
                return t or default_title, b
            return None

        for fname, key, label, cls in [
            ("briefs.md", "briefs", "Briefs", "briefs"),
            ("primer.md", "primer", "SI Primer", "primer"),
            ("signal.md", "signal", "Signal to watch", "signal"),
        ]:
            got = part(fname, key, label)
            if got:
                title, b = got
                issue["sections"].append({"kicker": label, "title": title if title.lower() != label.lower() else "",
                                          "html": md(b), "cls": cls})
        if "horizon" in extracted:
            h_title, h_body = extracted.pop("horizon")
            yr = re.search(r"(19|20)\d\d", h_title)
            issue["horizon"] = {"title": h_title, "year": yr.group(0) if yr else "", "html": md(h_body)}
        else:
            issue["horizon"] = None
        short_src = None if single else (read(d / "short.md") or read(d / "short-version.md"))
        if short_src and short_src.strip():
            short_md = strip_leading_h1(parse_frontmatter(short_src)[1])[1]
        elif "short" in extracted:
            short_md = extracted.pop("short")[1]
        elif meta.get("short"):
            short_md = "\n".join(f"- {x.strip()}" for x in meta["short"].split("|") if x.strip())
        else:
            short_md = ""
        bullets = [re.sub(r"^\s*(?:[-*+•]|\d+[.)])\s+", "", l).strip() for l in short_md.split("\n")
                   if l.strip() and not l.strip().startswith("#") and not re.match(r"^\W*(tags?|topics?)\s*:", l.strip(), re.I)]
        if len(bullets) > 3:
            print(f"  warning: {d.name} short version has {len(bullets)} bullets; showing the first 3", file=sys.stderr)
        first = re.sub(r"[*_`]|\[([^\]]*)\]\([^)]*\)", r"\1", bullets[0]) if bullets else ""
        first = re.split(r"(?<=[.!?])\s+", first)[0]  # first sentence only
        issue["kicker"] = meta.get("kicker") or first
        unknown = [t for t in issue["tags"] if t.lower() not in {x.lower() for x in TOPICS}]
        if unknown:
            print(f"  warning: {d.name} has unknown topic label(s) {unknown}; allowed: {', '.join(TOPICS)}", file=sys.stderr)
        issue["tags"] = [next((x for x in TOPICS if x.lower() == t.lower()), t) for t in issue["tags"]]
        issue["short_html"] = md("\n".join(f"- {x}" for x in bullets[:3])) if bullets else ""
        for sec_file in (() if single else ("briefs.md", "primer.md", "signal.md")):
            t = read(d / sec_file)
            if t:
                issue["words"] += len(re.findall(r"\w+", parse_frontmatter(t)[1]))
        if single:
            issue["words"] = len(re.findall(r"\w+", parse_frontmatter(lead_txt)[1]))
        issue["minutes"] = max(1, round(issue["words"] / 230))
        disc = None if single else read(d / "disclaimer.md")
        if disc and disc.strip():
            issue["disclaimer_html"] = md(parse_frontmatter(disc)[1])
        elif "disclaimer" in extracted:
            issue["disclaimer_html"] = md(extracted["disclaimer"][1])
        else:
            issue["disclaimer_html"] = None
        allhtml = issue["lead_html"] + "".join(s["html"] for s in issue["sections"]) + (issue["horizon"]["html"] if issue["horizon"] else "")
        issue["sources"] = len({u for u in re.findall(r'href="(https?://[^"]+)"', allhtml)})
        issues.append(issue)
    issues.sort(key=lambda i: i["date"])
    n = 0
    for i in issues:
        if not i["example"]:
            n += 1
        i["number"] = i["number"] or ("Example" if i["example"] else str(n))
    issues.reverse()  # newest first
    return issues


DEFAULT_COPY = {
    "soon_kicker": "On its way",
    "soon_title": "Issue No. 1 is on its way.",
    "soon_body": "Good things take a minute. Follow the RSS feed and it will find you when it lands.",
    "footer": "Thanks for reading. A new issue comes every morning.",
    "notfound_title": "Well, this page wandered off.",
    "notfound_body": "Let’s head on back to today’s issue.",
    "signup_soon": "The morning email is still being set up.",
    "signup_lede": "One issue, every morning. Easy to read, easy to leave.",
    "search_title": "Search the archive",
    "search_body": "Every issue, brief and primer, all in one place.",
}

# ---------------------------------------------------------------- templates
FONTS = ""  # self-hosted in assets/fonts (see style.css); preloaded per page in page()


STRIP = {}
CSS_TEXT = [""]


def nav_items(root, canonical):
    items = [("", "Latest"), ("#archive", "Archive"), ("primers/", "Primer"), ("about/", "About"), ("subscribe/", "Subscribe")]
    cur = (canonical or "").split("/si-journal/")[-1] if canonical else None
    out = []
    for path, label in items:
        here = cur is not None and path == cur and path != "#archive"
        out.append(f'<li><a href="{root}{path}"{" aria-current=\"page\"" if here else ""}>{label}</a></li>')
    return "".join(out)


def page(site, root, title, body, description="", canonical="", kind="website", jsonld=None,
         noindex=False, banner="", head_extra=""):
    C = {**DEFAULT_COPY, **site.get("copy", {})}
    full_title = f"{title} · {site['name']}" if title != site["name"] else f"{site['name']}: {site['tagline']}"
    desc = description or site["description"]
    og_img = site["base_url"] + "assets/og.png"
    ld = "".join(f'<script type="application/ld+json">{json.dumps(x, ensure_ascii=False)}</script>' for x in (jsonld or []))
    robots = '<meta name="robots" content="noindex, nofollow, noarchive">' if noindex else ""
    og_title = title if title != site["name"] else full_title
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(full_title)}</title>
<meta name="description" content="{esc(desc)}">
{robots}
{f'<link rel="canonical" href="{esc(canonical)}">' if canonical and not noindex else ''}
<meta property="og:type" content="{kind}">
<meta property="og:title" content="{esc(og_title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:site_name" content="{esc(site['name'])}">
{f'<meta property="og:url" content="{esc(canonical)}">' if canonical and not noindex else ''}
<meta property="og:image" content="{og_img}">
<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">
<meta property="og:locale" content="en_US">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{esc(og_title)}">
<meta name="twitter:description" content="{esc(desc)}">
<meta name="twitter:image" content="{og_img}">
{f'<meta name="twitter:site" content="{esc(site["twitter"])}">' if site.get("twitter") else ''}
<meta name="theme-color" content="{site.get('paper', '#ECEAE4')}">
<link rel="alternate" type="application/rss+xml" title="{esc(site['name'])}" href="{root}feed.xml">
<link rel="icon" href="{root}assets/favicon.svg" type="image/svg+xml">
<link rel="preload" href="{root}assets/fonts/newsreader.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="{root}assets/fonts/plexmono-400.woff2" as="font" type="font/woff2" crossorigin>
{f'<link rel="preload" href="{root}assets/fonts/newsreader-italic.woff2" as="font" type="font/woff2" crossorigin>' if 'class="dek"' in body and kind in ("article",) or canonical == site["base_url"] else ""}
<style>{CSS_TEXT[0].replace("url(fonts/", "url(" + root + "assets/fonts/")}</style>
<script>document.documentElement.classList.add('js')</script>
{head_extra}
{ld}
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
{banner}
<div class="frame" aria-hidden="true"><i></i><i></i><i></i><i></i><b></b></div>
<header class="masthead" data-pagefind-ignore>
  <div class="wrap"><p class="strip"><span>{esc(site["name"])} · Daily<span class="wide"> · Est. 2026</span></span><span>{esc(STRIP.get("right", ""))}</span></p></div>
  <div class="wrap masthead-inner">
    <a class="wordmark" href="{root}">{esc(site['name'])}</a>
    <p class="tagline">{esc(site['tagline'])}</p>
    <nav aria-label="Primary"><ul>
      {nav_items(root, canonical)}
    </ul></nav>
    <form class="masthead-search" role="search" action="{root}search/" method="get">
      <label for="q-top" class="visually-hidden">Search issues</label>
      <input id="q-top" name="q" type="search" placeholder="Search" autocomplete="off" aria-keyshortcuts="/ Control+K Meta+K">
      <kbd aria-hidden="true">/</kbd>
    </form>
  </div>
</header>
<main id="main" tabindex="-1">
{body}
</main>
<footer class="colophon" data-pagefind-ignore>
  <div class="wrap">
    {"" if 'class="disclaimer"' in body else f'<p class="signoff">{esc(C["footer"])}</p>'}
    {"" if 'class="disclaimer"' in body else f'<p class="disclaimer-short">{esc(site["disclaimer"])}</p>'}
    <p class="small">© {dt.date.today().year} {esc(site['name'])} · <a href="{root}about/">About</a> · <a href="{root}search/">Search</a> · <a href="{root}feed.xml">RSS</a></p>
  </div>
</footer>
{TYPE_JS if 'class="typeline"' in body else ""}
{DECODE_JS if 'data-decode=' in body else ""}
{KEYS_JS}
</body>
</html>
"""


KEYS_JS = """<script>
document.addEventListener('keydown', function(e){
  var t = e.target, typing = t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName));
  var k = (e.key === '/' && !typing && !e.metaKey && !e.ctrlKey && !e.altKey) ||
          ((e.metaKey || e.ctrlKey) && (e.key === 'k' || e.key === 'K'));
  if (!k) return;
  var q = document.querySelector('#search .pagefind-ui__search-input') || document.getElementById('q-top');
  if (q) { e.preventDefault(); q.focus(); if (q.select) q.select(); }
});
</script>"""


def signup_block(site, root, bare=False):
    C = {**DEFAULT_COPY, **site.get("copy", {})}
    if bare:  # subscribe page: no second label/rule, the page itself is the block
        return (signup_block(site, root).replace('<div class="signup-inner">', '<div class="signup-inner bare">', 1)
                .replace('<h2 class="kicker" id="signup-title"><span class="q">MORNING EMAIL</span></h2>',
                         '<h2 class="visually-hidden" id="signup-title">Sign up</h2>', 1))
    action = site.get("signup_action") or site.get("form_endpoint") or ""
    if not action:
        return (f'<section class="wrap signup" aria-labelledby="signup-title" data-pagefind-ignore><div class="signup-inner">'
                f'<h2 class="kicker" id="signup-title"><span class="q">MORNING EMAIL</span></h2>'
                f'<p class="signup-soon">{esc(C["signup_soon"])} <a href="{root}feed.xml">RSS</a>.</p></div></section>')
    names = {"email": "email", "name": "name", "interest": "interest", **site.get("signup_fields", {})}
    hidden = "".join(f'<input type="hidden" name="{esc(k)}" value="{esc(v)}">' for k, v in site.get("signup_hidden", {}).items())
    opts = "".join(f"<option>{esc(t)}</option>" for t in TOPICS + ["Everything"])
    return f"""<section class="wrap signup" aria-labelledby="signup-title" data-pagefind-ignore>
  <div class="signup-inner"><h2 class="kicker" id="signup-title"><span class="q">MORNING EMAIL</span></h2>
  <p class="signup-lede">{esc(C["signup_lede"])}</p>
  <form class="signup-form" action="{esc(action)}" method="post" data-provider="{esc(site.get('signup_provider', ''))}">
    <div class="field"><label for="su-email">Email <span aria-hidden="true">*</span></label>
      <input id="su-email" name="{esc(names['email'])}" type="email" required autocomplete="email" inputmode="email"></div>
    <div class="field"><label for="su-name">Name <span class="opt">(optional)</span></label>
      <input id="su-name" name="{esc(names['name'])}" type="text" autocomplete="given-name"></div>
    <div class="field"><label for="su-interest">What are you watching? <span class="opt">(optional)</span></label>
      <select id="su-interest" name="{esc(names['interest'])}"><option value="">Choose one</option>{opts}</select></div>
    {hidden}
    <button type="submit">Subscribe</button>
  </form></div>
</section>"""


def org_ld(site):
    return {"@context": "https://schema.org", "@type": "Organization", "@id": site["base_url"] + "#org",
            "name": site["name"], "url": site["base_url"],
            "logo": {"@type": "ImageObject", "url": site["base_url"] + "assets/og.png"},
            "founder": {"@type": "Person", "name": site["author"]}}


def website_ld(site):
    return {"@context": "https://schema.org", "@type": "WebSite", "@id": site["base_url"] + "#website",
            "name": site["name"], "url": site["base_url"], "description": site["description"],
            "inLanguage": "en-US", "publisher": {"@id": site["base_url"] + "#org"},
            "potentialAction": {"@type": "SearchAction",
                                "target": {"@type": "EntryPoint", "urlTemplate": site["base_url"] + "search/?q={search_term_string}"},
                                "query-input": "required name=search_term_string"}}


def typeline(text):
    if not text:
        return ""
    # Screen readers get the full sentence at once; the animated copy is hidden from them.
    return (f'<p class="typeline"><span class="visually-hidden">{esc(text)}</span>'
            f'<span class="type" aria-hidden="true" data-text="{esc(text)}">{esc(text)}</span></p>')


TYPE_JS = """<script>
(function(){
  if (window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  document.querySelectorAll('.typeline .type').forEach(function(el){
    var t = el.getAttribute('data-text') || '', i = 0;
    el.textContent = ''; el.classList.add('typing');
    (function step(){
      el.textContent = t.slice(0, ++i);
      if (i < t.length) setTimeout(step, 38 + Math.random()*40);
      else setTimeout(function(){ el.classList.remove('typing'); el.classList.add('typed'); }, 1600);
    })();
  });
})();
</script>"""


def issue_label(i):
    n = str(i["number"])
    return f"No. {esc(n)}" if n.isdigit() else esc(n)


def readout_id(i):
    n = str(i["number"])
    return f"ASY/{int(n):03d}" if n.isdigit() else "ASY/EX"


def readout(i, prefix=""):
    """Instrument readout. Real values only: issue, date, reading time, words, distinct sources."""
    d = i["date"]
    parts = [("id", readout_id(i)), ("", d.isoformat()), ("", f'{i["minutes"]:02d} MIN'),
             ("", f'{i["words"]:,} W'), ("", f'{i["sources"]:02d} SRC')]
    spoken = (f'{full_label(i)}, {long_date(d)}, {i["minutes"]} minute read, {i["words"]:,} words, '
              f'{i["sources"]} linked sources')
    inner = " ".join(f'<span class="{c}">{esc(t)}</span>' for c, t in parts)
    return (f'<p class="readout" data-pagefind-ignore><span class="visually-hidden">{esc(spoken)}</span>'
            f'<span aria-hidden="true" style="display:contents">{esc(prefix)}{inner}</span></p>')


STATS = {}


def plural(n, word):
    return f"{n:02d} {word}{'' if n == 1 else 'S'}"


def page_head(site, code, spoken_bits, seed):
    """Readout + compact static trace for non-issue pages. Real values only."""
    shown = " ".join(f"<span>{esc(x)}</span>" for x in spoken_bits)
    return (f'<p class="readout" ><span class="visually-hidden">{esc(", ".join(spoken_bits))}</span>'
            f'<span aria-hidden="true" style="display:contents"><span class="id">{esc(code)}</span> {shown}</span></p>'
            + (trace_svg(seed, site["accent"], "", draw=False, compact=True).replace('role="img" aria-label=""', 'aria-hidden="true"')
               if site.get("trace", True) else ""))


def plain_label(text, id_=""):
    """Unquoted mono label, shown as written (no forced capitals)."""
    idattr = f' id="{id_}"' if id_ else ""
    return f'<p class="kicker plain"{idattr}>{esc(text)}</p>'


def qlabel(code, spoken, id_=""):
    """Tight, technical mono label in quotes, e.g. “BRIEFS/04”, with a plain spoken name for screen readers."""
    idattr = f' id="{id_}"' if id_ else ""
    return (f'<p class="kicker"{idattr}><span class="visually-hidden">{esc(spoken)}</span>'
            f'<span class="q" aria-hidden="true">{esc(code)}</span></p>')


def decode_h1(text, href=None, extra=""):
    inner = f'<a href="{href}">{esc(text)}</a>' if href else esc(text)
    return (f'<h1 class="decode"{extra}><span class="decode-real">{inner}</span>'
            f'<span class="decode-anim" aria-hidden="true" data-decode="{esc(text)}"></span></h1>')


DECODE_JS = """<script>
(function(){
  var reduce = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
  var key = 'asy-decoded:' + location.pathname, seen = false;
  try { seen = sessionStorage.getItem(key); sessionStorage.setItem(key, '1'); } catch (e) {}
  document.querySelectorAll('[data-decode]').forEach(function(el){
    if (reduce || seen) { el.remove(); return; }
    var h = el.parentNode, text = el.getAttribute('data-decode'), glyphs = '/\\|<>_-=+*#01:.';
    h.classList.add('decoding');
    var n = text.length, t0 = performance.now(), dur = 300 + Math.min(n, 60) * 18;
    (function frame(now){
      var p = (now - t0) / dur, out = '';
      for (var i = 0; i < n; i++) {
        var c = text[i];
        out += (c === ' ' || p > (i + 1) / n) ? c : glyphs[(Math.random() * glyphs.length) | 0];
      }
      el.textContent = out;
      if (p < 1.05) requestAnimationFrame(frame); else { h.classList.remove('decoding'); el.remove(); }
    })(t0);
  });
})();
</script>"""


def full_label(i):
    n = str(i["number"])
    return f"Issue No. {esc(n)}" if n.isdigit() else f"{esc(n)} issue"


def section_code(s):
    if s["cls"] == "briefs":
        return f'BRIEFS/{len(re.findall(r"<h[23]", s["html"])):02d}'
    if s["cls"] == "primer":
        m = re.search(r"day\s*(\d+)", s["title"] or "", re.I)
        return f"PRIMER/D{int(m.group(1)):02d}" if m else "PRIMER"
    return s["kicker"].upper()


def render_issue(site, i, newer, older, review=False):
    root = "../../"
    secs = []
    for s in i["sections"]:
        t = f'<h2 class="section-title" id="{s["cls"]}">{esc(s["title"])}</h2>' if s["title"] else ""
        secs.append(f'<section class="issue-section {s["cls"]}" aria-labelledby="k-{s["cls"]}">'
                    f'{qlabel(section_code(s), s["kicker"], "k-" + s["cls"])}{t}'
                    f'<div class="prose">{s["html"]}</div></section>')
    disc = (i["disclaimer_html"] or "") + f'<p class="legal">{esc(site["disclaimer"])}</p>'
    nav = []
    if older and not review:
        nav.append(f'<a rel="prev" href="{root}issues/{older["slug"]}/"><span class="sc">Previous</span>{esc(older["title"])}</a>')
    if newer and not review:
        nav.append(f'<a rel="next" class="next" href="{root}issues/{newer["slug"]}/"><span class="sc">Next</span>{esc(newer["title"])}</a>')
    d = i["date"]
    filters = "" if review else (
        # attribute forms, so none of this leaks into the indexed text or excerpts
        f'<span hidden data-pagefind-filter="year:{d.year}"></span>'
        f'<span hidden data-pagefind-filter="month:{d:%B %Y}"></span>'
        f'<span hidden data-pagefind-sort="date:{d.isoformat()}"></span>'
        f'<span hidden data-pagefind-meta="date:{long_date(d)}"></span>'
        f'<span hidden data-pagefind-meta="issue:{esc(issue_label(i))}"></span>')
    pf_body = "" if review else " data-pagefind-body"
    horizon = ""
    if i["horizon"]:
        h = i["horizon"]
        horizon = (f'<section class="horizon" aria-labelledby="h-horizon"><h2 class="visually-hidden" id="h-horizon">{esc(h["title"])}</h2>'
                   f'<p class="kicker"><span class="q" aria-hidden="true">BY {esc(h["year"])}</span></p><div class="prose">{h["html"]}</div></section>')
    short = (f'<aside class="short-version" aria-labelledby="k-short">{plain_label("Short version", "k-short")}{i["short_html"]}</aside>'
             if i["short_html"] else "")
    trace = trace_svg(i["title"] + "|" + i["slug"], site["accent"], "Signal trace drawn from this issue’s headline and date, closing on a dashed asymptote across the decade ahead", d.year) if site.get("trace", True) else ""
    body = f"""<article class="issue wrap"{pf_body}>
  {filters}
  <header class="issue-head">
    {fig(site, i["slug"], site["accent"], 168, f"Ink sprig, the unique mark of Issue {i['number']}")}
    {readout(i)}
    <div data-pagefind-ignore>{trace}
    {typeline(i["kicker"])}
    {qlabel("LEAD", "The lead essay")}</div>
    <span hidden data-pagefind-meta="title:{esc(i["title"])}"></span>
    {decode_h1(i["title"])}
    {f'<p class="dek">{esc(i["dek"])}</p>' if i["dek"] else ""}
    <div class="meta-row" data-pagefind-ignore><p class="meta"><time datetime="{d.isoformat()}">{long_date(d)}</time></p>{tags_html(i["tags"], filter_attr=not review)}</div>
    {f'<p class="byline sc">By {esc(i["author"])}</p>' if i["author"] else ""}
  </header>
  {short}
  <div class="prose lead-body">{i["lead_html"]}</div>
  {horizon}
  {"".join(secs)}
  <aside class="disclaimer" aria-label="Disclosures" data-pagefind-ignore>{qlabel("DISCLOSURES", "Disclosures")}{disc}</aside>
  {f'<nav class="issue-nav" aria-label="More issues" data-pagefind-ignore>{"".join(nav)}</nav>' if nav else ""}
</article>
{"" if review else signup_block(site, root)}"""
    url = f'{site["base_url"]}issues/{i["slug"]}/'
    if review:
        banner = (f'<div class="review-banner" role="note"><strong>Review copy</strong> · status: {esc(i["status"])} · '
                  f'unlisted, not indexed, not in the feed{" · example layout, not a real issue" if i["example"] else ""}</div>')
        return page(site, root, f"Review: {i['title']}", body, i["dek"], noindex=True, banner=banner)
    pub = f"{d.isoformat()}T06:00:00-04:00"
    ld = {"@context": "https://schema.org", "@type": "NewsArticle", "headline": i["title"][:110],
          "description": i["dek"], "datePublished": pub, "dateModified": pub, "url": url, "mainEntityOfPage": url,
          "image": [site["base_url"] + "assets/og.png"], "inLanguage": "en-US",
          "author": [{"@type": "Person", "name": i["author"] or site["author"]}],
          "publisher": org_ld(site), "isPartOf": {"@id": site["base_url"] + "#website"},
          "keywords": i["tags"], "wordCount": i["words"]}
    return page(site, root, i["title"], body, i["dek"] or i["kicker"], url, kind="article", jsonld=[ld],
                head_extra=f'<meta property="article:published_time" content="{pub}">' +
                "".join(f'<meta property="article:tag" content="{esc(t)}">' for t in i["tags"]))


def render_home(site, issues):
    C = {**DEFAULT_COPY, **site.get("copy", {})}
    root = "./"
    ld = [org_ld(site), website_ld(site)]
    if not issues:
        body = f"""<section class="wrap forthcoming">
  {fig(site, "forthcoming", site["accent"], 200, "An ink sprig awaiting its first issue")}
  {trace_svg("forthcoming", site["accent"], "A quiet signal trace, waiting for the first issue") if site.get("trace", True) else ""}
  <p class="kicker">{esc(C["soon_kicker"])}</p>
  <h1>{esc(C["soon_title"])}</h1>
  <p class="dek">{esc(C["soon_body"])}</p>
  <p><a class="cta" href="{root}about/">What this is <span class="arr" aria-hidden="true">→</span></a> <span class="sep" aria-hidden="true">·</span> <a class="cta" href="{root}feed.xml">RSS feed <span class="arr" aria-hidden="true">→</span></a></p>
</section>
<div id="archive"></div>
{signup_block(site, root)}"""
        return page(site, root, site["name"], body, canonical=site["base_url"], jsonld=ld)
    latest = issues[0]
    archive = "".join(
        f"""<li><a href="{root}issues/{i["slug"]}/">
  {mini(site, i["slug"])}
  <span class="sc"><span class="visually-hidden">{full_label(i)}, </span><span aria-hidden="true">{readout_id(i)}</span><br><time datetime="{i["date"].isoformat()}">{i["date"].isoformat()}</time></span>
  <span class="a-text"><span class="a-title">{esc(i["title"])}</span>
  {f'<span class="a-dek">{esc(i["dek"])}</span>' if i["dek"] else ""}
  {f'<span class="a-tags">{" ".join("[" + esc(t) + "]" for t in i["tags"])}</span>' if i["tags"] else ""}</span></a></li>"""
        for i in issues)
    contents = "".join(f'<li>{esc(s["kicker"])}{": " + esc(s["title"]) if s["title"] else ""}</li>' for s in latest["sections"])
    trace = trace_svg(latest["title"] + "|" + latest["slug"], site["accent"], "Signal trace drawn from today’s headline and date, closing on a dashed asymptote across the decade ahead", latest["date"].year) if site.get("trace", True) else ""
    short = f'<div class="short-version">{plain_label("Short version")}{latest["short_html"]}</div>' if latest["short_html"] else ""
    body = f"""<section class="wrap featured" aria-labelledby="featured-title">
  {fig(site, latest["slug"], site["accent"], 220, f"Ink sprig, the unique mark of Issue {latest['number']}")}
  {readout(latest)}
  {trace}
  {qlabel("TODAY", "Today’s issue")}
  {decode_h1(latest["title"], f'{root}issues/{latest["slug"]}/', ' id="featured-title"')}
  {f'<p class="dek">{esc(latest["dek"])}</p>' if latest["dek"] else ""}
  <div class="meta-row"><p class="meta"><time datetime="{latest["date"].isoformat()}">{long_date(latest["date"])}</time></p>{tags_html(latest["tags"])}</div>
  {short}
  {f'<ol class="contents" aria-label="In this issue"><li>The lead essay</li>{contents}</ol>' if contents else ""}
  <p><a class="cta" href="{root}issues/{latest["slug"]}/">Read the issue <span class="arr" aria-hidden="true">→</span></a></p>
</section>
{signup_block(site, root)}
<section class="wrap archive" id="archive" aria-labelledby="archive-title">
  <h2 id="archive-title" class="kicker"><span class="visually-hidden">The archive</span><span class="q" aria-hidden="true">ARCHIVE/{len(issues):02d}</span></h2>
  <ol class="archive-list">{archive}</ol>
</section>"""
    return page(site, root, site["name"], body, canonical=site["base_url"], jsonld=ld)


DEFAULT_ABOUT = """{name} is a daily read on the next decade, written for investors.

AI and superintelligence are the spine. Energy, bio, space, quantum, robotics and policy come in when they shape where the next ten years go. We pick stories that will still matter in 2036, that you can grasp in thirty seconds, and that you’d bring up at dinner.

Each morning has the same shape:

- **The short version.** Three lines or fewer.
- **The lead essay.** One idea, what happened, why it matters, and the investor angle. It closes with a hedged look at 2036, clearly marked as our judgment.
- **Briefs.** Three or four short items.
- **The SI Primer.** One concept a day, defined once and cleanly. Read them in order and the vocabulary builds.
- **Signal to watch.** One thing worth keeping an eye on.

Every number, date and quote has a link beside it. If we can’t source it, it doesn’t run.

Nobody knows the date. What we can watch is the slope.

{name} is edited by {author}, with research and editorial help from a small desk of AI collaborators.
"""


def render_about(site):
    root = "../"
    txt = read(BRAND / "about.md")
    if txt and txt.strip():
        _, b = parse_frontmatter(txt)
        _, b = strip_leading_h1(b)
    else:
        b = DEFAULT_ABOUT.format(**site)
    body = f"""<article class="wrap about">
  <header class="issue-head">
    {page_head(site, "ASY/ABOUT", [plural(STATS.get("issues", 0), "ISSUE"), plural(STATS.get("primers", 0), "PRIMER")] + ([f'SINCE {STATS["since"]}'] if STATS.get("since") else []), "about")}
    {qlabel("ABOUT", "About")}
    <h1>About {esc(site["name"])}</h1>
  </header>
  <div class="prose lead-body">{md(b)}</div>
</article>
{signup_block(site, root)}"""
    return page(site, root, "About", body, f"What {site['name']} is, how each issue is built, and who makes it.",
                f'{site["base_url"]}about/', jsonld=[org_ld(site)])


def render_primers(site, issues):
    C = {**DEFAULT_COPY, **site.get("copy", {})}
    root = "../"
    rows = []
    for i in reversed(issues):  # oldest first: lessons build on each other
        p = next((s for s in i["sections"] if s["cls"] == "primer"), None)
        if not p:
            continue
        rows.append(f'<li><a href="{root}issues/{i["slug"]}/#k-primer"><span class="a-text">'
                    f'<span class="sc"><span class="visually-hidden">{full_label(i)}, </span><span aria-hidden="true">{readout_id(i)} · </span><time datetime="{i["date"].isoformat()}">{i["date"].isoformat()}</time></span>'
                    f'<span class="a-title">{esc(p["title"] or "SI Primer")}</span></span></a></li>')
    lst = f'<ol class="archive-list">{"".join(rows)}</ol>' if rows else f'<p class="dek">{esc(C["soon_body"])}</p>'
    body = f"""<section class="wrap search-page" aria-labelledby="primers-title">
  {page_head(site, "ASY/PRIMER", [plural(len(rows), "LESSON"), "ONE A DAY"], "primer")}
  {qlabel(f"PRIMER/{len(rows):02d}", "Lessons")}
  <h1 id="primers-title">{esc(C["primers_title"])}</h1>
  <p class="dek">{esc(C["primers_body"])}</p>
  {lst}
</section>"""
    return page(site, root, C["primers_title"], body, C["primers_body"], f'{site["base_url"]}primers/')


def render_subscribe(site):
    C = {**DEFAULT_COPY, **site.get("copy", {})}
    root = "../"
    body = f"""<section class="wrap search-page" aria-labelledby="sub-title">
  {page_head(site, "ASY/SUBSCRIBE", ["DAILY", "SIGNUP " + ("OPEN" if (site.get("signup_action") or site.get("form_endpoint")) else "NOT YET OPEN")], "subscribe")}
  {qlabel("SUBSCRIBE", "Subscribe")}
  <h1 id="sub-title">{esc(C["subscribe_title"])}</h1>
  <p class="dek">{esc(C["subscribe_body"])}</p>
  <dl class="spec">
    <div><dt>Frequency</dt><dd>Every morning, ET.</dd></div>
    <div><dt>Format</dt><dd>The short version, the lead essay, three or four briefs, the SI Primer, one signal to watch.</dd></div>
    <div><dt>Sources</dt><dd>Every number, date and quote is linked.</dd></div>
    <div><dt>Status</dt><dd>{"Open." if (site.get("signup_action") or site.get("form_endpoint")) else "Not open yet."}</dd></div>
  </dl>
</section>
{signup_block(site, root, bare=True)}"""
    return page(site, root, "Subscribe", body, C["subscribe_body"], f'{site["base_url"]}subscribe/')


SEARCH_JS = """<link href="../pagefind/pagefind-ui.css" rel="stylesheet">
<script src="../pagefind/pagefind-ui.js"></script>
<script>
window.addEventListener('DOMContentLoaded', function(){
  var ui = new PagefindUI({ element: '#search', showSubResults: true, showImages: false, resetStyles: false,
    excerptLength: 26, pageSize: 8, autofocus: false,
    translations: { placeholder: 'Search issues, briefs and primers', zero_results: 'Nothing for [SEARCH_TERM] yet. Try a broader word.' } });
  var q = new URLSearchParams(location.search).get('q');
  if (q) { ui.triggerSearch(q); }
  var input = document.querySelector('#search .pagefind-ui__search-input');
  if (input) { input.setAttribute('aria-label', 'Search issues, briefs and primers'); if (!q) input.focus(); }
});
</script>"""


def render_search(site):
    C = {**DEFAULT_COPY, **site.get("copy", {})}
    root = "../"
    body = f"""<section class="wrap search-page" aria-labelledby="search-title">
  {page_head(site, "ASY/SEARCH", ["INDEX " + plural(STATS.get("issues", 0), "ISSUE"), "PAGEFIND"], "search")}
  {qlabel("SEARCH", "Search")}
  <h1 id="search-title">{esc(C["search_title"])}</h1>
  <p class="dek">{esc(C["search_body"])}</p>
  <div id="search" class="pf"></div>
  <noscript><p>Search needs JavaScript. The <a href="../#archive">archive</a> lists every issue.</p></noscript>
  <p class="small kbd-hint">Press <kbd>/</kbd> or <kbd>⌘K</kbd> anywhere to jump here. Use <kbd>Tab</kbd> to move through results and filters.</p>
</section>"""
    return page(site, root, "Search", body, f"Search every issue of {site['name']}.", f'{site["base_url"]}search/',
                head_extra=SEARCH_JS)


def render_404(site):
    C = {**DEFAULT_COPY, **site.get("copy", {})}
    root = "/" + site["base_url"].split("//", 1)[-1].split("/", 1)[-1] if "//" in site["base_url"] else "/"
    body = (f'<section class="wrap forthcoming">{fig(site, "lost", site["accent"], 160, "A stray ink sprig")}'
            f'<p class="kicker">404</p><h1>{esc(C["notfound_title"])}</h1><p class="dek">{esc(C["notfound_body"])}</p>'
            f'<p><a class="cta" href="{root}">Back to today’s issue <span class="arr" aria-hidden="true">→</span></a></p></section>')
    return page(site, root, "Not found", body, noindex=True)


def render_feed(site, issues):
    def cdata(s):
        return "<![CDATA[" + s.replace("]]>", "]]]]><![CDATA[>") + "]]>"
    items = []
    for i in issues[:50]:
        url = f'{site["base_url"]}issues/{i["slug"]}/'
        pub = email.utils.format_datetime(dt.datetime.combine(i["date"], dt.time(6, 0), tzinfo=dt.timezone(dt.timedelta(hours=-4))))
        content = (f"<p><strong>The short version</strong></p>{i['short_html']}" if i["short_html"] else "") + i["lead_html"]
        if i["horizon"]:
            content += f'<h2>{esc(i["horizon"]["title"])}</h2>{i["horizon"]["html"]}'
        content += "".join(f'<h2>{esc(s["kicker"])}{": " + esc(s["title"]) if s["title"] else ""}</h2>{s["html"]}' for s in i["sections"])
        content += i["disclaimer_html"] or f"<p><em>{esc(site['disclaimer'])}</em></p>"
        cats = "".join(f"    <category>{esc(t)}</category>\n" for t in i["tags"])
        items.append(f"""  <item>
    <title>{esc(i["title"])}</title>
    <link>{url}</link>
    <guid isPermaLink="true">{url}</guid>
    <pubDate>{pub}</pubDate>
    <description>{esc(i["dek"] or i["title"])}</description>
{cats}    <content:encoded>{cdata(content)}</content:encoded>
  </item>""")
    now = email.utils.format_datetime(dt.datetime.now(dt.timezone.utc))
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:atom="http://www.w3.org/2005/Atom">
<channel>
  <title>{esc(site["name"])}</title>
  <link>{site["base_url"]}</link>
  <atom:link href="{site["base_url"]}feed.xml" rel="self" type="application/rss+xml"/>
  <description>{esc(site["description"])}</description>
  <language>{esc(site.get("language", "en-us"))}</language>
  <lastBuildDate>{now}</lastBuildDate>
{chr(10).join(items)}
</channel>
</rss>
"""


def render_sitemap(site, issues):
    today = dt.date.today().isoformat()
    urls = [(site["base_url"], issues[0]["date"].isoformat() if issues else today),
            (site["base_url"] + "about/", today), (site["base_url"] + "primers/", today),
            (site["base_url"] + "subscribe/", today), (site["base_url"] + "search/", today)]
    urls += [(f'{site["base_url"]}issues/{i["slug"]}/', i["date"].isoformat()) for i in issues]
    body = "".join(f"  <url><loc>{esc(u)}</loc><lastmod>{m}</lastmod></url>\n" for u, m in urls)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{body}</urlset>\n'


def render_robots(site):
    path = "/" + site["base_url"].split("//", 1)[-1].split("/", 1)[-1] if "//" in site["base_url"] else "/"
    return f"User-agent: *\nAllow: /\nDisallow: {path}review/\n\nSitemap: {site['base_url']}sitemap.xml\n"


# ---------------------------------------------------------------- build
def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def run_pagefind(have_issues):
    """Index only published issue pages (lead essay, briefs, primer, signal as sub-results)."""
    import subprocess
    if not have_issues:
        print("  search: no published issues yet, index skipped")
        return
    cmd = ["npx", "-y", "pagefind@1.5.2", "--site", str(OUT), "--glob", "issues/**/*.html"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout[-2000:], r.stderr[-2000:], file=sys.stderr)
        raise SystemExit("pagefind failed")
    m = re.search(r"Indexed (\d+) pages?", r.stdout)
    print(f"  search: pagefind indexed {m.group(1) if m else '?'} page(s)")


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Build the SI Journal site into docs/.")
    ap.add_argument("--review", action="store_true",
                    help="also build unlisted review copies of real issues with status: review (example issues always build)")
    ap.add_argument("--no-search", action="store_true", help="skip the Pagefind index")
    ap.add_argument("--list", action="store_true", help="print slug and status of every issue folder, then exit")
    args = ap.parse_args()
    if args.list:
        for d in sorted(ISSUES.iterdir()) if ISSUES.exists() else []:
            if d.is_dir() and (DATE_RE.match(d.name) or d.name.startswith("example-")):
                lead = read(d / "lead-essay.md") or ""
                print(d.name, issue_status(d, parse_frontmatter(lead)[0]) if lead.strip() else "empty")
        return 0

    site = load_site()
    global TOPICS
    TOPICS = site.get("topics", TOPICS)
    everything = load_issues()
    issues = [i for i in everything if i["status"] == "approved" and not i["example"]]
    reviews = [i for i in everything if i["status"] == "review" or (i["example"] and i["status"] == "approved")]

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    shutil.copytree(ASSETS, OUT / "assets")
    css = (OUT / "assets" / "style.css")
    tok = css.read_text(encoding="utf-8")
    for k in ("paper", "paper_deep", "ink", "ink_soft", "muted", "rule", "accent", "accent_text"):
        tok = tok.replace(f"__{k.upper()}__", site.get(k, ""))
    assert "__" not in re.sub(r"[a-z]__[a-z]|__[a-z]", "", tok), "unfilled CSS token"
    css.write_text(tok, encoding="utf-8")
    CSS_TEXT[0] = re.sub(r"\s*\n\s*", "\n", re.sub(r"/\*.*?\*/", "", tok, flags=re.S)).strip()
    prim = [i for i in issues if any(s["cls"] == "primer" for s in i["sections"])]
    STATS.update(issues=len(issues), primers=len(prim), since=issues[-1]["date"].isoformat() if issues else "")
    if issues:
        a = issues[0]
        STRIP["right"] = f"Latest {readout_id(a)} · {a['date'].isoformat()}"
    write(OUT / "assets" / "favicon.svg", f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="10" fill="{site["accent"]}"/><text x="32" y="45" font-family="Georgia,serif" font-size="38" text-anchor="middle" fill="{site.get("paper", "#F5EFE4")}">{esc(site["name"][:1])}</text></svg>')
    write(OUT / ".nojekyll", "")
    write(OUT / "index.html", render_home(site, issues))
    write(OUT / "about" / "index.html", render_about(site))
    write(OUT / "search" / "index.html", render_search(site))
    write(OUT / "primers" / "index.html", render_primers(site, issues))
    write(OUT / "subscribe" / "index.html", render_subscribe(site))
    write(OUT / "404.html", render_404(site))
    for n, i in enumerate(issues):
        newer = issues[n - 1] if n > 0 else None
        older = issues[n + 1] if n + 1 < len(issues) else None
        write(OUT / "issues" / i["slug"] / "index.html", render_issue(site, i, newer, older))
    review_links = []
    for i in reviews:
        if not (i["example"] or args.review):
            print(f"  review copy of {i['slug']} kept local (rebuild with --review to publish the unlisted link)")
            continue
        slug = f'{i["slug"]}-{review_token(i["slug"])}'
        write(OUT / "review" / slug / "index.html", render_issue(site, i, None, None, review=True))
        review_links.append((i["slug"], f'{site["base_url"]}review/{slug}/', f"review/{slug}/"))
    write(OUT / "feed.xml", render_feed(site, issues))
    write(OUT / "sitemap.xml", render_sitemap(site, issues))
    write(OUT / "robots.txt", render_robots(site))
    write(ROOT / ".review-links.json", json.dumps(review_links, indent=1))
    import xml.dom.minidom
    xml.dom.minidom.parseString((OUT / "feed.xml").read_bytes())
    xml.dom.minidom.parseString((OUT / "sitemap.xml").read_bytes())
    if not args.no_search:
        run_pagefind(bool(issues))
    print(f"Built {len(issues)} published issue(s), {len(review_links)} review cop(ies) → {OUT}")
    for i in issues:
        print(f"  published  No. {i['number']}  {i['slug']}  {i['title']}")
    for slug, url, _ in review_links:
        print(f"  review     {slug}  {url}")


if __name__ == "__main__":
    sys.exit(main())
