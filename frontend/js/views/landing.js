// The public landing page: what QRIP is, and why it is not another manual
// CAQDAS tool. Motion here is explanatory — highlights land where coding lands.

import { barChart, codeNetwork, counter, groupedBars, heatmap, observeReveals,
  sparkline, svg } from "../charts.js";
import { h, link } from "../ui.js";

const METHODS = [
  ["thematic", "Thematic analysis", "Braun & Clarke's six phases, with sub-patterns, "
    + "defining quotations and boundary notes."],
  ["grounded_theory", "Grounded theory", "Open, axial and selective coding with the "
    + "paradigm model, memos and a saturation curve."],
  ["ipa", "Interpretative phenomenological analysis", "Idiographic first: experiential "
    + "statements per case, then group themes with divergence kept visible."],
  ["framework", "Framework analysis", "Ritchie & Spencer's five stages, ending in a "
    + "living framework matrix you can read down or across."],
  ["narrative", "Narrative analysis", "Labov structure, valence arc, turning points, "
    + "plot shape and how much agency each teller claims."],
  ["content", "Content analysis", "Category counts by case, manifest frequency, a latent "
    + "layer and KWIC concordances."],
];

const DEMO_LINES = [
  { text: "My GP referred me in the January. She said it would be six weeks.",
    mark: [34, 66], code: "Promised timescale", color: "#2B4570" },
  { text: "Nothing. Absolutely nothing. No letter, no phone call, no text.",
    mark: [0, 27], code: "Silence after referral", color: "#B5541B" },
  { text: "You ring the hospital and they say ring the GP. Nobody could tell me where my referral was.",
    mark: [48, 91], code: "Chasing as unpaid work", color: "#8A6D3B" },
  { text: "It made me feel invisible, like the letter had fallen down the back of a cabinet.",
    mark: [0, 25], code: "Being made invisible", color: "#7A2E4A" },
  { text: "A text message. Genuinely. It is not the wait that breaks you, it is not knowing.",
    mark: [27, 80], code: "Uncertainty over duration", color: "#2F6F4E" },
];

export function landingView() {
  const page = h("div", { class: "min-h-screen bg-paper" },
    nav(),
    hero(),
    marquee(),
    manualTax(),
    howItWorks(),
    workbenchSection(),
    methodsSection(),
    reviewsSection(),
    paritySection(),
    trustSection(),
    finalCta(),
    footer());
  setTimeout(() => {
    observeReveals(page);
    startNavShade(page);
  }, 0);
  return page;
}

// --- chrome ---------------------------------------------------------------

function nav() {
  const bar = h("header", { class: "header", dataset: { navbar: "1" } },
    h("div", { class: "max-w-7xl mx-auto px-6 h-16 flex items-center justify-between" },
      h("a", { href: "#top", class: "flex items-center gap-2" },
        h("span", { class: "dot dot-lg dot-pulse" }),
        h("span", { class: "font-display text-lg tracking-tight", text: "QRIP" })),
      h("nav", { class: "flex items-center gap-6 md-hide" },
        anchor("#how", "How it works"),
        anchor("#workbench", "Workbench"),
        anchor("#methods", "Methodologies"),
        anchor("#reviews", "Review intelligence"),
        anchor("#parity", "Compared"),
      ),
      h("div", { class: "flex items-center gap-2" },
        link("/login", { class: "btn btn-ghost btn-sm" }, "Sign in"),
        link("/register", { class: "btn btn-primary btn-sm" }, "Start free"))));
  return bar;
}

function anchor(href, label) {
  return h("a", { href, class: "text-sm text-inkfaint", text: label,
                  style: "transition:color .16s",
                  onMouseenter: (e) => { e.target.style.color = "var(--ink)"; },
                  onMouseleave: (e) => { e.target.style.color = ""; } });
}

function startNavShade(page) {
  const bar = page.querySelector("[data-navbar]");
  if (!bar) return;
  const onScroll = () => {
    if (!bar.isConnected) {
      window.removeEventListener("scroll", onScroll);
      return;
    }
    bar.style.boxShadow = window.scrollY > 12 ? "0 1px 0 rgba(28,29,33,.06)" : "none";
  };
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();
}

// --- hero -----------------------------------------------------------------

