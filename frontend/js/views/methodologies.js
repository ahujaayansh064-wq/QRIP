// Renderers for the six methodology readings.
// Every renderer builds arrays through small helpers: shallow nesting keeps the
// markup readable and each piece independently testable.

import { badge, h, meter, num, pct, titleCase, valenceColor } from "../ui.js";

export function renderMethodology(key, payload) {
  const renderer = RENDERERS[key];
  const body = renderer ? renderer(payload) : h("pre", { text: JSON.stringify(payload, null, 2) });
  const head = h("div", { class: "card p-5" },
    h("h2", { class: "font-display text-2xl mb-1", text: payload.name || titleCase(key) }),
    h("p", { class: "text-sm text-inkfaint", text: payload.framework || "" }),
    h("p", { class: "text-xs text-inkfaint mt-2 mono", text: "engine " + (payload.engine || "—") }));
  return h("div", { class: "space-y-8" }, head, body);
}

// --- shared pieces --------------------------------------------------------

const OPEN_Q = "“";
const CLOSE_Q = "”";

function card(title, ...children) {
  const head = title ? h("h3", { class: "font-display text-lg mb-3", text: title }) : null;
  return h("div", { class: "card p-5" }, head, ...children);
}

function quote(text, attribution, note) {
  const parts = [h("p", { class: "quote", text: OPEN_Q + text + CLOSE_Q })];
  if (attribution) parts.push(h("p", { class: "text-xs text-inkfaint mt-1", text: attribution }));
  if (note) parts.push(h("p", { class: "text-xs text-ledger mt-1", text: note }));
  return h("div", { class: "mb-3" }, ...parts);
}

function row(label, value) {
  return h("tr", null,
    h("td", { class: "text-inkfaint", style: "width:14rem", text: label }),
    h("td", { text: String(value) }));
}

function keyValues(pairs) {
  return h("table", null, h("tbody", null, ...pairs.map(([label, value]) => row(label, value))));
}

function label(text) {
  return h("p", { class: "text-xs uppercase tracking-wide text-inkfaint mb-1", text });
}

function bar(text, value, count) {
  const head = h("div", { class: "flex justify-between text-sm mb-1" },
    h("span", { text }),
    h("span", { class: "text-inkfaint tabular", text: String(count) }));
  return h("div", null, head, meter(value));
}

function table(headings, bodyRows, className) {
  const head = h("tr", null, ...headings.map((cell) => (
    typeof cell === "string" ? h("th", { text: cell }) : cell)));
  return h("div", { class: "overflow-x-auto" },
    h("table", { class: className || "" },
      h("thead", null, head),
      h("tbody", null, ...bodyRows)));
}

function numberedSteps(items, indexKey, nameKey, textKey) {
  const steps = items.map((item) => h("div", { class: "flex gap-4" },
    h("span", { class: "font-display text-2xl text-hairline shrink-0",
                text: String(item[indexKey]) }),
    h("div", null,
      h("p", { class: "font-medium text-sm", text: item[nameKey] }),
      h("p", { class: "text-sm text-inkfaint", text: item[textKey] }))));
  return h("div", { class: "space-y-3" }, ...steps);
}

// --- thematic -------------------------------------------------------------

