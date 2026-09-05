# QRIP — Qualitative Research Intelligence Platform

A qualitative analysis workbench with everything a CAQDAS tool must have —
quotations, a code manager, memos, networks, queries, inter-coder agreement —
plus an automatic first pass that does the mechanical coding in seconds and
hands you every object to argue with.

Everything runs locally. No Node, no npm, no pip install, no API key.

## Run it

```bash
python backend/server.py --demo
```

Then open <http://127.0.0.1:8000>. `--demo` seeds a demo account and loads the six
sample interviews in `samples/`; drop the flag on later runs.

```
demo@qrip.local / demo-password
```

Options: `--port 8000`, `--host 127.0.0.1`. The first account created becomes the
workspace **owner** and can see every project and the usage ledger.

## The idea

Classic CAQDAS software stores what you decide and decides nothing itself. Every
quotation, code and cross-case comparison is made by hand, which is why the first
real finding is weeks away and the second coder never quite happens.

QRIP does the mechanical pass immediately and then gets out of the way. The
machine's output is not a report — it is *the same objects you would have made by
hand*: real quotations with document offsets, real codebook entries, real themes.
You rename, merge, split, re-code and delete them, and your changes feed the next
analysis.

## The workbench (manual analysis)

| | |
|---|---|
| **Reader** | The document with every quotation highlighted in its code's colour. Select any passage to code it — pick an existing code, type a new one, or take the participant's own words in vivo. Click a highlight to open it, add codes, comment, or delete it. |
| **Code manager** | Groundedness, density, cases, colours, definitions, groups, merge, split, delete. Machine and hand codes in one list, marked but not separated. Duplicate-looking codes are suggested for merging. |
| **Quotation manager** | Every quotation with its codes, its provenance, and the machine's reading — emotion, intent, valence, confidence and alternative interpretations. |
| **Memos** | Analytic, method, reflexive, theoretical or to-do memos, attachable to any code, theme, document or quotation. |
| **Networks** | Drag objects onto a canvas and draw typed relations — *is cause of*, *contradicts*, *is part of*, *supports*… Layouts are saved. |
| **Queries** | Boolean retrieval (all / any / none / exactly, within a quotation or a document), code co-occurrence with c-coefficients, the code–document table, word frequency and one-click auto-coding of any search term. |
| **Agreement** | Your coding against the machine's *on the same quotations*: percent agreement, Cohen's kappa and Krippendorff's alpha, with the disagreements listed. |
| **Audit trail** | Every upload, control change, rename, merge, split, link and analysis run. |

Hand coding survives every re-run of the analysis, and a re-run reuses the
quotations you have touched rather than duplicating them — so a passage stays one
object with both coders attached to it.

## The automatic pass

**Coding.** Transcripts are split into speaker turns (interviewer prompts kept as
context, not coded) and then into meaning units at clause, sentence or utterance
granularity. Every unit becomes a quotation with exact document offsets plus a
code carrying a label, a literal restatement, emotion and intent, valence,
confidence, and one to three *alternative interpretations*.

**Themes.** Codes are placed in a concept space derived from corpus
co-occurrence, then clustered. Each theme carries confidence, coverage,
participant count, an explicit alternative reading, and any counter-cases running
against it. Codes that cohere with nothing are left unassigned rather than padded
into a theme.

**Checks.** Contradictions are detected where similar material is spoken about in
opposing terms, between cases and within one account. Every theme is then
re-derived under a different clustering configuration; themes that do not survive
are flagged unstable.

**Six readings, one corpus.**

| Methodology | What you get |
|---|---|
| Thematic | Braun & Clarke's six phases, sub-patterns, defining quotations, boundary notes, keyness |
| Grounded theory | Open → axial (Strauss & Corbin paradigm model) → selective coding, core category, saturation curve, memos |
| IPA | Per-case experiential statements (descriptive / linguistic / conceptual), personal themes, then group themes with divergence kept visible |
| Framework | Ritchie & Spencer's five stages ending in the framework matrix, with column-wise mapping and gaps |
| Narrative | Labov structure per case, valence arc, turning points, plot shape, agency positioning |
| Content | Coding scheme, category × case counts, manifest frequency, latent layer, KWIC concordance, reliability diagnostics |

**Controls.** Six analytic decisions — similarity threshold, confidence
threshold, minimum supporting quotations, participant frequency threshold, coding
granularity, contradiction sensitivity — are on screen rather than buried in
defaults, and every change is written to the audit trail.

**Exports.** `.xlsx` workbook (project, themes, codebook with groundedness,
quotations, memos, relations, contradictions, agreement, framework matrix,
content counts, audit trail), plus `.docx` and `.pdf` reports. All written with
the standard library.

## Review intelligence (`/reviews`)

The same coding engine pointed at customer reviews, producing an executive
business-intelligence report instead of a research write-up.

**Getting reviews in — three ways, no key needed for two of them:**

| Mode | What it does |
|---|---|
| Paste | JSON, CSV, or plain lines. `5 \| Great staff, seen on time (2 weeks ago)` is understood, as is any CSV with `rating` / `review` / `date` columns. |
| One at a time | A form for rating, reviewer, age and text — for a handful you have in front of you. |
| Google Maps URL | Parsed for `place_id` / CID / feature id, then fetched through a configured provider. |
| Demo | 15 reviews for a dental practice plus 10 for a competitor, to see the whole report immediately. |