function hero() {
  const headline = h("h1", { class: "font-display text-6xl leading-tight tracking-tight mb-5" },
    "Read every transcript twice.",
    h("br"),
    h("span", { class: "text-inkfaint" }, "Once by machine. Once by you."));

  return h("section", { id: "top", class: "hero" },
    h("div", { class: "hero-grid" }),
    h("div", { class: "max-w-7xl mx-auto px-6 py-24 relative" },
      h("div", { class: "grid grid-2 gap-12 items-center" },
        h("div", { class: "reveal" },
          h("p", { class: "eyebrow mb-4", text: "Qualitative research intelligence platform" }),
          headline,
          h("p", { class: "text-lg text-inkfaint leading-relaxed mb-8", style: "max-width:34rem" },
            "QRIP codes your whole corpus in seconds — quotations, codes, themes, "
            + "contradictions — and then hands you every object to argue with. "
            + "All the manual control of a classic CAQDAS workbench, without the "
            + "forty hours before you see anything."),
          h("div", { class: "flex gap-3 flex-wrap mb-8" },
            link("/register", { class: "btn btn-primary btn-lg" }, "Start free"),
            link("/login", { class: "btn btn-lg" }, "Open the demo project")),
          h("div", { class: "flex gap-8 flex-wrap" },
            heroStat("6", "methodologies, one pass"),
            heroStat("0", "installs or dependencies"),
            heroStat("100%", "of coding editable by hand"))),
        h("div", { class: "reveal reveal-delay-2" }, codingDemo()))));
}

function heroStat(value, label) {
  return h("div", null,
    h("div", { class: "font-display text-2xl", text: value }),
    h("div", { class: "text-xs text-inkfaint", text: label }));
}

function codingDemo() {
  const lines = h("div", { class: "space-y-3" });
  const margin = h("div", { class: "space-y-3", style: "width:12rem" });
  const themeSlot = h("div", { class: "mt-4" });

  const panel = h("div", { class: "card shadow tilt overflow-hidden" },
    h("div", { class: "flex items-center justify-between px-4 py-3 border-b border-hairline" },
      h("div", { class: "flex items-center gap-2" },
        h("span", { class: "dot" }),
        h("span", { class: "text-sm", text: "P1 · referral-delays.txt" })),
      h("span", { class: "badge badge-auto", text: "auto-coding" })),
    h("div", { class: "flex gap-4 p-4" },
      h("div", { class: "flex-1", style: "min-width:0" }, lines),
      h("div", { class: "shrink-0 md-hide" }, margin)),
    h("div", { class: "px-4 pb-4" }, themeSlot));

  runDemo(lines, margin, themeSlot);
  return panel;
}

function runDemo(lines, margin, themeSlot) {
  let timers = [];
  const later = (fn, delay) => timers.push(setTimeout(fn, delay));

  function cycle() {
    if (!lines.isConnected) {
      timers.forEach(clearTimeout);
      return;
    }
    lines.replaceChildren();
    margin.replaceChildren();
    themeSlot.replaceChildren();

    DEMO_LINES.forEach((line, index) => {
      const before = line.text.slice(0, line.mark[0]);
      const marked = line.text.slice(line.mark[0], line.mark[1]);
      const after = line.text.slice(line.mark[1]);
      const em = h("em", { text: marked, style: "color:" + line.color + "1f;"
        + "animation-delay:" + (0.5 + index * 0.9) + "s" });
      const inner = h("span", null,
        h("span", { text: before }),
        h("span", { style: "position:relative" }, em,
          h("span", { style: "position:absolute;left:0;top:0;color:var(--ink)", text: marked })),
        h("span", { text: after }));
      lines.appendChild(h("span", { class: "demo-line font-display text-sm leading-relaxed" },
        inner));

      later(() => {
        if (!margin.isConnected) return;
        margin.appendChild(h("span", {
          class: "code-chip demo-chip", style: "background:" + line.color + "14;color:"
            + line.color },
          h("span", { class: "code-swatch", style: "background:" + line.color }),
          h("span", { text: line.code })));
      }, 900 + index * 900);
    });

    later(() => {
      if (!themeSlot.isConnected) return;
      themeSlot.appendChild(h("div", {
        class: "card p-3 demo-chip",
        style: "background:var(--ledgerlight);border-color:transparent" },
        h("div", { class: "flex items-center justify-between mb-1" },
          h("span", { class: "text-xs uppercase tracking-wide text-ledger",
                      text: "theme formed" }),
          h("span", { class: "badge badge-confirmed", text: "6 of 6 participants" })),
        h("p", { class: "font-display text-lg", text: "Waiting without information" }),
        h("p", { class: "text-xs text-inkfaint",
                 text: "16 quotations · confidence 0.67 · 3 counter-cases kept" })));
    }, 900 + DEMO_LINES.length * 900);

    later(cycle, 2600 + DEMO_LINES.length * 900);
  }
  cycle();
}