function thematicTheme(theme) {
  const parts = [];
  parts.push(h("div", { class: "flex items-start justify-between gap-4 mb-2" },
    h("h3", { class: "font-display text-xl", text: theme.name }),
    badge(theme.status)));
  parts.push(h("div", { class: "flex gap-4 text-xs text-inkfaint mb-3 tabular" },
    h("span", { text: theme.participant_count + " participants" }),
    h("span", { text: theme.quote_count + " quotations" }),
    h("span", { text: "coverage " + pct(theme.coverage, 1) }),
    h("span", { text: "confidence " + theme.confidence.toFixed(2) })));
  if (theme.defining_quote) {
    parts.push(quote(theme.defining_quote.text,
      theme.defining_quote.participant + " · defining quotation"));
  }
  if (theme.subthemes && theme.subthemes.length) {
    const subs = theme.subthemes.map((sub) => h("div", { class: "border-l-2 border-hairline pl-3" },
      h("p", { class: "text-sm font-medium", text: sub.name }),
      h("p", { class: "text-xs text-inkfaint",
               text: sub.quote_count + " quotations · " + sub.participants.join(", ") }),
      h("p", { class: "text-sm text-inkfaint", text: sub.example })));
    parts.push(h("div", { class: "mb-3" }, label("Sub-patterns"),
                 h("div", { class: "space-y-2" }, ...subs)));
  }
  if (theme.counter_cases && theme.counter_cases.length) {
    const cases = theme.counter_cases.map((c) =>
      h("p", { class: "text-sm", text: c.participant + ": " + c.text }));
    parts.push(h("div", { class: "bg-warnlight p-3 rounded-card mb-3" },
      h("p", { class: "text-xs uppercase tracking-wide text-warn mb-1", text: "Counter-cases" }),
      ...cases));
  }
  parts.push(h("p", { class: "text-sm text-inkfaint", text: theme.boundary_note }));
  return card(null, ...parts);
}

function thematic(payload) {
  const keyness = payload.keyness.map((item) => h("tr", null,
    h("td", { text: item.term }),
    h("td", { class: "text-right tabular", text: num(item.count) }),
    h("td", { class: "text-right tabular", text: item.keyness })));
  const prompts = payload.reflexive_prompts.map((prompt) =>
    h("li", { class: "text-sm text-inkfaint", text: "· " + prompt }));
  return h("div", { class: "space-y-6" },
    card("Six phases", numberedSteps(payload.phases, "phase", "name", "output")),
    ...payload.themes.map(thematicTheme),
    card("Keyness", table(["Term",
      h("th", { class: "text-right", text: "Segments" }),
      h("th", { class: "text-right", text: "Keyness" })], keyness)),
    card("Reflexive prompts", h("ul", { class: "space-y-2" }, ...prompts)));
}

// --- grounded theory ------------------------------------------------------

function saturationChart(saturation) {
  const points = saturation.points || [];
  if (points.length < 2) {
    return h("p", { class: "text-sm text-inkfaint", text: "Not enough interviews to plot." });
  }
  const width = 420;
  const height = 130;
  const maxCumulative = Math.max(...points.map((p) => p.cumulative), 1);
  const path = points.map((point, i) => {
    const x = 10 + (i / (points.length - 1)) * (width - 20);
    const y = height - 20 - (point.cumulative / maxCumulative) * (height - 40);
    return (i ? "L" : "M") + x.toFixed(1) + " " + y.toFixed(1);
  }).join(" ");
  const bars = points.map((point, i) => {
    const x = 10 + (i / (points.length - 1)) * (width - 20);
    const barHeight = point.new_rate * (height - 40);
    return '<rect x="' + (x - 6) + '" y="' + (height - 20 - barHeight)
      + '" width="12" height="' + barHeight + '" fill="#2B4570" fill-opacity="0.16"/>'
      + '<text x="' + x + '" y="' + (height - 6) + '" font-size="10" text-anchor="middle"'
      + ' fill="#6B6D76">' + point.transcript + "</text>";
  }).join("");
  const svg = '<svg viewBox="0 0 ' + width + " " + height + '" width="100%"'
    + ' xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Saturation curve">'
    + bars + '<path d="' + path + '" fill="none" stroke="#2F6F4E" stroke-width="2"/></svg>';
  return h("div", { html: svg });
}

function paradigmSlot(data) {
  const body = data.evidence.length
    ? data.evidence.slice(0, 2).map((item) => h("p", { class: "text-sm text-inkfaint mb-1",
        text: OPEN_Q + item.quote + CLOSE_Q + " — " + item.participant }))
    : [h("p", { class: "text-sm text-hairline", text: "no evidence indexed" })];
  return h("div", { class: "border-l-2 border-hairline pl-3" },
    h("p", { class: "text-xs uppercase tracking-wide text-ledger mb-1", text: data.label }),
    ...body);
}

