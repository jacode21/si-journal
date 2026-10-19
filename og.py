#!/usr/bin/env python3
"""Regenerate site/assets/og.png (1200x630 social card) from brand/site.json. Run after a name/tagline change."""
import json, sys
sys.path.insert(0, ".")
import build
from playwright.sync_api import sync_playwright
s = json.load(open("brand/site.json"))
svg = build.trace_svg(s["name"], s["accent"], "")
html = f'''<!doctype html><html><head><link href="https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,500;1,6..72,400&family=IBM+Plex+Mono&display=swap" rel="stylesheet">
<style>html,body{{margin:0;width:1200px;height:630px;background:{s["paper"]};color:{s["ink"]}}}
.c{{box-sizing:border-box;width:1200px;height:630px;padding:84px 96px;display:flex;flex-direction:column;justify-content:space-between}}
.k{{font-family:'IBM Plex Mono',monospace;font-size:22px;letter-spacing:.08em;text-transform:uppercase;color:{s["accent"]}}}
h1{{font-family:Newsreader,serif;font-weight:500;font-size:160px;line-height:1;letter-spacing:-.03em;margin:0}}
p{{font-family:Newsreader,serif;font-style:italic;font-size:44px;color:#4A4037;margin:24px 0 0;max-width:900px;line-height:1.25}}
svg{{width:100%;height:40px;color:{s["muted"]}}}</style></head><body><div class="c">
<div class="k">Daily · The next decade, for investors</div>
<div><h1>{build.esc(s["name"])}</h1><p>{build.esc(s["tagline"])}</p></div>{svg}</div></body></html>'''
open("/tmp/og-card.html", "w").write(html)
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
    pg = b.new_page(viewport={"width": 1200, "height": 630})
    pg.goto("file:///tmp/og-card.html", wait_until="networkidle"); pg.evaluate("document.fonts.ready")
    pg.screenshot(path="site/assets/og.png"); b.close()
print("site/assets/og.png")