function marquee() {
  const items = METHODS.map(([, name]) => name)
    .concat(["Quotations", "Code manager", "Memos", "Networks", "Co-occurrence",
             "Framework matrix", "Inter-coder agreement", "Audit trail"]);
  const row = items.concat(items).map((label) =>
    h("span", { class: "text-sm text-inkfaint shrink-0", text: label }));
  return h("section", { class: "border-t border-b border-hairline py-3 overflow-hidden" },
    h("div", { class: "marquee" }, ...row));
}

// --- the manual tax -------------------------------------------------------

function manualTax() {
  const rows = [
    { label: "Import and familiarisation", manual: 4, qrip: 0.2 },
    { label: "Open coding, whole corpus", manual: 40, qrip: 0.1 },
    { label: "Building the codebook", manual: 12, qrip: 0.1 },
    { label: "Clustering into themes", manual: 10, qrip: 0.1 },
    { label: "Contradiction hunting", manual: 8, qrip: 0.1 },
    { label: "Second coder / reliability", manual: 20, qrip: 0.1 },
  ];
  const manualTotal = rows.reduce((sum, row) => sum + row.manual, 0);

  const bars = rows.map((row, i) => {
    const width = (row.manual / manualTotal) * 100;
    return h("div", { class: "mb-3 reveal", style: "transition-delay:" + (i * 0.06) + "s" },
      h("div", { class: "flex justify-between text-xs mb-1" },
        h("span", { text: row.label }),
        h("span", { class: "text-inkfaint tabular", text: row.manual + " h → " + "seconds" })),
      h("div", { style: "height:8px;background:#34353d;border-radius:9999px;overflow:hidden" },
        h("div", { style: "height:100%;background:#b5541b;width:" + width + "%;"
          + "transform-origin:left;animation:growx .9s var(--ease) both;"
          + "animation-delay:" + (i * 0.08) + "s" })));
  });

  return h("section", { class: "section-dark py-24" },
    h("div", { class: "max-w-7xl mx-auto px-6" },
      h("div", { class: "grid grid-2 gap-12 items-start" },
        h("div", { class: "reveal" },
          h("p", { class: "eyebrow mb-4", text: "The problem with manual CAQDAS" }),
          h("h2", { class: "font-display text-4xl leading-tight mb-5" },
            "Classic tools give you a filing cabinet and wish you luck."),
          h("p", { class: "text-inkfaint leading-relaxed mb-6" },
            "ATLAS.ti, NVivo and MAXQDA are excellent at storing what you decide. "
            + "They decide nothing themselves. Every quotation, every code, every "
            + "comparison across cases is yours to make by hand — which is why the "
            + "first real finding is usually weeks away, and why the second coder "
            + "never quite happens."),
          h("p", { class: "text-inkfaint leading-relaxed mb-8" },
            "QRIP does the mechanical pass in seconds and then gets out of the way. "
            + "Nothing it produces is locked: every quotation can be moved, every "
            + "code renamed or merged, every theme split or rejected — and your "
            + "changes feed the next analysis."),
          h("div", { class: "flex gap-8 flex-wrap" },
            h("div", null,
              h("div", { class: "font-display text-4xl" }, counter(94, { suffix: " h" })),
              h("div", { class: "text-xs text-inkfaint", text: "typical manual first pass" })),
            h("div", null,
              h("div", { class: "font-display text-4xl" }, counter(0.7, { decimals: 1, suffix: " s" })),
              h("div", { class: "text-xs text-inkfaint", text: "QRIP first pass, 6 interviews" })))),
        h("div", { class: "card p-6" },
          h("p", { class: "eyebrow mb-4", text: "Where the hours go" }),
          ...bars,
          h("p", { class: "text-xs text-inkfaint mt-4" },
            "Indicative hours for a six-interview study, based on published "
            + "estimates of manual coding effort. Your mileage varies; the shape does not.")))));
}

// --- how it works ---------------------------------------------------------

