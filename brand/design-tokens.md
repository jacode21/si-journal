# Asymptote design tokens (site and email)

Source of truth: `brand/site.json` (keys in brackets). Last update: Oct 19, 2026, design guide applied (local, not yet live). Design rationale: `DESIGN_NOTES.md`.

## Color (design guide, Oct 2026): bone paper, near-black ink, signal orange, graphite
Orange marks an active state or meaningful emphasis, never decoration.

| Token | Hex | Use |
|---|---|---|
| paper [`paper`] | `#F0EEE8` | Bone paper: page background |
| paper deep [`paper_deep`] | `#E6E3DB` | Analysis ("our view") block, code, inputs |
| ink [`ink`] | `#191918` | Near-black ink: text, headlines, strong rules (15.2:1 on paper) |
| ink soft [`ink_soft`] | `#4A4843` | Deks, mono summaries (7.9:1) |
| muted [`muted`] | `#5F5B55` | Small grey text: dates, labels, tags (5.8:1) |
| graphite [`graphite`] | `#928D85` | Graphite: dividers, separators and icons only (2.8:1, never text) |
| rule [`rule`] | `#D3CFC6` | Hairlines between rows |
| accent [`accent`] | `#D95727` | Signal orange: active tab underline, dots, short accent rules, the analysis bar. 3.4:1, so never small text |
| accent text [`accent_text`] | `#AD4217` | Orange text: topic labels, numbers, "Read primer" links (5.1:1) |

**Newsletter Desk:** the email must match these values. Small orange text uses `accent_text`; `accent` is for rules and dots only. Graphite is never used for text.

## Type: one serif + one mono
The guide names no typefaces; its mockups show a literary serif with a utilitarian mono. Self-hosted:
- **Serif** for headlines and body: Newsreader (SIL OFL). Headlines are weight 600, large, with tight tracking.
- **Mono** for data labels, dates, nav, key points and summaries: IBM Plex Mono (SIL OFL), 400/500, uppercase labels, tracking 0.08em.
- Email fallbacks: Georgia and Courier New.

## Components
- **Masthead:** the wordmark, "ALWAYS CLOSER." in small mono, then the nav FEED · ISSUES · PRIMER · ABOUT and a search icon. The active item gets an orange 2px underline.
- **Feed lead:** "The next decade, daily." with a mono descriptor and a short orange rule.
- **Topic tabs:** mono text, active underline in orange, "● LATEST" on the right.
- **Story rows:** `OCT 19, 2026 | TOPIC` with the topic in orange text, a serif headline, a 2-line mono summary, mono tags, and an arrow column behind a hairline.
- **Story page:** meta line, headline, dek. A right rail holds KEY POINTS (numbered mono), TOPICS and SOURCES (numbered). Body sections are numbered mono labels (01 WHAT HAPPENED…). The analysis section sits on paper-deep with an orange left bar. The footer reads NOT INVESTMENT ADVICE · ← PREVIOUS / NEXT →.
- **Archive:** month groups, rows of `OCT 19 · title · →`. **Primer:** the latest card, then a numbered list with dates. **About:** label/value rows (Our focus / Our approach / Our team).
- No animation, no ornament, no dashboard clutter. The waveform is retired (`trace: false`).

## URLs
- Home: `https://jacode21.github.io/si-journal/`
- Issue: `https://jacode21.github.io/si-journal/issues/YYYY-MM-DD/` (Issue No. 1: `/issues/2026-10-19/`)
- Primers: `/primers/`, Subscribe: `/subscribe/`, Search: `/search/?q=term`, RSS: `/feed.xml`, Sitemap: `/sitemap.xml`
- Social card: `/assets/og.png` (1200×630)
