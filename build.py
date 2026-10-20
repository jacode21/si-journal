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
STORIES = Path(os.environ.get("SI_STORIES", ROOT / "stories"))
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
            last = None
            for line in parts[1:end]:
                if re.match(r"^\s+-\s+", line) and last:  # list item under the previous key
                    if not isinstance(meta.get(last), list):
                        meta[last] = [meta[last]] if meta.get(last) else []
                    meta[last].append(re.sub(r"^\s+-\s+", "", line).strip())
                    continue
                if ":" in line and not line.lstrip().startswith("#"):
                    k, v = line.split(":", 1)
                    v = v.strip()
                    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
                        v = v[1:-1]
                    last = k.strip().lower()
                    meta[last] = v
            body = "\n".join(parts[end + 1:])
    return meta, body.strip("\n")


TAGLINE_RE = re.compile(r"<p>(?:<(em|strong)>)?\s*(?:Tags?|Topics?)\s*:\s*([^<]{1,120}?)\s*(?:</\1>)?</p>", re.I)


def md(text):
    out = markdown.markdown(
        text, extensions=["extra", "smarty", "sane_lists", "toc"], output_format="html5"
    )
    # "Tags: AI, Energy" lines inside briefs/signal become quiet mono labels
    return TAGLINE_RE.sub(lambda m: '<p class="inline-tags" data-pagefind-ignore><span class="visually-hidden">Topics: </span>'
                          + " · ".join(esc(t.strip()) for t in m.group(2).split(",") if t.strip()) + "</p>", out)


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
    if year and False:  # scale labels removed in the clean pass
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
            "story_slugs": parse_tags(meta.get("stories") or "") if not isinstance(meta.get("stories"), list) else meta["stories"],
        }

        def part(fname, key, default_title):
            # the Primer has its own file (primer.md) and that file wins over any copy inside issue.md;
            # versioned copies such as primer.v1.md are never read
            txt = read(d / fname) if (not single or key == "primer") else None
            if txt and txt.strip():
                extracted.pop(key, None)
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
    "hero_title": "", "hero_body": "", "topic_sub": "", "archive_sub": "", "primer_sub": "", "about_sub": "", "about_rows": [],
    "about": "{name} is a daily briefing on AI and the technologies shaping the next decade, written for investors. Every figure links to its source. Edited by {author}.",
    "subscribe_open": "One issue each morning, by email.",
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
SIGNUP_OPEN = [False]
HAVE_STORIES = [False]
VARIANT = [""]
CSS_TEXT = [""]


def nav_items(root, canonical):
    items = ([("", "Feed"), ("issues/", "Issues")] if HAVE_STORIES[0] else [("#archive", "Issues")]) + [("primers/", "Primer"), ("about/", "About")]
    if SIGNUP_OPEN[0]:
        items.append(("subscribe/", "Subscribe"))
    cur = (canonical or "").split("/si-journal/")[-1] if canonical else None
    out = []
    for path, label in items:
        here = cur is not None and path != "#archive" and (path == cur or (path == "" and cur.startswith("topic/")))
        out.append(f'<li><a href="{root}{path}"{" aria-current=\"page\"" if here else ""}>{label}</a></li>')
    here = cur == "search/"
    out.append(f'<li><a class="search-link" href="{root}search/" aria-label="Search"{AC if here else ""}>'
               '<svg viewBox="0 0 16 16" width="15" height="15" aria-hidden="true" focusable="false"><circle cx="6.8" cy="6.8" r="5" fill="none" stroke="currentColor" stroke-width="1.3"/><path d="M10.5 10.5 15 15" stroke="currentColor" stroke-width="1.3"/></svg></a></li>')
    return "".join(out)


AC = ' aria-current="page"'


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
<body{f' class="v-{VARIANT[0].lower()}"' if VARIANT[0] else ""}>
<a class="skip" href="#main">Skip to content</a>
{banner}
<header class="masthead" data-pagefind-ignore>
  <div class="wrap masthead-inner">
    <p class="brand"><a class="wordmark" href="{root}">{esc(site['name'])}</a>{f'<span class="tagline">{esc(site["tagline"])}</span>' if site.get("tagline") else ""}</p>
    <nav aria-label="Primary"><ul>{nav_items(root, canonical)}</ul></nav>
  </div>
</header>
<main id="main" tabindex="-1">
{body}
</main>
<footer class="colophon" data-pagefind-ignore>
  <div class="wrap">
    <p class="small"><span>{esc(site["disclaimer"])} <a href="{root}disclosures/">Disclosures</a></span><span>© {dt.date.today().year} {esc(site['name'])} · <a href="{root}feed.xml">RSS</a></span></p>
  </div>