function howItWorks() {
  const steps = [
    ["Upload", "Drop in transcripts. Speaker turns are detected, interviewer prompts "
      + "kept as context, and the text is segmented into meaning units."],
    ["Machine first pass", "Every unit becomes a real quotation with document offsets, "
      + "an interpretive code, an emotion and intent reading, a confidence score and "
      + "explicit alternative readings."],
    ["You take over", "Select any text to code it yourself. Rename, merge, split, "
      + "recolour, group, memo, link. Your coding is not a separate track — it feeds "
      + "the next run."],
    ["Six readings", "The same coded corpus is read six ways at once, with "
      + "contradictions, counter-cases and a second-pass stability check attached."],
  ];

  const pipeline = svg("0 0 900 150", [
    '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6"',
    ' markerHeight="6" orient="auto"><path d="M0 0 L10 5 L0 10 z" fill="#2B4570"/></marker></defs>',
    stage(70, "Documents", "#4F5D66"),
    stage(290, "Quotations", "#8A6D3B"),
    stage(510, "Codes", "#2B4570"),
    stage(730, "Themes", "#2F6F4E"),
    flow(150, 250), flow(370, 470), flow(590, 690),
  ].join(""));

  return h("section", { id: "how", class: "py-24" },
    h("div", { class: "max-w-7xl mx-auto px-6" },
      h("div", { class: "text-center mb-16 reveal" },
        h("p", { class: "eyebrow mb-3", text: "How it works" }),
        h("h2", { class: "font-display text-4xl mb-4" }, "Four objects. One chain."),
        h("p", { class: "text-inkfaint", style: "max-width:40rem;margin:0 auto" },
          "Everything in QRIP is one of four things, and each one is editable. "
          + "That is what makes an automatic first pass safe.")),
      h("div", { class: "reveal mb-16" }, pipeline),
      h("div", { class: "grid grid-4 gap-6" },
        ...steps.map(([title, body], i) => h("div", {
          class: "reveal", style: "transition-delay:" + (i * 0.08) + "s" },
          h("div", { class: "font-display text-3xl text-hairline mb-2",
                     text: "0" + (i + 1) }),
          h("h3", { class: "font-display text-lg mb-2", text: title }),
          h("p", { class: "text-sm text-inkfaint leading-relaxed", text: body }))))));
}

function stage(x, label, color) {
  return '<g><rect x="' + x + '" y="40" width="100" height="54" rx="6" fill="' + color
    + '" fill-opacity="0.1" stroke="' + color + '" stroke-opacity="0.5"/>'
    + '<text x="' + (x + 50) + '" y="72" text-anchor="middle" font-size="13"'
    + ' font-family="Georgia, serif" fill="#1C1D21">' + label + "</text></g>";
}

function flow(from, to) {
  return '<line x1="' + from + '" y1="67" x2="' + to + '" y2="67" stroke="#2B4570"'
    + ' stroke-width="1.5" marker-end="url(#arrow)" stroke-dasharray="120"'
    + ' stroke-dashoffset="120"><animate attributeName="stroke-dashoffset" from="120"'
    + ' to="0" dur="0.9s" begin="0.3s" fill="freeze"/></line>';
}

// --- workbench ------------------------------------------------------------

function workbenchSection() {
  const features = [
    ["Select and code", "Highlight any span and code it — pick an existing code, type a "
      + "new one, or take the participant's own words as the code."],
    ["Code manager", "Groundedness, density, colours, definitions, groups, merge and "
      + "split. Everything the machine produced is in there with everything you add."],
    ["Memos and links", "Analytic memos attached to codes, quotations or documents, and "
      + "typed relations — is cause of, contradicts, is part of — between any two objects."],
    ["Networks", "Drag objects onto a canvas and draw the relations. Saved layouts, "
      + "not a screenshot."],
    ["Queries", "Boolean retrieval across codes, code co-occurrence, the code–document "
      + "table, word frequency and search-based auto-coding."],
    ["Agreement", "Your coding against the machine's on the same quotations: percent "
      + "agreement, Cohen's kappa and Krippendorff's alpha."],
  ];

  return h("section", { id: "workbench", class: "py-24 bg-surface border-t border-b border-hairline" },
    h("div", { class: "max-w-7xl mx-auto px-6" },
      h("div", { class: "grid grid-2 gap-12 items-center mb-16" },
        h("div", { class: "reveal" },
          h("p", { class: "eyebrow mb-3", text: "The workbench" }),
          h("h2", { class: "font-display text-4xl mb-4 leading-tight" },
            "A proper coding surface, not a results screen."),
          h("p", { class: "text-inkfaint leading-relaxed" },
            "The reader shows the document with every quotation highlighted in its "
            + "code's colour, machine and hand coding side by side. Select text to "
            + "code it. Click a highlight to open it, add codes, write a comment, or "
            + "throw it away. This is where an automatic pass stops being a black box.")),
        h("div", { class: "reveal reveal-delay-2" }, readerMock())),
      h("div", { class: "grid grid-3 gap-6" },
        ...features.map(([title, body], i) => h("div", {
          class: "card p-5 card-hover reveal",
          style: "transition-delay:" + (i * 0.05) + "s" },
          h("h3", { class: "font-display text-lg mb-2", text: title }),
          h("p", { class: "text-sm text-inkfaint leading-relaxed", text: body }))))));
}