function axialCategory(category) {
  const slots = Object.values(category.paradigm).map(paradigmSlot);
  return card(null,
    h("div", { class: "flex items-start justify-between gap-4 mb-1" },
      h("h3", { class: "font-display text-xl", text: category.name }),
      h("span", { class: "text-xs text-inkfaint tabular",
                  text: "centrality " + category.centrality
                        + " · density " + category.density + "/6" })),
    h("p", { class: "text-xs text-inkfaint mb-3",
             text: category.code_count + " codes · " + category.participants.join(", ") }),
    h("div", { class: "grid grid-2 gap-4" }, ...slots),
    h("p", { class: "text-sm text-inkfaint mt-3", text: category.dimensions.note }));
}

function groundedTheory(payload) {
  const open = payload.open_coding;
  const frequent = open.most_frequent.slice(0, 8).map((item) =>
    h("div", { class: "flex justify-between text-sm" },
      h("span", { text: item.label }),
      h("span", { class: "text-inkfaint tabular", text: String(item.count) })));
  const memos = payload.memos.map((memo) => h("div", null,
    h("p", { class: "font-medium text-sm mb-1", text: memo.title }),
    h("p", { class: "text-sm text-inkfaint leading-relaxed", text: memo.text })));
  const comparisons = payload.constant_comparison.map((item) => h("div", null,
    h("p", { class: "text-sm font-medium", text: item.pair.join("  ·  ") }),
    h("p", { class: "text-sm text-inkfaint", text: item.note })));

  const openCard = card("Open coding",
    keyValues([["Codes generated", num(open.code_count)],
               ["Distinct labels", num(open.distinct_labels)]]),
    h("p", { class: "text-sm text-inkfaint mt-3", text: open.note }),
    h("p", { class: "text-xs uppercase tracking-wide text-inkfaint mt-4 mb-2",
             text: "Most frequent codes" }),
    h("div", { class: "space-y-1" }, ...frequent));

  const saturationCard = card("Theoretical saturation",
    saturationChart(payload.saturation),
    h("p", { class: "text-sm mt-3", text: payload.saturation.verdict }));

  const selectiveCard = card("Selective coding",
    label("Core category"),
    h("p", { class: "font-display text-2xl mb-3",
             text: payload.selective_coding.core_category || "—" }),
    h("p", { class: "text-sm leading-relaxed mb-3", text: payload.selective_coding.storyline }),
    h("p", { class: "text-sm text-inkfaint",
             text: payload.selective_coding.integration_note || "" }));

  return h("div", { class: "space-y-6" },
    h("div", { class: "grid grid-2 gap-4" }, openCard, saturationCard),
    selectiveCard,
    ...payload.axial_categories.slice(0, 6).map(axialCategory),
    card("Memos", h("div", { class: "space-y-4" }, ...memos)),
    comparisons.length
      ? card("Constant comparison", h("div", { class: "space-y-3" }, ...comparisons))
      : null);
}

// --- IPA ------------------------------------------------------------------

function ipaGroupTheme(get) {
  const parts = [];
  parts.push(h("div", { class: "flex items-center justify-between gap-3 mb-1" },
    h("p", { class: "font-display text-lg", text: get.name }),
    h("span", { class: "text-xs text-inkfaint tabular",
                text: "convergence " + pct(get.convergence) })));
  parts.push(h("p", { class: "text-xs text-inkfaint mb-2",
                      text: "Present in " + get.present_in.join(", ") }));
  for (const exemplar of get.exemplars.slice(0, 2)) {
    parts.push(quote(exemplar.quote, exemplar.participant, exemplar.reading));
  }
  for (const note of get.divergence) {
    parts.push(h("p", { class: "text-sm text-warn", text: note }));
  }
  return h("div", { class: "border-l-2 border-hairline pl-4" }, ...parts);
}