</footer>
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
  var q = document.querySelector('#search .pagefind-ui__search-input');
  e.preventDefault();
  if (q) { q.focus(); if (q.select) q.select(); }
  else { var a = document.querySelector('.search-link'); if (a) location.href = a.href; }
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
        return ""  # hidden until signup_action is set
        return (f'<section class="wrap signup" aria-labelledby="signup-title" data-pagefind-ignore><div class="signup-inner">'
                f'<h2 class="kicker" id="signup-title"><span class="q">MORNING EMAIL</span></h2>'
                f'<p class="signup-soon">{esc(C["signup_soon"])} <a href="{root}feed.xml">RSS</a>.</p></div></section>')
    names = {"email": "email", "name": "name", "interest": "interest", **site.get("signup_fields", {})}
    hidden = "".join(f'<input type="hidden" name="{esc(k)}" value="{esc(v)}">' for k, v in site.get("signup_hidden", {}).items())
    opts = "".join(f"<option>{esc(t)}</option>" for t in TOPICS + ["Everything"])
    return f"""<section class="wrap signup" aria-labelledby="signup-title" data-pagefind-ignore>
  <div class="signup-inner"><h2 class="visually-hidden" id="signup-title">Subscribe</h2>
  <form class="signup-form" action="{esc(action)}" method="post" data-provider="{esc(site.get('signup_provider', ''))}">
    <div class="field"><label for="su-email">Email <span aria-hidden="true">*</span></label>
      <input id="su-email" name="{esc(names['email'])}" type="email" required autocomplete="email" inputmode="email"></div>
    <div class="field"><label for="su-name">Name <span class="opt">(optional)</span></label>
      <input id="su-name" name="{esc(names['name'])}" type="text" autocomplete="given-name"></div>
    <div class="field"><label for="su-interest">Topic <span class="opt">(optional)</span></label>
      <select id="su-interest" name="{esc(names['interest'])}"><option value="">Any</option>{opts}</select></div>
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
    return f'<h1{extra}>{inner}</h1>'


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


def dek_span(i):
    return f'<span class="a-dek">{esc(i["dek"])}</span>' if i["dek"] else ""


def quiet_trace(site, i):
    """The waveform as quiet art: static, unlabeled, decorative."""
    if not site.get("trace", True):
        return ""
    t = trace_svg(i["title"] + "|" + i["slug"], site["accent"], "", draw=False, compact=True)
    return t.replace('role="img" aria-label=""', 'aria-hidden="true" focusable="false"')


def section_name(s):
    if s["cls"] == "primer":
        return f'Primer: {s["title"]}' if s["title"] else "Primer"
    return s["title"] or s["kicker"]


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


ALL_STORIES = []


def roundup(i):
    want = i.get("story_slugs") or []
    if not want:
        return ""
    by = {st["slug"]: st for st in ALL_STORIES if st["day"] == i["slug"]}
    got = [by[x] for x in want if x in by]
    missing = [x for x in want if x not in by]
    if missing:
        print(f"  warning: issue {i['slug']} lists stories that aren't approved or don't exist: {missing}", file=sys.stderr)
    if not got:
        return ""
    return (f'<section class="roundup" aria-labelledby="rd-h" data-pagefind-ignore><h2 id="rd-h" class="section-title small-h">Stories</h2>'
            f'<ol class="cards">{"".join(story_card(st, "../../") for st in got)}</ol></section>')


def render_issue(site, i, newer, older, review=False):
    root = "../../"
    secs = []
    for s in i["sections"]:
        t = f'<h2 class="section-title" id="k-{s["cls"]}">{esc(section_name(s))}</h2>'
        secs.append(f'<section class="issue-section {s["cls"]}" aria-labelledby="k-{s["cls"]}">'
                    f'{t}'
                    f'<div class="prose">{s["html"]}</div></section>')
    disc = i["disclaimer_html"] or ""
    nav = []
    if older and not review:
        nav.append(f'<a rel="prev" href="{root}issues/{older["slug"]}/"><span class="sc">Earlier</span>{esc(older["title"])}</a>')
    if newer and not review:
        nav.append(f'<a rel="next" class="next" href="{root}issues/{newer["slug"]}/"><span class="sc">Later</span>{esc(newer["title"])}</a>')
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
        horizon = (f'<section class="horizon" aria-labelledby="h-horizon"><h2 class="section-title small-h" id="h-horizon">{esc(h["title"])}</h2>'
                   f'<div class="prose">{h["html"]}</div></section>')
    short = (f'<aside class="short-version" aria-labelledby="k-short">{plain_label("Short version", "k-short")}{i["short_html"]}</aside>'
             if i["short_html"] else "")
    trace = quiet_trace(site, i)
    body = f"""<article class="issue wrap"{pf_body}>
  {filters}
  <header class="issue-head">
    {trace}
    <span hidden data-pagefind-meta="title:{esc(i["title"])}"></span>
    <p class="meta" data-pagefind-ignore><time datetime="{d.isoformat()}">{long_date(d)}</time></p>
    {decode_h1(i["title"])}
    {f'<p class="dek">{esc(i["dek"])}</p>' if i["dek"] else ""}
    <div data-pagefind-ignore>{tags_html(i["tags"], filter_attr=not review)}</div>
  </header>
  {short}
  {roundup(i)}
  <div class="prose lead-body">{i["lead_html"]}</div>
  {horizon}
  {"".join(secs)}
  {f'<aside class="disclaimer" aria-label="Disclosures" data-pagefind-ignore>{disc}</aside>' if disc else ""}
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
  <h1>No issues yet.</h1>
</section>
<div id="archive"></div>
{signup_block(site, root)}"""
        return page(site, root, site["name"], body, canonical=site["base_url"], jsonld=ld)
    latest = issues[0]
    archive = "".join(
        f'<li><a href="{root}issues/{i["slug"]}/"><time class="sc" datetime="{i["date"].isoformat()}">{i["date"]:%b} {i["date"].day}, {i["date"].year}</time>'
        f'<span class="a-title">{esc(i["title"])}</span></a></li>' for i in issues)
    archive_html = f"""<section class="wrap archive" id="archive" aria-labelledby="archive-title">
  <h2 id="archive-title" class="list-head">Archive</h2>
  <ol class="archive-list">{archive}</ol>