function readerMock() {
  const passage = [
    ["You ring the hospital and they say ring the GP. ", "#2B4570"],
    ["You ring the GP and they say it is with the hospital now. ", "#2B4570"],
    ["Nobody could tell me where my referral actually was. ", "#B5541B"],
    ["It made me feel invisible. ", "#7A2E4A"],
    ["The system does not do that. ", "#8A6D3B"],
    ["I have thought about that sentence a lot.", null],
  ];
  const text = passage.map(([fragment, color]) => color
    ? h("span", { text: fragment, style: "background:" + color + "1a;border-radius:2px" })
    : h("span", { text: fragment }));

  const chips = [
    ["Chasing as unpaid work", "#2B4570", "auto"],
    ["Nobody owns the case", "#B5541B", "auto"],
    ["Being made invisible", "#7A2E4A", "you"],
    ["Institutional voice", "#8A6D3B", "you"],
  ].map(([label, color, by]) => h("div", {
    class: "code-chip mb-2",
    style: "background:" + color + "14;color:" + color },
    h("span", { class: "code-swatch", style: "background:" + color }),
    h("span", { text: label }),
    h("span", { class: "text-xs", style: "opacity:.7", text: by })));

  return h("div", { class: "card shadow overflow-hidden tilt" },
    h("div", { class: "flex items-center justify-between px-4 py-2 border-b border-hairline" },
      h("span", { class: "text-xs uppercase tracking-wide text-inkfaint",
                  text: "P1 · maria.txt" }),
      h("span", { class: "text-xs text-inkfaint", text: "37 quotations" })),
    h("div", { class: "flex" },
      h("div", { class: "flex-1 p-4 font-display leading-relaxed", style: "min-width:0" }, ...text),
      h("div", { class: "shrink-0 p-4 border-l border-hairline", style: "width:13rem" },
        h("p", { class: "eyebrow mb-2", text: "Margin" }), ...chips)));
}

// --- methodologies --------------------------------------------------------

function methodsSection() {
  const body = h("div", { class: "card p-6", style: "min-height:22rem" });
  const buttons = h("div", { class: "flex flex-wrap gap-2 mb-6" });

  function show(key) {
    for (const node of buttons.children) {
      node.className = "btn btn-sm" + (node.dataset.key === key ? " btn-primary" : "");
    }
    const entry = METHODS.find(([id]) => id === key);
    body.replaceChildren(
      h("div", { class: "grid grid-2 gap-8 items-center" },
        h("div", null,
          h("h3", { class: "font-display text-2xl mb-3", text: entry[1] }),
          h("p", { class: "text-inkfaint leading-relaxed mb-4", text: entry[2] }),
          h("p", { class: "text-sm text-inkfaint",
                   text: "Runs on every analysis — you do not choose one and lose the rest." })),
        h("div", null, methodGraphic(key))));
  }

  METHODS.forEach(([key, name]) => {
    buttons.appendChild(h("button", { class: "btn btn-sm", dataset: { key },
                                      onClick: () => show(key) }, name));
  });

  const section = h("section", { id: "methods", class: "py-24" },
    h("div", { class: "max-w-7xl mx-auto px-6" },
      h("div", { class: "text-center mb-12 reveal" },
        h("p", { class: "eyebrow mb-3", text: "Six methodologies, one corpus" }),
        h("h2", { class: "font-display text-4xl mb-4" },
          "Not a checkbox on the project form."),
        h("p", { class: "text-inkfaint", style: "max-width:42rem;margin:0 auto" },
          "Each methodology is a genuinely different reading of the same coded data, "
          + "with its own objects and its own output — not the same theme list with a "
          + "different heading.")),
      h("div", { class: "reveal" }, buttons, body)));
  show("thematic");
  return section;
}