function ipaStatement(statement) {
  const column = (heading, text) => h("div", null,
    h("p", { class: "text-xs uppercase tracking-wide text-inkfaint", text: heading }),
    h("p", { class: "text-sm", text }));
  return h("div", null,
    h("p", { class: "quote", text: OPEN_Q + statement.quote + CLOSE_Q }),
    h("div", { class: "grid grid-3 gap-3 mt-2" },
      column("Descriptive", statement.descriptive),
      column("Linguistic", statement.linguistic),
      column("Conceptual", statement.conceptual)));
}

function ipaCase(entry) {
  const pets = entry.personal_experiential_themes.map((pet) =>
    h("div", { class: "border-l-2 border-hairline pl-3" },
      h("p", { class: "text-sm font-medium", text: pet.name }),
      h("p", { class: "text-xs text-inkfaint", text: pet.statement_count + " statements" })));
  const statements = entry.experiential_statements.slice(0, 4).map(ipaStatement);
  const petBlock = pets.length
    ? h("div", { class: "mb-4" }, label("Personal experiential themes"),
        h("div", { class: "space-y-2" }, ...pets))
    : null;
  return card(entry.participant,
    h("p", { class: "text-sm leading-relaxed mb-4", text: entry.idiographic_summary }),
    petBlock,
    label("Experiential statements"),
    h("div", { class: "space-y-4" }, ...statements));
}

function ipaDimensions(totals) {
  const values = Object.values(totals || {});
  const max = values.length ? Math.max(...values) : 1;
  const rows = Object.entries(totals || {}).sort((a, b) => b[1] - a[1])
    .map(([dimension, count]) => bar(titleCase(dimension), count / max, count));
  return h("div", { class: "space-y-2" }, ...rows);
}

function ipa(payload) {
  const gets = payload.group_experiential_themes.slice(0, 8).map(ipaGroupTheme);
  const notes = payload.hermeneutic_notes.map((note) =>
    h("li", { class: "text-sm text-inkfaint leading-relaxed", text: note }));
  return h("div", { class: "space-y-6" },
    card("Group experiential themes", h("div", { class: "space-y-5" }, ...gets)),
    ...payload.cases.map(ipaCase),
    card("Experiential dimensions across the corpus", ipaDimensions(payload.dimension_totals)),
    card("Hermeneutic notes", h("ul", { class: "space-y-3" }, ...notes)));
}

// --- framework ------------------------------------------------------------

function frameworkCell(cell) {
  if (!cell.count) return h("td", null, h("span", { class: "text-hairline", text: "—" }));
  return h("td", null,
    h("p", { class: "text-sm", text: cell.summary }),
    h("p", { class: "text-xs text-inkfaint mt-1",
             text: cell.count + " segments · valence " + cell.valence }));
}

function frameworkMatrix(matrix) {
  const headings = [h("th", { text: "Participant" })];
  matrix.columns.forEach((column, i) => {
    headings.push(h("th", null,
      h("span", { text: column }),
      h("span", { class: "block text-inkfaint",
                  style: "text-transform:none;letter-spacing:0",
                  text: matrix.sources[i] })));
  });
  const rows = matrix.rows.map((entry) => h("tr", null,
    h("td", { class: "font-medium", text: entry.participant }),
    ...entry.cells.map(frameworkCell)));
  return table(headings, rows, "matrix");
}

function framework(payload) {
  const mapping = payload.mapping.map((item) => h("div", null,
    h("div", { class: "flex items-center justify-between gap-3" },
      h("p", { class: "text-sm font-medium", text: item.category }),
      h("span", { class: "text-xs text-inkfaint tabular",
                  text: "coverage " + pct(item.coverage) })),
    h("p", { class: "text-sm text-inkfaint", text: item.pattern })));
  const gaps = payload.gaps.map((gap) => h("p", { class: "text-sm text-inkfaint",
    text: gap.category + " — " + gap.note }));
  return h("div", { class: "space-y-6" },
    card("Five stages", numberedSteps(payload.stages, "stage", "name", "output")),
    card("Framework matrix",
      h("p", { class: "text-sm text-inkfaint mb-3",
               text: "One row per case, one column per category. Read down a column to "
                     + "compare cases, along a row to keep a case whole." }),
      frameworkMatrix(payload.matrix)),
    card("Mapping and interpretation", h("div", { class: "space-y-3" }, ...mapping)),
    gaps.length ? card("Gaps in the matrix", h("div", { class: "space-y-2" }, ...gaps)) : null);
}

