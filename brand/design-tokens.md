# Asymptote design tokens (site and email)

Source of truth: `brand/site.json` (keys in brackets). Last design pass: Oct 19, 2026.

## Color: one accent, no tech blue
| Token | Hex | Use |
|---|---|---|
| paper [`paper`] | `#F5EFE4` | page background |
| paper deep [`paper_deep`] | `#EDE4D3` | Primer panel, code background |
| ink [`ink`] | `#1F1A15` | text, headlines, buttons (15.1:1 on paper) |
| ink soft | `#4A4037` | deks, secondary text (8.8:1) |
| muted [`muted`] | `#6A5F53` | metadata, labels (5.4:1) |
| rule [`rule`] | `#DCD0BC` | hairlines, borders |
| accent [`accent`] | `#A8482A` | terracotta: kickers, links underline, list markers (5.1:1 on paper, 4.6:1 on paper deep) |

## Type: one serif, one mono, no grotesk
- **Serif** (headlines and body): `'Newsreader', Georgia, 'Times New Roman', Times, serif`. Google Fonts, opsz 6–72, weights 300–700, plus italics. Headlines are 500 at opsz 72, body is 400.
- **Mono** (labels, metadata, inputs): `'IBM Plex Mono', 'Courier New', Courier, monospace`. Weights 400/500, uppercase, letter-spacing 0.06em, about 0.74rem.
- Email-safe fallbacks: Georgia for the serif, Courier New for the mono.
- Measure 65ch. Body 17–19.6px with 1.62 line-height.

## Signature touches, used sparingly
- One quoted label: the “BY 2036” section (accent quote marks, hairline rule above, softer italic).
- A hairline signal trace (seismograph) per issue, seeded by headline and date, in muted ink with a single accent dot.
- A typed one-line kicker at the top of each issue (skipped under reduced motion).

## URLs
- Home: `https://jacode21.github.io/si-journal/`
- Issue: `https://jacode21.github.io/si-journal/issues/YYYY-MM-DD/` (Issue No. 1: `/issues/2026-10-19/`)
- Primer on an issue: `.../issues/YYYY-MM-DD/#k-primer`. All primers: `/primers/`
- Subscribe: `/subscribe/`, Search: `/search/?q=term`, RSS: `/feed.xml`, Sitemap: `/sitemap.xml`
- Social card: `/assets/og.png` (1200×630)
