# Asymptote: design notes

The brief: future-minimal (Rubin × Abloh), "technology with a soul", one serif (Newsreader), one mono (IBM Plex Mono), one accent.
The test for each pass: *would someone think a careful machine that reads poetry made this?*
Each pass has before/after screenshots at 1440 and 390 px in `screenshots/pass-N/{before,after}/`, plus Lighthouse summaries in `screenshots/pass-N/lh-*.txt`.

## Pass 1 — Oct 19, 01:10–01:40 ET: from warm-classic to instrument

**Critique of the live v0**
- It read as a warm literary magazine, with nothing machine-made about it. Cream paper, pill tags and soft rules all said "classic".
- The headline came sixth in the stack (trace, typed line, meta, tags, kicker, H1). The hierarchy was buried.
- **Bug:** the dek was printed twice, once as the frontmatter dek and again as the italic standfirst in issue.md.
- The hero trace was a 30px hairline that read as a divider, not a signature.
- Performance: mobile Lighthouse scored 78 (LCP 4.0 s), because Google Fonts was render-blocking from two extra origins.
- The subscribe page said "The morning email" three times and "feed works" twice.
- The search index still carried the "placeholder" stub.

**Changes**
- **Palette:** cooler bone paper `#ECEAE4` with near-black ink `#111110`. The single accent is now signal orange `#E4500E`, used on marks, rules, focus rings and quote marks. Small text uses a darker shade of the same hue, `accent_text #B83A09` (4.8:1). The warmth stays in the serif italics and a faint SVG grain.
- **Construction layer** (desktop ≥1100px, decorative, `aria-hidden`): corner registration marks with a center target, a faint 28px baseline grid and column guides at the measure.
- **Instrument readout** with real values only: `ASY/001 · 2026-10-19 · 09 MIN · 2,166 W · 22 SRC` (issue, date, reading time, word count, distinct linked sources). Screen readers get a plain sentence.
- **Signature hero:** the seeded signal trace now closes on a dashed asymptote ("Always closer"). It's 1000×120 with a decade scale (2026, 2031, 2036) and draws itself in once on load; the spike lights up in orange at the end. Static under reduced motion.
- **Headline glyph-decode** on first load, once per session. An `aria-hidden` overlay scrambles while the real H1 keeps the layout (no CLS) and stays in the accessibility tree. Skipped under reduced motion.
- **Labels** are tight and technical in quotes: “LEAD”, “SHORT VERSION”, “BRIEFS/04”, “PRIMER/D01”, “SIGNAL TO WATCH”, “BY 2036”, “ARCHIVE/01”. Each has a spoken name for screen readers. Tags are now bracketed `[ENERGY]` instead of pills.
- **Hairlines:** 1px ink for structure, rule-grey for subdivision, zero radius everywhere. The short version is numbered 01/02, as is the home contents list.
- **Order:** readout → trace → typed line → “LEAD” → H1 → dek → date + tags → short version.
- **Masthead:** a mono strip on top: `ASYMPTOTE · DAILY · EST. 2026 | LATEST ASY/001 · 2026-10-19`.
- **Bug fixes:** the duplicate dek is fixed (the standfirst is dropped only when it matches the dek exactly, and no editorial text changes). The search placeholder stub is removed.
- **Performance:** fonts are self-hosted (latin woff2), with preloads for the two upright faces and `font-display: swap`.
- **Copy:** the subscribe page copy is de-duplicated.
- `brand/site.json` gained `ink_soft`, `accent_text`, `tokens_note`, and the new paper/ink/muted/rule/accent values.