// --- narrative ------------------------------------------------------------

function valenceLine(series) {
  if (!series || series.length < 2) return h("div");
  const width = 820;
  const height = 90;
  const path = series.map((point, i) => {
    const x = (i / (series.length - 1)) * (width - 10) + 5;
    const y = height / 2 - point.valence * (height / 2 - 8);
    return (i ? "L" : "M") + x.toFixed(1) + " " + y.toFixed(1);
  }).join(" ");
  const svg = '<svg viewBox="0 0 ' + width + " " + height + '" width="100%"'
    + ' style="min-width:420px" xmlns="http://www.w3.org/2000/svg" role="img"'
    + ' aria-label="Valence across the telling">'
    + '<line x1="0" y1="' + (height / 2) + '" x2="' + width + '" y2="' + (height / 2)
    + '" stroke="#E4E1D8" stroke-width="1"/>'
    + '<path d="' + path + '" fill="none" stroke="#2B4570" stroke-width="1.6"/></svg>';
  return h("div", { class: "overflow-x-auto", html: svg });
}

function narrativeArc(entry) {
  const blocks = entry.arc.map((element) => {
    const body = element.segments.length
      ? h("p", { class: "text-sm text-inkfaint",
                 text: OPEN_Q + element.segments[0].quote + CLOSE_Q })
      : h("p", { class: "text-sm text-hairline", text: "not present" });
    return h("div", { class: "mb-2" },
      h("p", { class: "text-sm font-medium",
               text: titleCase(element.element) + " (" + element.count + ")" }),
      body);
  });
  return h("div", null, label("Structure"), ...blocks);
}

function narrativeTurningPoints(entry) {
  const points = entry.turning_points.map((point) => h("div", { class: "mb-3" },
    h("p", { class: "text-xs " + (point.direction === "upturn" ? "text-confidence" : "text-warn"),
             text: point.direction + " · delta " + point.delta }),
    h("p", { class: "text-sm text-inkfaint", text: OPEN_Q + point.after + CLOSE_Q })));
  const body = points.length ? points
    : [h("p", { class: "text-sm text-hairline", text: "no sharp reversals" })];
  return h("div", null,
    label("Turning points"),
    ...body,
    h("p", { class: "text-xs uppercase tracking-wide text-inkfaint mt-4 mb-1", text: "Agency" }),
    h("p", { class: "text-sm text-inkfaint", text: entry.agency.note }),
    meter(entry.agency.ratio));
}

function narrativeCase(entry) {
  return card(null,
    h("div", { class: "flex items-start justify-between gap-4 mb-2" },
      h("h3", { class: "font-display text-xl", text: entry.participant }),
      h("span", { class: "badge badge-review", text: entry.plot_type.type })),
    h("p", { class: "text-sm leading-relaxed mb-3", text: entry.summary }),
    valenceLine(entry.valence_series),
    h("div", { class: "grid grid-2 gap-4 mt-4" },
      narrativeArc(entry),
      narrativeTurningPoints(entry)));
}

function narrative(payload) {
  const shapes = Object.entries(payload.cross_narrative.plot_types)
    .map(([type, n]) => type + " x" + n).join(", ");
  return h("div", { class: "space-y-6" },
    card("Across the narratives",
      h("p", { class: "text-sm leading-relaxed mb-3", text: payload.cross_narrative.note }),
      keyValues([["Plot shapes", shapes],
                 ["Mean agency ratio", payload.cross_narrative.mean_agency_ratio]])),
    ...payload.narratives.map(narrativeCase));
}

// --- content --------------------------------------------------------------

function statTile(text, value) {
  return h("div", { class: "stat" },
    h("div", { class: "stat-value", text: String(value) }),
    h("div", { class: "stat-label", text }));
}

