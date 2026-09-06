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

Customer reviews in, executive report out, in three explicit stages.

### The three functions

**Function 1 — thematic analysis** (`reviews/thematic.py`). Every review is read
and coded: a short analytic label, the verbatim quote, what it literally says,
the emotion behind it, the reviewer's intent, a valence from -1 to +1, a
confidence score, and whether it runs against the tone of its own review. Output
is the codebook workbook: **Themes, Codes, Quotations, Confidence Scores, Audit
Log**.

**Function 2 — theme reasoning** (`reviews/reasoning.py`). Claude Opus 5 at
**medium effort** decides the theme set once across the whole codebook, then
assigns every code to the theme it belongs to, in batches. This is the pass that
needs judgement: *"nobody returned my call"*, *"three unanswered emails"* and
*"the phone just rings"* share no words and are one finding. Coverage,
participant counts and confidence are computed in code, never asked of the model.

**Function 3 — report generation** (`reviews/report_pdf.py`). The same charts as
before, with sharper content from function 2, plus a thematic-framework section
and a sentiment-over-time line chart.

> **Function 1 and 2 both need `ANTHROPIC_API_KEY`.** Without it they fall back to
> a lexicon that matches words rather than meaning — which is what produced
> themes like *"Anger and comfortable"*. The UI says plainly which engine ran.

### Getting reviews in

| Mode | What it does |
|---|---|
| Paste | The block format: `*(Review 001)*` / `*Anitha Reddy (2 weeks ago)*` / text. Plain lines, CSV and JSON also work. |
| Outscraper file | Upload an Outscraper `.xlsx` or `.csv` export. Reads `author_title`, `review_text`, `review_rating`, `review_datetime_utc` and `owner_answer`. |
| Google Maps URL | Needs `OUTSCRAPER_KEY`, `SERPAPI_KEY` or `GOOGLE_MAPS_API_KEY`. |
| One at a time | A form, for a handful you have in front of you. |
| Demo | The bundled sample dataset. |

**Reviewer names are shown everywhere** — in the codebook, the themes, the
quotes, the report and the workbook. Internal ids exist only to join rows.

### Competitors

Add **as many competitors as you like**. Each is analysed through the same three
functions, then compared: a ranking by net sentiment, a dimension matrix showing
who leads each dimension, and adoption parameters drawn from *whichever rival
actually leads that dimension* rather than from an average of them.

### Outputs

An interactive report in the browser and three downloads: the executive **PDF**
(vector charts, no chart library), the full **.xlsx** analysis, and the
**codebook** workbook from function 1.

```
POST   /api/analyze                  { mode, business_name, business_reviews, competitors: [...] }
POST   /api/reviews/parse-upload     multipart Outscraper export -> parsed reviews
GET    /api/reviews/engine           which reasoning engine and providers are configured
GET    /api/report/{job_id}          full report JSON
GET    /api/report/{job_id}/status   progress while it runs
GET    /api/report/{job_id}/pdf      executive PDF
GET    /api/report/{job_id}/excel    multi-sheet workbook
GET    /api/report/{job_id}/codebook function-1 codebook workbook
```

Review-level sentiment blends the coded text (65%) with the star rating (35%),
which is what lets a five-star review full of complaint register as negative and
surface in the contradictions matrix.

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

## Tests

120 end-to-end checks against a running server — no test framework, no
dependencies.

```bash
python backend/server.py --demo    # one terminal
python tests/run_all.py            # another
```

`api_test.py` (37) covers auth, projects, documents, analysis and exports;
`caqdas_test.py` (29) the manual workbench — quotations, codebook, memos,
networks, queries, agreement; `reviews_test.py` (54) the three review functions,
all five ingestion modes, multi-competitor comparison and the three downloads.
Point `QRIP_TEST_BASE` at another host to run them against a deployment.

## Layout

```
backend/
  server.py            HTTP server: /api/* plus the static frontend
  claude.py            shared Claude client: structured output, fallbacks
  xlsxreader.py        stdlib .xlsx reader (Outscraper imports)
  api.py               route handlers (78 routes)
  caqdas.py            quotations, codebook, groups, memos, links, queries, agreement
  db.py                SQLite schema, migrations and helpers
  auth.py              pbkdf2 passwords, HMAC bearer tokens
  exports.py           xlsx / docx / pdf writers (stdlib only)
  pdfkit.py            vector PDF: flowed text, tables, donut/bar/radar charts
  reviews/
    thematic.py        function 1: Claude codes every review
    reasoning.py       function 2: Claude Opus 5 sorts codes into themes
    codebook.py        the function-1 codebook workbook
    scoring.py         sentiment cuts, text/star blend
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
  js/views/reviewinput.js  the five ways reviews get in
tests/                 120 end-to-end checks
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