function methodGraphic(key) {
  if (key === "thematic") {
    return codeNetwork(
      [{ id: "a", label: "Waiting without information", color: "#2B4570", count: 16 },
       { id: "b", label: "Chasing as unpaid work", color: "#B5541B", count: 12 },
       { id: "c", label: "Individuals vs the system", color: "#2F6F4E", count: 9 },
       { id: "d", label: "Becoming an advocate", color: "#8A6D3B", count: 7 },
       { id: "e", label: "Trust in people", color: "#5B4B8A", count: 6 },
       { id: "f", label: "Silence as harm", color: "#7A2E4A", count: 5 }],
      [{ source: "a", target: "b", weight: 6 }, { source: "b", target: "c", weight: 4 },
       { source: "a", target: "f", weight: 5 }, { source: "c", target: "e", weight: 3 },
       { source: "d", target: "b", weight: 2 }],
      { size: 420, height: 300, margin: 120 });
  }
  if (key === "grounded_theory") {
    return sparkline([12, 9, 7, 4, 3, 2], { color: "#2F6F4E", height: 130, width: 380 });
  }
  if (key === "ipa") {
    return barChart([
      { label: "Temporal", value: 34, color: "#2B4570" },
      { label: "Relational", value: 28, color: "#5B4B8A" },
      { label: "Embodied", value: 19, color: "#B5541B" },
      { label: "Existential", value: 14, color: "#8A6D3B" },
      { label: "Spatial", value: 9, color: "#2F6F4E" },
    ]);
  }
  if (key === "framework") {
    return heatmap(["P1", "P2", "P3", "P4", "P5", "P6"], [
      { label: "Expectations", cells: [3, 1, 2, 1, 2, 2], color: "#2B4570" },
      { label: "Barriers", cells: [6, 0, 5, 3, 6, 4], color: "#B5541B" },
      { label: "Enablers", cells: [1, 4, 2, 1, 1, 3], color: "#2F6F4E" },
      { label: "Impact", cells: [4, 1, 4, 2, 5, 3], color: "#8A6D3B" },
      { label: "Suggestions", cells: [2, 2, 3, 1, 4, 2], color: "#5B4B8A" },
    ], { cell: 30, labelWidth: 120 });
  }
  if (key === "narrative") {
    return sparkline([0.3, -0.2, -0.6, -0.8, -0.4, 0.1, 0.5, 0.2, -0.1, 0.4],
                     { color: "#2B4570", height: 140, width: 380 });
  }
  return barChart([
    { label: "Access", value: 61, color: "#2B4570" },
    { label: "Communication", value: 54, color: "#8A6D3B" },
    { label: "Systems", value: 38, color: "#B5541B" },
    { label: "Staff", value: 31, color: "#2F6F4E" },
    { label: "Outcomes", value: 22, color: "#5B4B8A" },
  ]);
}

// --- review intelligence --------------------------------------------------

function reviewsSection() {
  const capabilities = [
    "Paste reviews, add them one at a time, or pull them from a Google Maps URL",
    "Net sentiment score, valence split and negative ratio, not just a star average",
    "Trend across 0-3, 3-6, 6-12 and 12+ months, so you can see when it turned",
    "Operational bottlenecks ranked by severity, with the quotes as evidence",
    "Contradictions — five-star reviews whose text describes a failure",
    "Customer-journey framework matrix: expectations, barriers, enablers, impact",
    "Radar comparison against a competitor, and what to adopt from them",
    "Executive PDF with vector charts, plus the full multi-sheet workbook",
  ];
  const bullets = capabilities.map((item, index) => h("li", {
    class: "flex items-start gap-3 py-2 reveal",
    style: "transition-delay:" + (index * 0.03) + "s" },
    h("span", { html: tick(LEDGER_TICK) }),
    h("span", { class: "text-sm", text: item })));

  return h("section", { id: "reviews", class: "py-24" },
    h("div", { class: "max-w-7xl mx-auto px-6" },
      h("div", { class: "grid grid-2 gap-12 items-center" },
        h("div", { class: "reveal" },
          h("p", { class: "eyebrow mb-3", text: "Also built on the same engine" }),
          h("h2", { class: "font-display text-4xl mb-4 leading-tight" },
            "Review intelligence for operators."),
          h("p", { class: "text-inkfaint leading-relaxed mb-6" },
            "The same coding engine, pointed at customer reviews. Every review is read "
            + "sentence by sentence — emotion, intent, valence, confidence — and turned "
            + "into an executive report: where the friction is, when it started, which "
            + "five-star reviews are hiding a complaint, and what your competitor is "
            + "doing that you are not."),
          h("ul", { class: "divide-y mb-6" }, ...bullets),
          h("div", { class: "flex gap-3 flex-wrap" },
            link("/reviews", { class: "btn btn-primary" }, "Open the review tool"),
            link("/login", { class: "btn" }, "Try it on the demo dataset"))),
        h("div", { class: "reveal reveal-delay-2" }, reportMock()))));
}