</section>"""
    if VARIANT[0] == "C":  # index-first: the home page is the list
        rows = "".join(
            f'<li><a href="{root}issues/{i["slug"]}/"><time class="sc" datetime="{i["date"].isoformat()}">{i["date"]:%b} {i["date"].day}, {i["date"].year}</time>'
            f'<span class="a-text"><span class="a-title">{esc(i["title"])}</span>{dek_span(i)}</span></a></li>' for i in issues)
        body = f"""<section class="wrap archive index-first" id="archive" aria-labelledby="archive-title">
  <h1 id="archive-title" class="visually-hidden">Issues</h1>
  <ol class="archive-list">{rows}</ol>
</section>"""
        return page(site, root, site["name"], body, canonical=site["base_url"], jsonld=ld)
    short = f'<div class="short-version">{plain_label("Short version")}{latest["short_html"]}</div>' if latest["short_html"] else ""
    body = f"""<section class="wrap featured" aria-labelledby="featured-title">
  {quiet_trace(site, latest)}
  <p class="meta"><time datetime="{latest["date"].isoformat()}">{long_date(latest["date"])}</time></p>
  {decode_h1(latest["title"], f'{root}issues/{latest["slug"]}/', ' id="featured-title"')}
  {f'<p class="dek">{esc(latest["dek"])}</p>' if latest["dek"] else ""}
  {tags_html(latest["tags"])}
  {short}
