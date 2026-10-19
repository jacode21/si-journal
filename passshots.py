#!/usr/bin/env python3
"""Design-pass screenshots: python3 passshots.py <outdir> [base_url]
Six pages at 1440 and 390 widths, full page."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shots
out = sys.argv[1]; base = sys.argv[2] if len(sys.argv) > 2 else "https://jacode21.github.io/si-journal/"
os.makedirs(out, exist_ok=True)
pages = {"home": "", "issue": "issues/2026-10-19/", "about": "about/", "primer": "primers/",
         "search": "search/?q=grid", "subscribe": "subscribe/"}
jobs = []
for name, path in pages.items():
    jobs.append((base + path, f"{out}/{name}-1440.png", False, True))
    jobs.append((base + path, f"{out}/{name}-390.png", True, True))
shots.shoot(jobs)