**On scraping.** Direct scraping of maps.google.com is deliberately not
implemented: it needs a headless browser, breaks constantly against anti-bot
measures, and is against Google's terms. URLs are served by whichever provider
is configured:

```bash
set GOOGLE_MAPS_API_KEY=...   # official Places API — legitimate, but max 5 reviews
set SERPAPI_KEY=...           # full review history, paginated
set OUTSCRAPER_KEY=...        # full review history
```

With none of these set, the URL tab says so plainly and points you at pasting.

**What comes out.** An interactive report in the browser and two downloads:

1. **Executive dashboard** — net sentiment score, reviews analysed, average
   rating, negative ratio, and a sentiment valence donut.
2. **Temporal trend** — positive/neutral/negative across 0-3, 3-6, 6-12 and 12+
   months, with a reading of whether things are getting worse or better.
3. **Operational bottleneck audit** — friction ranked by severity (how negative
   the language is, how many separate reviewers raise it, how much explicit
   failure vocabulary appears), each with supporting quotes; plus a
   contradictions matrix, including five-star reviews whose text describes a
   failure.
4. **Framework matrix** — the customer journey: expectations, experience,
   barriers, enablers, impact, suggestions for change.
5. **Competitor cross-comparison** — a radar across Staff & Hospitality, Pricing
   & Value, Facility Quality & Maintenance, Process & Wait Times and Overall
   Satisfaction, plus *adoption parameters*: what their customers praise that
   yours do not, with their words as the evidence.

Exports: a five-plus-section **PDF** with real vector charts (donut, grouped
bars, radar — drawn by `backend/pdfkit.py`, no chart library), and a **12-sheet
.xlsx** whose first five sheets are exactly Codebook, Themes, Contradictions,
Content Counts and Framework Matrix.

**Endpoints:**

```
POST   /api/analyze                  { mode, business_name, business_url, business_reviews, ... }
GET    /api/jobs                     list your reports
GET    /api/report/{job_id}          full report JSON
GET    /api/report/{job_id}/status   progress while it runs
GET    /api/report/{job_id}/pdf      executive PDF
GET    /api/report/{job_id}/excel    multi-sheet workbook
GET    /api/review-providers         which URL providers are configured
```

Sentiment at review level blends the text reading (65%) with the star rating
(35%). That is deliberate: it is what lets a five-star review full of complaint
register as negative and surface in the contradictions matrix instead of
disappearing into an average.

## Using Claude for the interpretive layer (optional)

The default engine is deterministic and offline. To have Claude re-read every
coded segment instead:

```bash
pip install anthropic
set ANTHROPIC_API_KEY=sk-ant-...
python backend/server.py
```

Codes are then read by `claude-opus-5`, and real token counts and costs appear in
the usage ledger. Any failure leaves the local coding in place, so an analysis
never half-completes. `QRIP_LLM=off` forces the local engine; `QRIP_LLM_MAX_UNITS`
caps how many segments are sent.

## Layout

```
backend/
  server.py            HTTP server: /api/* plus the static frontend
  api.py               route handlers (78 routes)
  caqdas.py            quotations, codebook, groups, memos, links, queries, agreement
  db.py                SQLite schema, migrations and helpers
  auth.py              pbkdf2 passwords, HMAC bearer tokens
  exports.py           xlsx / docx / pdf writers (stdlib only)
  pdfkit.py            vector PDF: flowed text, tables, donut/bar/radar charts
  reviews/
    sources.py         Maps URL parsing, providers, manual/CSV/JSON parsing, demo data
    lexicon.py         review vocabulary: categories, radar dimensions, journey stages
    analysis.py        coding -> KPIs, trend, bottlenecks, content counts, framework
    compare.py         radar scoring and adoption parameters
    report_pdf.py      the executive PDF
    workbook.py        the multi-sheet workbook
    jobs.py            background job runner
  analysis/
    textproc.py        segmentation with offsets, stemming, tf-idf, concept space
    lexicons.py        emotion / intent / narrative / paradigm lexicons
    coding.py          meaning units -> codes
    clustering.py      codes -> themes, naming, merge suggestions
    contradictions.py  contradiction detection, second-pass comparison
    pipeline.py        orchestration
    llm.py             optional Claude adapter
    methodologies/     the six readings
frontend/              zero-build SPA (vanilla ES modules + hand-written CSS)
  js/charts.js         animated SVG infographics
  js/views/landing.js  the public page
  js/views/workbench.js  the coding surface
  js/views/reviews.js  the review intelligence tool
samples/               six sample interview transcripts
data/                  SQLite database and uploads (created on first run)
```

## A note on what the engine is

The offline engine is lexicon- and statistics-driven, not a language model. It is
deterministic and auditable, and it will read some segments differently from how
you would. Auto-generated code and theme names in particular often want renaming
— which is why rename, merge and split are first-class operations, each recorded
in the audit trail. Treat the first pass as a coding draft to argue with, not a
finding to accept.