</section>
{signup_block(site, root)}
{archive_html}"""
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


# ---------------------------------------------------------------- stories
STORY_SKIP = re.compile(r"(\.v\d+|\.draft|\.notes?|^_|^readme)", re.I)


def day_status(date_dir):
    """Approval is per day: stories/<date>/status, else issues/<date>/status, else draft."""
    for f in (STORIES / date_dir / "status", ISSUES / date_dir / "status"):
        t = read(f)
        if t and t.strip():
            return STATUS_ALIASES.get(t.strip().lower(), "draft")
    return "draft"


def parse_sources(v):
    out = []
    for x in (v if isinstance(v, list) else [v] if v else []):
        if "|" in x:
            label, url = [y.strip() for y in x.rsplit("|", 1)]
        else:
            label, url = re.sub(r"^https?://(www\.)?", "", x).split("/")[0], x.strip()
        out.append((label, url))
    return out


def load_stories(include_review=False):
    out = []
    if not STORIES.exists():
        return out
    allow_mock = os.environ.get("SI_MOCK") == "1"
    for d in sorted(STORIES.iterdir()):
        if not (d.is_dir() and DATE_RE.match(d.name)):
            continue
        status = day_status(d.name)
        if status != "approved" and not (include_review and status == "review"):
            continue
        for f in sorted(d.glob("*.md")):
            if STORY_SKIP.search(f.stem):
                continue
            meta, body = parse_frontmatter(f.read_text(encoding="utf-8"))
            if not body.strip():
                continue
            mock = str(meta.get("mock", "")).lower() in ("true", "yes", "1")
            if mock and not allow_mock:
                continue  # local mocks never reach a real build
            _, body = strip_leading_h1(body)
            date = dt.date.fromisoformat(str(meta.get("date", d.name))[:10])
            tags = parse_tags(meta.get("topics") or meta.get("tags") or "")
            unknown = [t for t in tags if t.lower() not in {x.lower() for x in TOPICS}]
            if unknown:
                print(f"  warning: {d.name}/{f.name}: unknown topic(s) {unknown}; use {TOPICS}", file=sys.stderr)
            out.append({
                "slug": f.stem, "day": d.name, "date": date, "time": str(meta.get("time", "")).strip(),
                "order": int(meta.get("order") or 99),
                "title": meta.get("headline") or meta.get("title") or f.stem.replace("-", " ").capitalize(),
                "dek": meta.get("dek") or "", "tags": [next((x for x in TOPICS if x.lower() == t.lower()), t) for t in tags],
                "sources": parse_sources(meta.get("sources")), "html": md(body), "mock": mock,
                "mock_note": meta.get("mock_note") or "Local mock, not for publication.",
                "status": status, "words": len(re.findall(r"\w+", body)),
                "key_points": meta["key_points"] if isinstance(meta.get("key_points"), list) else [],
            })
    # newest first; within a day, by time (latest first), then the editor's order
    out.sort(key=lambda x: (x["date"], x["time"] or "", -x["order"]), reverse=True)
    return out


def story_url(st, root=""):
    if st.get("url"):
        return root + st["url"]
    return f'{root}stories/{st["day"]}/{st["slug"]}/'


def story_when(st):
    return f'{long_date(st["date"])}{" · " + esc(st["time"]) + " ET" if st["time"] else ""}'


ARROW = '<svg class="arr" viewBox="0 0 16 10" width="16" height="10" aria-hidden="true" focusable="false"><path d="M0 5h14M10 1l4 4-4 4" fill="none" stroke="currentColor" stroke-width="1.2"/></svg>'
ARROW_L = '<svg class="arr" viewBox="0 0 16 10" width="16" height="10" aria-hidden="true" focusable="false"><path d="M16 5H2M6 1 2 5l4 4" fill="none" stroke="currentColor" stroke-width="1.2"/></svg>'


def mono_date(d):
    return f"{d:%b} {d.day:02d}, {d.year}".upper()


def card_time(st):
    return f'<time>{esc(st["time"])} ET</time>' if st["time"] else ""


def dek_html(st):
    return f'<span class="card-dek">{esc(st["dek"])}</span>' if st["dek"] else ""


def tags_line(st):
    if not st["tags"]:
        return ""
    return '<span class="card-tags"><span class="visually-hidden">Topics: </span>' + "".join(f"<span>{esc(x)}</span>" for x in st["tags"]) + "</span>"


def story_card(st, root, prefer=""):
    t = prefer if prefer in st["tags"] else (st["tags"][0] if st["tags"] else "")
    lead = f' <span class="sep" aria-hidden="true">|</span> <span class="card-tag">{esc(t)}</span>' if t else ""
    return (f'<li class="card" data-topics="{esc(" ".join(x.lower() for x in st["tags"]))}"><a href="{story_url(st, root)}">'
            f'<span class="card-body"><span class="card-top"><time datetime="{st["date"].isoformat()}">{mono_date(st["date"])}</time>'
            f'{" · " + card_time(st) if st["time"] else ""}{lead}</span>'
            f'<span class="card-title">{esc(st["title"])}</span>'
            f'{dek_html(st)}'
            f'{tags_line(st)}</span>'
            f'<span class="card-go">{ARROW}</span></a></li>')


def topic_slug(t):
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")


def chips(root, active=""):
    items = [("", "All")] + [(topic_slug(t), t) for t in TOPICS]
    out = []
    for sl, label in items:
        href = f"{root}topic/{sl}/" if sl else root
        cur = ' aria-current="page"' if sl == active else ""
        out.append(f'<li><a class="chip" href="{href}" data-topic="{sl}"{cur}>{esc(label)}</a></li>')
    return (f'<nav class="chips" aria-label="Filter by topic"><ul>{"".join(out)}</ul>'
            f'<p class="chips-sort" aria-hidden="true"><span class="dot"></span>Latest</p></nav>')


def stream(stories, root, prefer=""):
    days, out = {}, []
    for st in stories:
        days.setdefault(st["date"], []).append(st)
    for d, group in days.items():
        out.append(f'<section class="day" data-day="{d.isoformat()}"><h2 class="day-head"><time datetime="{d.isoformat()}">{long_date(d)}</time></h2>'
                   f'<ol class="cards">{"".join(story_card(st, root, prefer) for st in group)}</ol></section>')
    return "".join(out)


FEED_STORIES = []


FEED_JS = """<script>
(function(){
  // day headings: Today / Yesterday, from the reader's own clock
  var now = new Date(), iso = function(d){ return d.getFullYear() + '-' + ('0' + (d.getMonth() + 1)).slice(-2) + '-' + ('0' + d.getDate()).slice(-2); };
  var today = iso(now), y = new Date(now); y.setDate(now.getDate() - 1); var yday = iso(y);
  document.querySelectorAll('.day-head time').forEach(function(t){
    var v = t.getAttribute('datetime');
    if (v === today) t.textContent = 'Today'; else if (v === yday) t.textContent = 'Yesterday';
  });
  // topic chips filter in place; the links still work without JavaScript
  var chips = document.querySelectorAll('.chip[data-topic]'), empty = document.querySelector('.feed-empty');
  function apply(topic){
    var shown = 0;
    document.querySelectorAll('.day').forEach(function(day){
      var n = 0;
      day.querySelectorAll('.card').forEach(function(c){
        var ok = !topic || (' ' + c.getAttribute('data-topics') + ' ').indexOf(' ' + topic.replace(/-/g, ' ') + ' ') >= 0;
        c.hidden = !ok; if (ok) n++;
      });
      day.hidden = n === 0; shown += n;
    });
    if (empty) empty.hidden = shown > 0;
    chips.forEach(function(c){ if (c.getAttribute('data-topic') === topic) c.setAttribute('aria-current', 'page'); else c.removeAttribute('aria-current'); });
  }
  if (!document.querySelector('.feed[data-static-topic]')) chips.forEach(function(c){
    c.addEventListener('click', function(e){
      if (e.metaKey || e.ctrlKey || e.shiftKey) return;
      e.preventDefault(); var t = c.getAttribute('data-topic'); apply(t);
      history.replaceState(null, '', t ? '?topic=' + t : location.pathname);
    });
  });
  var q = new URLSearchParams(location.search).get('topic');
  if (q && !document.querySelector('.feed[data-static-topic]')) apply(q);
})();
</script>"""


def render_feed_page(site, stories, root, topic=""):
    C = {**DEFAULT_COPY, **site.get("copy", {})}
    label = next((t for t in TOPICS if topic_slug(t) == topic), "")
    shown = [st for st in stories if not topic or label in st["tags"]]
    if topic:
        head = f'<header class="page-head"><p class="meta">Topic</p><h1 class="feed-title">{esc(label)}</h1></header>'
    else:
        head = (f'<header class="lead"><h1>{esc(C["hero_title"])}</h1><p class="sub">{esc(C["hero_body"])}</p>'
                f'<span class="rule-accent" aria-hidden="true"></span></header>')
    mock = ('<p class="mock-note" role="note">Local mock: these stories are Issue No. 1 split into parts, text and sources verbatim. Not published.</p>'
            if any(x["mock"] for x in shown) else "")
    empty = f'<p class="feed-empty"{" hidden" if shown else ""}>No stories in this topic yet.</p>'
    body = f"""<section class="wrap feed"{f' data-static-topic="{topic}"' if topic else ""} aria-label="Stories">
  {head}
  {chips(root, topic)}
  {stream(shown, root, label)}
  {empty}
  {mock}
