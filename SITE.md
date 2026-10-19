# Asymptote: the website

Static site for the daily publication. A small Python generator (`build.py`, using python-markdown) turns the issue markdown into `docs/`, and GitHub Pages serves `docs/` from `main`.

- **Live:** https://jacode21.github.io/si-journal/
- **Issue URL pattern:** `https://jacode21.github.io/si-journal/issues/YYYY-MM-DD/`
- **Repo:** https://github.com/jacode21/si-journal

## Commands (run in /workspace/si-journal)

| Command | What it does |
|---|---|
| `./si build` | Builds `docs/` with approved issues only, plus the Pagefind search index |
| `./si preview` | Builds and serves the site at http://localhost:8000 |
| `./si review` | Renders every `review` issue and saves full-page screenshots to `review/<date>/desktop.png` and `mobile.png` |
| `./si review --push` | The same, and also publishes the unlisted link `/review/<date>-<token>/` |
| `./si approve <date>` | Writes `issues/<date>/status` = `approved`, then rebuilds and publishes |
| `./si publish` | Builds, commits and pushes |
| `./si shots` | Screenshots the live site to `screenshots/` and `preview.png` |
| `python3 og.py` | Regenerates the social card `site/assets/og.png` after a name or tagline change |

## Adding an issue

Preferred: one file, `issues/YYYY-MM-DD/issue.md`.

```markdown
---
issue: 2
date: 2026-10-20
headline: The headline
dek: One-sentence dek.
subject: Email subject
preview: Email preview text
topics: AI, Compute, Energy        # allowed: AI, Compute, Energy, Bio, Space, Quantum, Robotics, Policy (others print a warning)
kicker: Optional line that types itself out at the top. Default: the first sentence of the short version.
status: review                     # draft | review | approved. An issues/<date>/status file overrides this.
---
# The headline

## The short version
Three lines or fewer.

## What happened
## Why it matters
## The investor angle
## What this looks like by 2036       ← quiet treatment with a quoted "BY 2036" label
## Briefs                             ← ### per brief, optional "Tags: X, Y" line
## SI Primer: Day N · Title           ← also listed on /primers/
## Signal to watch
## Not investment advice
```

Split files also work: `lead-essay.md` plus optional `briefs.md`, `primer.md`, `signal.md`, `short.md` and `disclaimer.md`. If `issue.md` exists, it wins.

## The review gate

- **draft** (the default): not built.
- **review**: built only as an unlisted review copy at `/review/<date>-<token>/`. The copy is marked noindex and nofollow, carries a REVIEW COPY banner, and is left out of the home page, archive, RSS, sitemap and search. The token comes from `.review-secret`, which stays local and out of git.
- **approved**: published on the home page and archive, in RSS, the sitemap and search.

> **GitHub Pages is public, so a review copy is unlisted, not private.** Anyone who has the link, or who browses the public repo's `docs/review/`, can read it. Review copies only go online when you run `./si review --push`. By default they stay on the box as screenshots. Issue sources are only committed once an issue is approved.

## Config: `brand/site.json`

`name`, `tagline`, `description`, `disclaimer`, `base_url`, colors (`paper`, `paper_deep`, `ink`, `muted`, `rule`, `accent`), fonts (`serif`, `mono`), `topics`, `copy` (all site microcopy), `signup_action` (alias `form_endpoint`), `signup_provider`, optional `signup_fields` and `signup_hidden`, `ornament` (generative sprig mark, off), and `trace` (signal-trace hairline, on). Edit, then run `./si publish`.

Search is Pagefind 1.5.2 via npx, run by `build.py`. Press `/` or Cmd-K to focus it. Filters: topic, year, month. Only issue pages are indexed. Briefs, primer and other headings show up as sub-results.

No custom domain is set (there's no CNAME). Domains are tracked in `brand/domains.md` (Editor-owned).
