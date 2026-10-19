#!/usr/bin/env python3
"""Full-page screenshots with the box's Chrome (Playwright, no browser download).

  python3 shots.py URL OUT.png [--mobile] [--viewport]    one shot
  python3 shots.py --serve DIR ...                        serve DIR on localhost first (for local review copies)
"""
import sys, time
from playwright.sync_api import sync_playwright

CHROME = "/usr/bin/google-chrome"


def shoot(jobs):
    """jobs: list of (url, out_path, mobile: bool, full_page: bool)"""
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=CHROME, args=["--no-sandbox", "--hide-scrollbars"])
        for url, out, mobile, full in jobs:
            ctx = b.new_context(viewport={"width": 390, "height": 844} if mobile else {"width": 1440, "height": 900},
                                device_scale_factor=2 if mobile else 1, is_mobile=mobile, has_touch=mobile,
                                reduced_motion="reduce")
            pg = ctx.new_page()
            pg.goto(url, wait_until="networkidle", timeout=60000)
            pg.evaluate("document.fonts && document.fonts.ready")
            time.sleep(0.4)
            pg.screenshot(path=out, full_page=full)
            ctx.close()
            print(out)
        b.close()


if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    shoot([(a[0], a[1], "--mobile" in sys.argv, "--viewport" not in sys.argv)])