</section>"""
    title = site["name"] if not topic else label
    canon = site["base_url"] + (f"topic/{topic}/" if topic else "")
    desc = site["description"] if not topic else f"{label} stories from {site['name']}."
    ld = [org_ld(site), website_ld(site)] if not topic else []
    return page(site, root, title, body + FEED_JS, desc, canon, jsonld=ld)


VIEW_RE = re.compile(r"(our view|outlook|by 20\d\d|what is our view)", re.I)


def number_sections(h):
    """Story system: each H2 becomes a numbered mono section label; the analysis section is set apart."""
    n = [0]
    def sub(m):
        n[0] += 1
        cls = " view" if VIEW_RE.search(m.group(2)) else ""
        return f'<h2{m.group(1)} class="sec{cls}">{m.group(2)}</h2>'
    out = re.sub(r"<h2([^>]*)>(.*?)</h2>", sub, h)
    # wrap the analysis section (heading + following blocks up to the next h2) so it reads visibly separate
    return re.sub(r'(<h2[^>]*class="sec view".*?)(?=<h2|\Z)', r'<div class="view-block">\1</div>', out, flags=re.S)


def render_story(site, st, newer, older, review=False, root="../../../"):
    srcs = "".join(f'<li><a href="{esc(u)}" rel="noopener">{esc(l)}</a></li>' for l, u in st["sources"])
    nav = []
    if older:
        nav.append(f'<a rel="prev" href="{story_url(older, root)}"><span class="sc">Previous</span>{esc(older["title"])}</a>')
    if newer:
        nav.append(f'<a rel="next" class="next" href="{story_url(newer, root)}"><span class="sc">Next</span>{esc(newer["title"])}</a>')
    d = st["date"]
    filters = "" if review else (
        f'<span hidden data-pagefind-filter="year:{d.year}"></span><span hidden data-pagefind-filter="month:{d:%B %Y}"></span>'
        f'<span hidden data-pagefind-sort="date:{d.isoformat()}"></span><span hidden data-pagefind-meta="date:{long_date(d)}"></span>')
    kp = "".join(f"<li>{md(x)[3:-4] if md(x).startswith('<p>') else md(x)}</li>" for x in st.get("key_points", []))
    rail_kp = f'<section class="rail-block kp" aria-labelledby="kp-h"><h2 id="kp-h" class="rail-h">Key points</h2><ol>{kp}</ol></section>' if kp else ""
    rail_tags = (f'<section class="rail-block" aria-labelledby="tp-h"><h2 id="tp-h" class="rail-h">Topics</h2><p class="rail-tags">'
                 + " ".join(f'<a href="{root}topic/{topic_slug(t)}/">{esc(t)}</a>' for t in st["tags"]) + "</p></section>") if st["tags"] else ""
    mock = ""
    norm = lambda x: re.sub(r"\W+", "", re.sub(r"<[^>]+>|\([^)]*\)", "", html.unescape(x or ""))).lower()
    show_dek = st["dek"] and not norm(st["html"]).startswith(norm(st["dek"])[:80])  # no dek that repeats the first line
    nav = []
    if older:
        nav.append(f'<a rel="prev" href="{story_url(older, root)}">{ARROW_L}<span>Previous<span class="visually-hidden">: {esc(older["title"])}</span></span></a>')
    if newer:
        nav.append(f'<a rel="next" class="next" href="{story_url(newer, root)}"><span>Next<span class="visually-hidden">: {esc(newer["title"])}</span></span>{ARROW}</a>')
    meta_tags = " ".join(f"<span>{esc(t)}</span>" for t in st["tags"])
    body = f"""<article class="wrap story"{"" if review else " data-pagefind-body"}>
  {filters}
  <header class="story-head">
    <p class="meta" data-pagefind-ignore><time datetime="{d.isoformat()}">{mono_date(d)}{" · " + esc(st["time"]) + " ET" if st["time"] else ""}</time>{f' <span class="sep" aria-hidden="true">|</span> <span class="meta-tags">{meta_tags}</span>' if meta_tags else ""}</p>
    <h1>{esc(st["title"])}</h1>
    {f'<p class="dek">{esc(st["dek"])}</p>' if show_dek else ""}
  </header>
  {f'<aside class="rail rail-top" aria-label="Key points" data-pagefind-ignore>{rail_kp}</aside>' if rail_kp else ""}
  <div class="prose story-body">{number_sections(st["html"])}</div>
  <aside class="rail rail-side" aria-label="Story details" data-pagefind-ignore>
    {rail_tags}
    {f'<section class="rail-block sources" aria-labelledby="src-h"><h2 id="src-h" class="rail-h">Sources</h2><ol>{srcs}</ol></section>' if srcs else ""}
  </aside>
  <footer class="story-foot" data-pagefind-ignore><p class="nia">{esc(site["disclaimer"])}</p>{f'<nav class="pn" aria-label="More stories">{"".join(nav)}</nav>' if nav else ""}</footer>
