#!/usr/bin/env python3
"""Verify the live site: waits for the latest Pages build, then checks 200s, RSS/sitemap XML, and a real search."""
import json, subprocess, sys, time, urllib.request, xml.dom.minidom
BASE = json.load(open("brand/site.json"))["base_url"]
sha = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
for _ in range(40):
    r = subprocess.run(["gh", "api", "repos/jacode21/si-journal/pages/builds/latest", "--jq", ".status + \" \" + .commit"], capture_output=True, text=True).stdout.split()
    if len(r) == 2 and r[1] == sha and r[0] == "built":
        break
    time.sleep(10)
print("pages build:", r)
time.sleep(5)
ok = True
def get(path):
    req = urllib.request.Request(BASE + path + ("&" if "?" in path else "?") + f"v={int(time.time())}", headers={"User-Agent": "verify"})
    with urllib.request.urlopen(req, timeout=20) as f:
        return f.status, f.read()
for path in ["", "issues/2026-10-19/", "about/", "primers/", "search/", "subscribe/", "feed.xml", "sitemap.xml", "robots.txt",
             "assets/style.css", "assets/fonts/newsreader.woff2", "pagefind/pagefind-ui.js"]:
    try:
        st, body = get(path)
    except Exception as e:
        st, body = str(e), b""
    print(f"  {st}  /{path}"); ok &= st == 200
    if path == "feed.xml":
        d = xml.dom.minidom.parseString(body); print("     RSS well-formed, items:", len(d.getElementsByTagName("item")))
    if path == "sitemap.xml":
        d = xml.dom.minidom.parseString(body); print("     sitemap well-formed, urls:", len(d.getElementsByTagName("loc")))
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
    pg = b.new_page()
    for q in ["grid", "placeholder"]:
        pg.goto(BASE + f"search/?q={q}", wait_until="networkidle")
        pg.wait_for_timeout(1500)
        n = pg.locator(".pagefind-ui__result").count()
        print(f"  search '{q}': {n} result(s)", pg.locator(".pagefind-ui__result-link").all_inner_texts()[:3])
        if q == "grid": ok &= n >= 1
        if q == "placeholder": ok &= n == 0
    b.close()
print("ALL OK" if ok else "SOME CHECKS FAILED")