const LEDGER_TICK = "#2B4570";

function reportMock() {
  const tiles = [
    ["33", "Net sentiment", "#2F6F4E"],
    ["15", "Reviews", "#2B4570"],
    ["3.53", "Avg rating", "#2B4570"],
    ["27%", "Negative", "#B5541B"],
  ].map(([value, label, colour]) => h("div", {
    class: "card p-3", style: "border-top:3px solid " + colour },
    h("div", { class: "font-display text-xl", style: "color:" + colour, text: value }),
    h("div", { class: "text-xs text-inkfaint", text: label })));

  const bars = [
    ["0-3 months", 2, 1], ["3-6 months", 2, 0],
    ["6-12 months", 1, 2], ["12+ months", 4, 1],
  ];
  const chart = groupedBars(bars.map((row) => row[0]), [
    { name: "Positive", color: "#2F6F4E", values: bars.map((row) => row[1]) },
    { name: "Negative", color: "#B5541B", values: bars.map((row) => row[2]) },
  ], { height: 190 });

  return h("div", { class: "card shadow tilt p-5" },
    h("div", { class: "flex items-center justify-between mb-3" },
      h("span", { class: "text-sm font-medium", text: "Riverside Dental Studio" }),
      h("span", { class: "badge badge-auto", text: "executive report" })),
    h("div", { class: "grid grid-4 gap-2 mb-4" }, ...tiles),
    chart,
    h("div", { class: "bg-warnlight p-3 rounded-card mt-3" },
      h("p", { class: "text-xs uppercase tracking-wide text-warn mb-1",
               text: "Top bottleneck" }),
      h("p", { class: "text-sm", text: "Systems — booking failures, raised by 3 reviewers, "
                                       + "mean rating 1.7" })));
}

// --- parity ---------------------------------------------------------------

function paritySection() {
  const parity = [
    "Documents, groups and comments",
    "Quotations with exact document offsets",
    "Select-to-code, in-vivo coding, quick coding",
    "Code manager: groundedness, density, colours, definitions",
    "Code groups and document groups",
    "Memos attached to any object",
    "Typed relations and network editor",
    "Code co-occurrence and the code–document table",
    "Boolean retrieval across codes",
    "Word frequency, KWIC concordance, search auto-coding",
    "Inter-coder agreement with kappa and alpha",
    "Excel, Word and PDF reporting",
  ];
  const extra = [
    "A complete first coding pass in seconds",
    "Themes clustered with confidence, coverage and counter-cases",
    "Explicit alternative interpretations on every code",
    "Contradiction detection within and between cases",
    "Second-pass stability check on every theme",
    "Six methodologies run at once, each with its own objects",
    "Analytic controls exposed, not hidden in defaults",
    "Every decision written to an audit trail",
    "Machine-versus-you reliability, not just human-versus-human",
    "Runs locally with no install and no dependencies",
  ];

  return h("section", { id: "parity", class: "py-24 bg-surface border-t border-hairline" },
    h("div", { class: "max-w-6xl mx-auto px-6" },
      h("div", { class: "text-center mb-12 reveal" },
        h("p", { class: "eyebrow mb-3", text: "Compared" }),
        h("h2", { class: "font-display text-4xl mb-4" },
          "Everything you expect. Then the part that saves the weeks."),
        h("p", { class: "text-inkfaint", style: "max-width:40rem;margin:0 auto" },
          "Feature parity with a classic CAQDAS workbench is the floor, not the pitch.")),
      h("div", { class: "grid grid-2 gap-8" },
        parityColumn("What a CAQDAS tool must do", parity, "#6B6D76"),
        parityColumn("What QRIP adds", extra, "#2B4570"))));
}