</article>"""
    url = site["base_url"] + story_url(st)
    pub = f'{d.isoformat()}T{(st["time"] or "06:00")}:00-04:00'
    ld = {"@context": "https://schema.org", "@type": "NewsArticle", "headline": st["title"][:110], "description": st["dek"],
          "datePublished": pub, "dateModified": pub, "url": url, "mainEntityOfPage": url,
          "image": [site["base_url"] + "assets/og.png"], "inLanguage": "en-US",
          "author": [{"@type": "Person", "name": site["author"]}], "publisher": org_ld(site),
          "isPartOf": {"@id": site["base_url"] + "#website"}, "keywords": st["tags"], "wordCount": st["words"],
          "citation": [u for _, u in st["sources"]]}
    if review or st["mock"]:
        banner = ('<div class="review-banner" role="note"><strong>' + ("Local mock" if st["mock"] else "Review copy")
                  + '</strong> · not published, not indexed</div>')
        return page(site, root, st["title"], body, st["dek"], kind="article", jsonld=[ld], noindex=True, banner=banner)
    return page(site, root, st["title"], body, st["dek"], url, kind="article", jsonld=[ld],
                head_extra=f'<meta property="article:published_time" content="{pub}">' +
                "".join(f'<meta property="article:tag" content="{esc(t)}">' for t in st["tags"]))


def render_issues_index(site, issues):
    C = {**DEFAULT_COPY, **site.get("copy", {})}
    root = "../"
    months, out = {}, []
    for i in issues:
        months.setdefault((i["date"].year, i["date"].month), []).append(i)
    for (y, m), group in months.items():
        rows = "".join(
            f'<li><a href="{root}issues/{i["slug"]}/"><time datetime="{i["date"].isoformat()}">{i["date"]:%b} {i["date"].day:02d}</time>'
            f'<span class="row-title">{esc(i["title"])}</span>{ARROW}</a></li>' for i in group)
        out.append(f'<section class="month"><h2 class="month-h">{dt.date(y, m, 1):%B %Y}</h2><ol class="rows">{rows}</ol></section>')
    body = f"""<section class="wrap page" aria-labelledby="issues-title">
  <header class="page-head"><h1 id="issues-title">Archive</h1><p class="sub">{esc(C["archive_sub"])}</p></header>
  {"".join(out) or "<p>No issues yet.</p>"}
</section>"""
    return page(site, root, "Archive", body, C["archive_sub"], f'{site["base_url"]}issues/')


def render_about(site):
    root = "../"
    C = {**DEFAULT_COPY, **site.get("copy", {})}
    rows = []
    for label, val in C.get("about_rows", []):
        if isinstance(val, list):
            v = "".join(f'<div class="team"><strong>{esc(a)}</strong><span>{esc(b)}</span></div>' for a, b in val)
        else:
            v = f"<p>{esc(val)}</p>"
        rows.append(f'<div class="about-row"><h2>{esc(label)}</h2><div>{v}</div></div>')
    body = f"""<article class="wrap page">
  <header class="page-head"><h1>About</h1><p class="sub">{esc(C["about_sub"])}</p><span class="rule-accent" aria-hidden="true"></span></header>
  <div class="about-rows">{"".join(rows)}</div>
  <p class="about-foot">{esc(C["about"].format(**site))}</p>
</article>"""
    return page(site, root, "About", body, C["about_sub"], f'{site["base_url"]}about/', jsonld=[org_ld(site)])


def render_disclosures(site):
    root = "../"
    text = site.get("disclosures") or site["disclaimer"]
    body = f"""<article class="wrap page">
  <h1>Disclosures</h1>
  <p>{esc(text)}</p>
</article>"""
    return page(site, root, "Disclosures", body, text, f'{site["base_url"]}disclosures/')


def render_primers(site, issues):
    C = {**DEFAULT_COPY, **site.get("copy", {})}
    root = "../"
    items = []
    for i in issues:  # newest first
        p = next((s for s in i["sections"] if s["cls"] == "primer"), None)
        if p:
            items.append((i, p))
    if items:
        i, p = items[0]
        latest = (f'<article class="primer-latest"><p class="meta"><time datetime="{i["date"].isoformat()}">{mono_date(i["date"])}</time></p>'
                  f'<h2><a href="{root}issues/{i["slug"]}/#k-primer">{esc(p["title"] or "SI Primer")}</a></h2>'
                  f'<p><a class="read" href="{root}issues/{i["slug"]}/#k-primer">Read primer {ARROW}</a></p></article>')
        rows = "".join(
            f'<li><a href="{root}issues/{i["slug"]}/#k-primer"><span class="num">{n:02d}</span><span class="row-title">{esc(p["title"] or "SI Primer")}</span>'
            f'<time datetime="{i["date"].isoformat()}">{mono_date(i["date"])}</time></a></li>'
            for n, (i, p) in enumerate(reversed(items), 1))
        lst = f'{latest}<ol class="rows numbered" aria-label="All lessons, in order">{rows}</ol>'
    else:
        lst = "<p>No lessons yet.</p>"
    body = f"""<section class="wrap page" aria-labelledby="primers-title">
  <header class="page-head"><h1 id="primers-title">Primer</h1><p class="sub">{esc(C["primer_sub"])}</p></header>
  {lst}
