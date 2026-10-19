# Asymptote design tokens (site and email)

Source of truth: `brand/site.json` (keys in brackets). Last design pass: Oct 19, 2026 (pass 4). Design rationale: `DESIGN_NOTES.md`.

## Color: cool bone paper, near-black ink, one signal-orange accent
| Token | Hex | Use |
|---|---|---|
| paper [`paper`] | `#ECEAE4` | page background (with faint grain on the site) |
| paper deep [`paper_deep`] | `#E2DFD7` | Primer panel, code and input background |
| ink [`ink`] | `#111110` | text, headlines, buttons, strong rules (16.5:1 on paper) |
| ink soft [`ink_soft`] | `#3A3936` | deks, secondary text |
| muted [`muted`] | `#5C5B57` | metadata, mono labels (≥ 5.4:1 on paper) |
| rule [`rule`] | `#C9C5BC` | hairlines, borders, grid |
| accent [`accent`] | `#E4500E` | **marks only**: trace dot, registration marks, focus ring, underlines, list markers. 3.2:1 on paper, so never for small text |
| accent text [`accent_text`] | `#AC3406` | accent-colored **text and links** (≥ 4.5:1 on paper and paper deep) |

**Email:** use `accent_text` for any accent-colored words or links, and `accent` only for rules, bullets and blocks.

## Type: one serif, one mono, no grotesk
- **Serif** (headlines, deks, body): `'Newsreader', Georgia, 'Times New Roman', Times, serif`. Self-hosted, Latin subset, opsz axis, weights 400–700, upright and italic. Headlines are 500 at display opsz, body is 400.
- **Mono** (labels, readout, tags, inputs): `'IBM Plex Mono', 'Courier New', Courier, monospace`. Weights 400/500, uppercase, tracking 0.06–0.08em, ~0.72rem.
- Email-safe fallbacks: Georgia for the serif, Courier New for the mono.
- Measure ~65ch. Body ~17–19.6px with 1.62 line-height.

## System
- **Readout** (mono, real values only): `ASY/001 · 2026-10-19 · 09 MIN · 2,166 W · 22 SRC` (issue number, date, reading time, word count, distinct sources). Screen readers get a spoken version.
- **Quoted labels**: tight mono codes in accent quotes, e.g. “BY 2036”, “BRIEFS/03”, “PRIMER”.
- **Tags**: bracketed and square, `[AI] [ENERGY]`, from the fixed list AI, Compute, Energy, Bio, Space, Quantum, Robotics, Policy. No pills.
- **Signal trace**: a hairline waveform seeded by the issue, closing on a dashed asymptote with a 2026–2036 scale and one accent dot. It draws in once on load (static under reduced motion).
- **Construction layer** (desktop ≥ 1100px): registration marks, a margin ruler, and a faint baseline/column grid.
- **Headline decode** on first load, as an aria-hidden overlay. Skipped under reduced motion.

## URLs
- Home: `https://jacode21.github.io/si-journal/`
- Issue: `https://jacode21.github.io/si-journal/issues/YYYY-MM-DD/` (Issue No. 1: `/issues/2026-10-19/`)
- Primers: `/primers/`, Subscribe: `/subscribe/`, Search: `/search/?q=term`, RSS: `/feed.xml`, Sitemap: `/sitemap.xml`
- Social card: `/assets/og.png` (1200×630)
