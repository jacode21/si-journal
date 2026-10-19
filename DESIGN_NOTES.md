# Asymptote: design notes

The brief: future-minimal (Rubin × Abloh), "technology with a soul", one serif (Newsreader), one mono (IBM Plex Mono), one accent.
The test for each pass: *would someone think a careful machine that reads poetry made this?*
Each pass has before/after screenshots at 1440 and 390 px in `screenshots/pass-N/{before,after}/`, plus Lighthouse summaries in `screenshots/pass-N/lh-*.txt`.

## Pass 1 — Oct 19, ~01:08–01:18 ET: from warm-classic to instrument

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

**Results:** Lighthouse mobile performance went from 78 to 98 on home and 96 on the issue (LCP 4.0 s → 2.4–2.6 s). Desktop performance is 100, CLS is 0 or close to it, and SEO and best practices are 100. Accessibility dropped to 96 on the issue page because of one contrast failure, fixed in pass 2.

## Pass 2 — Oct 19, ~01:18–01:22 ET: consistency, contrast, search hygiene

**Critique of pass 1**
- **Accessibility:** Lighthouse flagged the orange "PRIMER/D01" label on the tinted Primer panel at 4.32:1, below the 4.5:1 minimum for small text.
- Search excerpts began with leaked metadata ("19, 2026No. 1 The Grid Said No…"). The hidden filter and meta spans were being indexed as text.
- The quoted-label system was half applied. Issue sections were quoted, but page kickers (About, Search, Subscribe, Lessons) and "Disclosures" were not.
- Briefs' topic lines used "AI · COMPUTE" while page tags used `[AI]`. Two dialects for the same thing.
- On issue pages, "Not investment advice. Just a clearer view." showed twice: once in Disclosures, once as the footer sign-off.
- The disclosure rule was shorter than the other rules, because `font-size` shrank the `ch` measure.
- The signup line read "Status: soon. The morning email opens soon…". It said "soon" twice.

**Changes**
- `accent_text` is now `#AC3406`: 5.4:1 on paper, 4.9:1 on paper-deep. Synced in `brand/site.json` for the email.
- Pagefind filters, sort and meta now use the attribute form (`data-pagefind-filter="year:2026"`), so excerpts start with real prose.
- Every page kicker is a quoted mono label: “ABOUT”, “SEARCH”, “SUBSCRIBE”, “PRIMER/01”, “DISCLOSURES”. Each has a spoken name for screen readers.
- Inline topic lines in briefs and signal now render as `[AI] [COMPUTE]`, matching the tags.
- The footer sign-off is suppressed on pages that already carry Disclosures.
- The disclosure rule is now full measure; only the paragraph text is smaller.
- The signup line now reads: "The morning email opens soon. Until then, follow along by RSS."
- **Focus check:** keyboard focus on nav and search shows a 2px signal-orange ring (3.2:1 against paper, which meets the 3:1 non-text minimum). `/` jumps to search. Shots: `screenshots/pass-2/focus-*.png`.

**Results:** Lighthouse accessibility is 100 on all four runs. Mobile performance is 100 on home (LCP 1.6 s) and 96 on the issue. Desktop is 100.

## Pass 3 — Oct 19, ~01:22–01:26 ET: the system reaches every page, and the CSS is inlined

**Critique of pass 2**
- Only the home and issue pages felt machine-made. About, Primer, Search and Subscribe fell back to plain editorial pages with no readout and no trace, so the system broke as you navigated.
- The About page's dek repeated the masthead tagline ("Always closer." twice on one screen).
- The Primer list used a different date dialect ("NO. 1 · OCTOBER 19, 2026") from the archive (`ASY/001 · 2026-10-19`).
- The nav never showed where you were (no `aria-current`).
- **Performance:** the one remaining blocker was the 15 KB stylesheet (about 150 ms render-blocking on mobile, LCP on the dek). Mobile issue score was 96.

**Changes**
- Every secondary page gets an instrument readout with real counts and a compact, static, seeded trace (`aria-hidden`):
  - About: `ASY/ABOUT · 01 ISSUE · 01 PRIMER · SINCE 2026-10-19`
  - Primer: `ASY/PRIMER · 01 LESSON · ONE A DAY`
  - Search: `ASY/SEARCH · INDEX 01 ISSUE · PAGEFIND`
  - Subscribe: `ASY/SUBSCRIBE · DAILY · SIGNUP NOT YET OPEN`
  Values come from the build, and singular/plural is handled.
- The About dek is removed; the H1 and the first paragraph carry it.
- Primer rows now use the archive's readout format.
- The nav gets `aria-current="page"` with a signal-orange underline.
- **CSS is inlined** (comments stripped) on every page, so nothing render-blocking remains. Fonts are still self-hosted and preloaded. `assets/style.css` is kept for anyone who links it.

**Results:** Render-blocking resources are gone on every run. Lighthouse home mobile scored 98 (LCP 2.4 s, network variance), issue mobile 96 (LCP 2.6 s, the italic dek waiting on a 143 KB font), desktop 100 on both. Accessibility, best practices and SEO are 100 everywhere.

## Pass 4 — Oct 19, ~01:26–01:30 ET: font weight and an honest Subscribe page

**Critique of pass 3**
- Mobile LCP is the italic dek, and it waits on `newsreader-italic.woff2` (143 KB), which wasn't preloaded. Both Newsreader files also carried the unused 300 weight and hinting.
- The Subscribe page was mostly empty. It also repeated itself: a "Subscribe" page header, then a second ruled block labeled “MORNING EMAIL” with one sentence. That reads like a stub, not an instrument.

**Changes**
- **Fonts** were re-cut with fontTools. The wght axis is limited to 400–700 (opsz stays for display sizes), the files are subset to Latin + punctuation, and hinting is dropped. Newsreader went from 128 to 92 KB, the italic from 143 to 102 KB, and Plex Mono from 15 to 12 KB each. `@font-face` ranges are updated to match.
- The italic is preloaded only where a dek is the likely LCP (home and issue pages).
- **Subscribe** is now a spec sheet: mono `dt`, serif `dd`, hairline rows (Frequency / Format / Sources / Status). Every line is true and comes from the house format, and Status is computed from `signup_action`. The signup block on this page renders bare, with no second label or rule. The form appears automatically once `signup_action` is set.

**Results** (live, published 01:30 ET): home mobile 100 (LCP 1.9 s), issue mobile 99 (LCP 2.0 s, down from 2.6 s), desktop 100/100. Accessibility, best practices and SEO are 100 on every run, CLS ≤ 0.007 and TBT 0 ms. The only flags left are cache-TTL, which GitHub Pages controls and we can't set. verify.py: ALL OK.

**Known and accepted:** U+2192 (→) isn't in Newsreader or Plex Mono, so it falls back to a system glyph wherever it appears.
