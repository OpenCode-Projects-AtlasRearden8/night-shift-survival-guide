# STATUS

**Project:** Night Shift Survival Guide — education-only manual for night-shift
workers (nurse-flavored), markdown source + dependency-free static site builder.
**Date:** October 27, 2026
**Owner:** Asdale Dynamics, LLC (Dylan Asdale, RN)

## What was built

- **`docs/` — the manual** (10 markdown files, ~10,000 words):
  - `00-introduction.md` — who it's for, scope note (education-only), 60-second version
  - `01-sleep-window-planning.md` — anchor sleep, three rotation patterns, pre-shift naps
  - `02-daytime-sleep-environment.md` — dark / quiet / cool / boring environment setup
  - `03-light-and-caffeine-timing.md` — sunglasses strategy, caffeine half-life concept
  - `04-meals-and-snacks.md` — evening-is-your-morning meal plan, packing lists, plate guide
  - `05-driving-home-safety.md` — sleepiness signs, countermeasures, do-not-drive ladder
  - `06-family-boundary-scripts.md` — copy-paste scripts for partners, kids, parents,
    neighbors, coworkers, and yourself
  - `07-low-energy-recovery-day.md` — three-block recovery day plan (ADHD-friendly)
  - `08-shift-cycle-planner.md` — planner worksheet: constants, week map, checklists, review loop
  - `09-glossary.md` — plain-English glossary of all terms used
- **`build.py`** — zero-dependency (Python stdlib) build script: mini-markdown
  renderer (headings with auto-anchors, bold/italic/inline code, links with
  `.md → .html` rewriting, nested lists, task checkboxes, tables, blockquotes)
  plus page templating, sidebar nav, prev/next pager, and a landing page.
- **`templates/`** — `page.html` template and `styles.css` (warm cream theme,
  automatic dark mode, mobile layout, print-tuned for the worksheet).
- **`site/`** — the generated static site (12 files: index + 10 chapters + stylesheet).
  Fully local: no external fonts, scripts, trackers, or network references.
- **`tests/test_site.py`** — 21-test unittest suite (see Verification below).
- **`Makefile`** — `make build`, `make test`, `make clean`.
- **`README.md`** — project overview, quick start, test instructions, structure.
- **`LICENSE`** — MIT, `Copyright (c) 2026 Asdale Dynamics, LLC`.

## How to run it

```bash
python3 build.py                          # build into ./site
python3 build.py --clean                  # wipe + rebuild
python3 build.py --out /tmp/elsewhere     # build anywhere
make test                                 # run the test suite
```

Then open `site/index.html` in any browser. No server, no install, no network.
Requires only Python 3.8+.

## Verification results

- `python3 build.py --clean` — exit 0, builds 10 chapters + index into `site/`.
- `python3 -m unittest discover -s tests -v` — **21/21 tests pass**, covering:
  - markdown renderer unit tests (inline formatting, escaping, nested lists,
    task lists, tables, blockquotes, heading id uniqueness, continuation lines)
  - real-build integration: expected page inventory, page chrome (doctype,
    charset, disclaimer, copyright on every page), no leftover template
    placeholders, no leftover markdown artifacts
  - link integrity: every internal link resolves to a generated file; every
    `#anchor` target exists on its destination page
  - local-first guarantee: no `<script>` tags, no external `http(s)` references
  - worksheet interactivity (20+ checkboxes) and print stylesheet presence
  - glossary core-term coverage; pager navigation; every doc has an H1
  - build determinism: two consecutive builds are byte-identical
- Manual checks: all 11 HTML pages pass an HTMLParser tag-balance audit;
  repo scanned for stray non-ASCII artifacts and accidental URLs (clean);
  `python3 -m py_compile` clean for both scripts.
- Git: initialized and committed locally (plain commit message, existing git
  identity, no Co-authored-by trailers, nothing pushed).

## Known gaps / limits

- **Mini-markdown renderer scope:** supports the constructs this manual uses
  (documented in README). It does not aim for full CommonMark parity — no
  images, footnotes, reference-style links, or setext headings.
- **No search, no JavaScript, no RSS** — deliberate: local-first and dead simple.
- The worksheet is fill-in-able in HTML and prints well, but there is no
  PDF/PDF-A export.
- **English only**, single theme, no per-reader font-size switcher (browser
  zoom and dark mode are respected).
- Content is education-only by design; it deliberately avoids medical
  specifics (no dosage, no clinical protocols, no diagnostic guidance) and
  points readers to their own clinician instead.
- Potential future additions: a chapter for on-call/call-home hybrid schedules,
  a partner-facing one-pager, and translations.