</section>"""
    return page(site, root, "Primer", body, C["primer_sub"], f'{site["base_url"]}primers/')


def render_subscribe(site):
    C = {**DEFAULT_COPY, **site.get("copy", {})}
    root = "../"
    if SIGNUP_OPEN[0]:
        inner = f'<p>{esc(C["subscribe_open"])}</p></section>{signup_block(site, root, bare=True)}'
    else:
        inner = f'<p>Subscribe by <a href="{root}feed.xml">RSS</a>.</p></section>'
    body = f"""<section class="wrap page" aria-labelledby="sub-title">
  <h1 id="sub-title">Subscribe</h1>
  {inner}"""
    return page(site, root, "Subscribe", body, "Subscribe to " + site["name"] + ".", f'{site["base_url"]}subscribe/')


SEARCH_JS = """<link href="../pagefind/pagefind-ui.css" rel="stylesheet">
<script src="../pagefind/pagefind-ui.js"></script>
<script>
window.addEventListener('DOMContentLoaded', function(){
  var ui = new PagefindUI({ element: '#search', showSubResults: true, showImages: false, resetStyles: false,
    excerptLength: 26, pageSize: 8, autofocus: false,
    translations: { placeholder: 'Search', zero_results: 'No results for [SEARCH_TERM].' } });
  var q = new URLSearchParams(location.search).get('q');
  if (q) { ui.triggerSearch(q); }
  var input = document.querySelector('#search .pagefind-ui__search-input');
  if (input) { input.setAttribute('aria-label', 'Search issues, briefs and primers'); if (!q) input.focus(); }
});
</script>"""


def render_search(site):
    C = {**DEFAULT_COPY, **site.get("copy", {})}
    root = "../"
    body = f"""<section class="wrap page" aria-labelledby="search-title">
  <header class="page-head"><h1 id="search-title">Search</h1></header>
  <div id="search" class="pf"></div>
  <noscript><p>Search needs JavaScript. The <a href="../#archive">archive</a> lists every issue.</p></noscript>