function contentMatrix(matrix) {
  const headings = [h("th", { text: "Participant" })];
  for (const column of matrix.columns) {
    headings.push(h("th", { class: "text-right", text: column }));
  }
  headings.push(h("th", { class: "text-right", text: "Total" }));

  const rows = matrix.rows.map((entry) => h("tr", null,
    h("td", { class: "font-medium", text: entry.participant }),
    ...entry.counts.map((count) => h("td", { class: "text-right tabular",
                                             text: count || "·" })),
    h("td", { class: "text-right tabular font-medium", text: String(entry.total) })));

  const grand = matrix.totals.reduce((a, b) => a + b, 0);
  rows.push(h("tr", null,
    h("td", { class: "text-inkfaint", text: "All" }),
    ...matrix.totals.map((total) => h("td", { class: "text-right tabular", text: String(total) })),
    h("td", { class: "text-right tabular", text: String(grand) })));
  return table(headings, rows);
}

function kwicEntry(entry) {
  const lines = entry.lines.map((line) => h("div", { class: "flex gap-2" },
    h("span", { class: "text-inkfaint shrink-0", style: "width:3rem", text: line.participant }),
    h("span", { class: "text-right text-inkfaint", style: "width:45%", text: line.left }),
    h("span", { class: "text-ledger", text: " " + line.keyword + " " }),
    h("span", { class: "text-inkfaint", text: line.right })));
  return h("div", null, label(entry.term), h("div", { class: "mono" }, ...lines));
}

function content(payload) {
  const manifest = payload.manifest;
  const maxCount = Math.max(...payload.matrix.totals, 1);
  const topCount = manifest.top_terms.length ? manifest.top_terms[0].count : 1;

  const scheme = payload.scheme.map((entry) => h("span", {
    class: "badge " + (entry.type === "emergent" ? "badge-candidate" : "badge-review"),
    text: entry.category }));

  const terms = manifest.top_terms.slice(0, 14).map((term) => bar(
    term.term, term.count / topCount, term.count + " · keyness " + term.keyness));

  const latent = payload.latent.map((entry) => h("div", null,
    h("div", { class: "flex items-center justify-between gap-3" },
      h("p", { class: "text-sm font-medium", text: entry.category }),
      h("span", { class: "text-xs tabular text-" + valenceColor(entry.mean_valence),
                  text: "valence " + entry.mean_valence })),
    meter(entry.count / maxCount),
    h("p", { class: "text-sm text-inkfaint mt-1", text: entry.interpretation })));

  const reliability = payload.reliability;
  return h("div", { class: "space-y-6" },
    h("div", { class: "grid grid-4 gap-3" },
      statTile("Words", num(manifest.total_words)),
      statTile("Content words", num(manifest.content_words)),
      statTile("Unique terms", num(manifest.unique_terms)),
      statTile("Type–token ratio", manifest.type_token_ratio)),
    card("Coding scheme", h("div", { class: "flex flex-wrap gap-2" }, ...scheme)),
    card("Category counts by participant", contentMatrix(payload.matrix)),
    card("Manifest frequency", h("div", { class: "space-y-1" }, ...terms)),
    card("Latent reading", h("div", { class: "space-y-3" }, ...latent)),
    payload.kwic.length
      ? card("Concordance (KWIC)",
             h("div", { class: "space-y-4" }, ...payload.kwic.slice(0, 6).map(kwicEntry)))
      : null,
    card("Coding reliability",
      keyValues([
        ["Coded units", num(reliability.coded_units)],
        ["Total meaning units", num(reliability.total_units)],
        ["Mean confidence", reliability.mean_confidence],
        ["Low-confidence units", num(reliability.low_confidence_units)],
        ["Multiply-interpretable units", num(reliability.ambiguous_units)],
      ]),
      h("p", { class: "text-sm text-inkfaint mt-3", text: reliability.note })));
}

const RENDERERS = {
  thematic,
  grounded_theory: groundedTheory,
  ipa,
  framework,
  narrative,
  content,
};