function parityColumn(title, items, color) {
  const rows = items.map((item, i) => h("li", {
    class: "flex items-start gap-3 py-2 reveal",
    style: "transition-delay:" + (i * 0.03) + "s" },
    h("span", { html: tick(color) }),
    h("span", { class: "text-sm", text: item })));
  return h("div", { class: "card p-6" },
    h("h3", { class: "font-display text-xl mb-4", text: title }),
    h("ul", { class: "divide-y" }, ...rows));
}

function tick(color) {
  return '<svg width="16" height="16" viewBox="0 0 16 16" style="margin-top:3px">'
    + '<circle cx="8" cy="8" r="7.2" fill="none" stroke="' + color + '" stroke-opacity="0.35"/>'
    + '<path d="M4.6 8.3 L7 10.6 L11.4 5.6" fill="none" stroke="' + color
    + '" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"'
    + ' stroke-dasharray="14" stroke-dashoffset="14">'
    + '<animate attributeName="stroke-dashoffset" from="14" to="0" dur="0.5s" fill="freeze"/>'
    + "</path></svg>";
}

// --- trust ----------------------------------------------------------------

function trustSection() {
  const cards = [
    ["Nothing is hidden", "Six analytic controls — similarity, confidence, minimum "
      + "quotations, participant threshold, granularity, contradiction sensitivity — "
      + "are on the screen, not buried in defaults. Change one and the findings change; "
      + "the audit trail records that you did."],
    ["Nothing is final", "Every theme carries an alternative reading and its counter-"
      + "cases. Themes that do not survive a second clustering pass are marked unstable "
      + "rather than quietly reported."],
    ["Nothing is a black box", "Every code links to its exact span in the transcript. "
      + "You can always get from a claim back to the sentence a participant said."],
  ];
  return h("section", { class: "py-24" },
    h("div", { class: "max-w-7xl mx-auto px-6" },
      h("div", { class: "text-center mb-12 reveal" },
        h("p", { class: "eyebrow mb-3", text: "Defensibility" }),
        h("h2", { class: "font-display text-4xl" }, "Automation you can defend in a viva.")),
      h("div", { class: "grid grid-3 gap-6" },
        ...cards.map(([title, body], i) => h("div", {
          class: "card p-6 reveal", style: "transition-delay:" + (i * 0.08) + "s" },
          h("h3", { class: "font-display text-xl mb-3", text: title }),
          h("p", { class: "text-sm text-inkfaint leading-relaxed", text: body }))))));
}

function finalCta() {
  return h("section", { class: "section-dark py-24" },
    h("div", { class: "max-w-4xl mx-auto px-6 text-center reveal" },
      h("h2", { class: "font-display text-5xl mb-5 leading-tight" },
        "Your corpus is already coded."),
      h("p", { class: "text-inkfaint text-lg mb-8", style: "max-width:34rem;margin:0 auto 2rem" },
        "Open the demo project and you are looking at 213 quotations, 130 codes, "
        + "20 themes and six methodology readings from six interviews. Then start "
        + "changing them."),
      h("div", { class: "flex gap-3 justify-center flex-wrap" },
        link("/register", { class: "btn btn-lg",
          style: "background:var(--paper);color:var(--ink);border-color:var(--paper)" },
          "Create an account"),
        link("/login", { class: "btn btn-lg",
          style: "background:transparent;color:var(--paper);border-color:#4a4b53" },
          "Sign in to the demo"))));
}

function footer() {
  return h("footer", { class: "py-8 border-t border-hairline" },
    h("div", { class: "max-w-7xl mx-auto px-6 flex items-center justify-between flex-wrap gap-4" },
      h("div", { class: "flex items-center gap-2" },
        h("span", { class: "dot" }),
        h("span", { class: "font-display", text: "QRIP" }),
        h("span", { class: "text-sm text-inkfaint",
                    text: "Qualitative Research Intelligence Platform" })),
      h("p", { class: "text-xs text-inkfaint",
               text: "Runs locally · stdlib Python · no tracking" })));
}