</section>"""
    return page(site, root, "Search", body, f"Search every issue of {site['name']}.", f'{site["base_url"]}search/',
                head_extra=SEARCH_JS)


def render_404(site):
    C = {**DEFAULT_COPY, **site.get("copy", {})}
    root = "/" + site["base_url"].split("//", 1)[-1].split("/", 1)[-1] if "//" in site["base_url"] else "/"
    body = f'<section class="wrap page"><header class="page-head"><p class="meta">404</p><h1>Page not found</h1></header><p><a class="read" href="{root}">Back to the feed {ARROW}</a></p></section>'
    return page(site, root, "Not found", body, noindex=True)


def render_feed(site, issues):
    def cdata(s):
        return "<![CDATA[" + s.replace("]]>", "]]]]><![CDATA[>") + "]]>"
    items = []
    for st in FEED_STORIES[:100]:
        url = site["base_url"] + story_url(st)
        hh, mm = (st["time"].split(":") + ["0"])[:2] if st["time"] else ("6", "0")
        pub = email.utils.format_datetime(dt.datetime.combine(st["date"], dt.time(int(hh), int(mm)), tzinfo=dt.timezone(dt.timedelta(hours=-4))))
        srcs = "".join(f'<li><a href="{esc(u)}">{esc(l)}</a></li>' for l, u in st["sources"])
        content = st["html"] + (f"<p><strong>Sources</strong></p><ol>{srcs}</ol>" if srcs else "")
        cats = "".join(f"    <category>{esc(t)}</category>\n" for t in st["tags"])
        items.append((st["date"], f"""  <item>
    <title>{esc(st["title"])}</title>
    <link>{url}</link>
    <guid isPermaLink="true">{url}</guid>
    <pubDate>{pub}</pubDate>
    <description>{esc(st["dek"] or st["title"])}</description>
{cats}    <content:encoded>{cdata(content)}</content:encoded>
  </item>"""))
    for i in issues[:50]:
        url = f'{site["base_url"]}issues/{i["slug"]}/'
        pub = email.utils.format_datetime(dt.datetime.combine(i["date"], dt.time(6, 0), tzinfo=dt.timezone(dt.timedelta(hours=-4))))
        content = (f"<p><strong>The short version</strong></p>{i['short_html']}" if i["short_html"] else "") + i["lead_html"]
        if i["horizon"]:
            content += f'<h2>{esc(i["horizon"]["title"])}</h2>{i["horizon"]["html"]}'
        content += "".join(f'<h2>{esc(s["kicker"])}{": " + esc(s["title"]) if s["title"] else ""}</h2>{s["html"]}' for s in i["sections"])
        content += i["disclaimer_html"] or f"<p><em>{esc(site['disclaimer'])}</em></p>"
        cats = "".join(f"    <category>{esc(t)}</category>\n" for t in i["tags"])
        items.append((i["date"], f"""  <item>
    <title>{esc(i["title"])}</title>
    <link>{url}</link>
    <guid isPermaLink="true">{url}</guid>
    <pubDate>{pub}</pubDate>
    <description>{esc(i["dek"] or i["title"])}</description>
{cats}    <content:encoded>{cdata(content)}</content:encoded>
  </item>"""))
    items = [x for _, x in sorted(items, key=lambda t: t[0], reverse=True)]
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
    urls += [(site["base_url"] + story_url(st), st["date"].isoformat()) for st in FEED_STORIES]
    if HAVE_STORIES[0]:
        urls += [(site["base_url"] + "issues/", today)] + [(f'{site["base_url"]}topic/{topic_slug(t)}/', today) for t in TOPICS]
    body = "".join(f"  <url><loc>{esc(u)}</loc><lastmod>{m}</lastmod></url>\n" for u, m in urls)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{body}</urlset>\n'


def render_robots(site):
    path = "/" + site["base_url"].split("//", 1)[-1].split("/", 1)[-1] if "//" in site["base_url"] else "/"
    return f"User-agent: *\nAllow: /\nDisallow: {path}review/\n\nSitemap: {site['base_url']}sitemap.xml\n"


# ---------------------------------------------------------------- build
def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def run_pagefind(have_issues, have_stories=False):
    """Index only published issue pages (lead essay, briefs, primer, signal as sub-results)."""
    import subprocess
    if not have_issues and not have_stories:
        print("  search: no published issues yet, index skipped")
        return
    cmd = ["npx", "-y", "pagefind@1.5.2", "--site", str(OUT), "--glob", "{issues,stories}/**/*.html"]
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
        for d in sorted(STORIES.iterdir()) if STORIES.exists() else []:
            if d.is_dir() and DATE_RE.match(d.name):
                n = len([f for f in d.glob("*.md") if not STORY_SKIP.search(f.stem)])
                print(f"stories/{d.name}", day_status(d.name), f"{n} file(s)")
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
    for k in ("paper", "paper_deep", "ink", "ink_soft", "muted", "graphite", "rule", "accent", "accent_text"):
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
    SIGNUP_OPEN[0] = bool(site.get("signup_action") or site.get("form_endpoint"))
    VARIANT[0] = os.environ.get("SI_VARIANT", "").upper()
    write(OUT / ".nojekyll", "")
    write(OUT / "disclosures" / "index.html", render_disclosures(site))
    stories_all = load_stories(include_review=args.review)
    pub_stories = [st for st in stories_all if st["status"] == "approved"]
    rev_stories = [st for st in stories_all if st["status"] == "review"]
    ALL_STORIES[:] = pub_stories
    FEED_STORIES[:] = [st for st in pub_stories if not st["mock"]] if os.environ.get("SI_MOCK") != "1" else pub_stories
    # with no published stories yet, each published issue is a feed entry (its own headline, dek, date, topics)
    entries = FEED_STORIES or [{"slug": i["slug"], "day": i["slug"], "date": i["date"], "time": "", "order": 0, "title": i["title"],
                                "dek": i["dek"], "tags": i["tags"], "mock": False, "url": f'issues/{i["slug"]}/'} for i in issues]
    HAVE_STORIES[0] = bool(entries)
    if entries:
        write(OUT / "index.html", render_feed_page(site, entries, "./"))
        for t in TOPICS:
            write(OUT / "topic" / topic_slug(t) / "index.html", render_feed_page(site, entries, "../../", topic_slug(t)))
        write(OUT / "issues" / "index.html", render_issues_index(site, issues))
        for n, st in enumerate(FEED_STORIES):
            write(OUT / "stories" / st["day"] / st["slug"] / "index.html",
                  render_story(site, st, FEED_STORIES[n - 1] if n > 0 else None, FEED_STORIES[n + 1] if n + 1 < len(FEED_STORIES) else None))
    else:
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
    for st in rev_stories:
        if not args.review:
            continue
        slug = f'{st["day"]}-{review_token(st["day"])}'
        write(OUT / "review" / slug / st["slug"] / "index.html", render_story(site, st, None, None, review=True, root="../../../"))
        review_links.append((f'{st["day"]}/{st["slug"]}', f'{site["base_url"]}review/{slug}/{st["slug"]}/', f"review/{slug}/{st['slug']}/"))
    write(OUT / "feed.xml", render_feed(site, issues))
    write(OUT / "sitemap.xml", render_sitemap(site, issues))
    write(OUT / "robots.txt", render_robots(site))
    write(ROOT / ".review-links.json", json.dumps(review_links, indent=1))
    import xml.dom.minidom
    xml.dom.minidom.parseString((OUT / "feed.xml").read_bytes())
    xml.dom.minidom.parseString((OUT / "sitemap.xml").read_bytes())
    if not args.no_search:
        run_pagefind(bool(issues), bool(FEED_STORIES))
    print(f"Built {len(issues)} published issue(s), {len(FEED_STORIES)} stor{'y' if len(FEED_STORIES) == 1 else 'ies'}"
          f"{' (incl. LOCAL MOCKS)' if any(st['mock'] for st in FEED_STORIES) else ''}, {len(review_links)} review cop(ies) → {OUT}")
    for i in issues:
        print(f"  published  No. {i['number']}  {i['slug']}  {i['title']}")
    for slug, url, _ in review_links:
        print(f"  review     {slug}  {url}")


if __name__ == "__main__":
    sys.exit(main())
