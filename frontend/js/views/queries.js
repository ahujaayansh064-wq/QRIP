// Query tools: code co-occurrence, the code–document table, Boolean retrieval,
// word frequency and search-based auto-coding.

import { api } from "../api.js";
import { codeNetwork, heatmap, wordCloud } from "../charts.js";
import { empty, h, num, toast } from "../ui.js";

const TOOLS = [
  ["cooccurrence", "Co-occurrence"],
  ["codedoc", "Code–document table"],
  ["retrieve", "Retrieval"],
  ["words", "Word frequency"],
];

export async function queriesPanel(project) {
  const bar = h("div", { class: "flex gap-2 flex-wrap mb-6" });
  const body = h("div");
  let current = "cooccurrence";

  async function show(key) {
    current = key;
    for (const node of bar.children) {
      node.className = "btn btn-sm" + (node.dataset.key === key ? " btn-primary" : "");
    }
    body.replaceChildren(h("div", { class: "skeleton", style: "height:9rem" }));
    try {
      const node = await TOOL_VIEWS[key](project);
      if (current === key) body.replaceChildren(node);
    } catch (error) {
      if (current === key) body.replaceChildren(empty("Could not run this query.", error.message));
    }
  }

  for (const [key, label] of TOOLS) {
    bar.appendChild(h("button", { class: "btn btn-sm", dataset: { key },
                                  onClick: () => show(key) }, label));
  }
  await show(current);
  return h("div", null, bar, body);
}

// --- co-occurrence --------------------------------------------------------

async function coOccurrenceView(project) {
  const data = await api.get("/projects/" + project.id + "/queries/co-occurrence");
  if (!data.edges.length) {
    return empty("No co-occurrence yet.",
                 "Two codes co-occur when they share a quotation or a document.");
  }
  const top = data.nodes.slice(0, 22);
  const ids = new Set(top.map((node) => node.id));
  const edges = data.edges
    .filter((edge) => ids.has(edge.source) && ids.has(edge.target))
    .slice(0, 90)
    .map((edge) => ({ source: edge.source, target: edge.target,
                      weight: edge.quotation_overlap * 3 + edge.document_overlap }));

  const rows = data.edges.slice(0, 40).map((edge) => h("tr", null,
    h("td", { text: edge.source_name }),
    h("td", { text: edge.target_name }),
    h("td", { class: "text-right tabular", text: String(edge.quotation_overlap) }),
    h("td", { class: "text-right tabular", text: String(edge.document_overlap) }),
    h("td", { class: "text-right tabular", text: edge.c_coefficient.toFixed(3) })));

  return h("div", { class: "space-y-6" },
    h("div", { class: "card p-5" },
      h("h3", { class: "font-display text-lg mb-1", text: "Which codes travel together" }),
      h("p", { class: "text-sm text-inkfaint mb-4" },
        "Lines connect codes that share quotations or documents; thickness is the "
        + "strength of the overlap. Nodes are sized by how often each code is applied."),
      codeNetwork(top, edges, { size: 640, height: 520 })),
    h("div", { class: "card overflow-x-auto" },
      h("table", { class: "row-hover" },
        h("thead", null, h("tr", null,
          h("th", { text: "Code" }), h("th", { text: "Co-occurs with" }),
          h("th", { class: "text-right", text: "Same quotation" }),
          h("th", { class: "text-right", text: "Same document" }),
          h("th", { class: "text-right", text: "c-coefficient" }))),
        h("tbody", null, ...rows))));
}

// --- code-document --------------------------------------------------------

async function codeDocumentView(project) {
  const table = await api.get("/projects/" + project.id + "/queries/code-document");
  if (!table.rows.length) return empty("Nothing coded yet.");
  const rows = table.rows.slice(0, 30).map((row) => ({
    label: row.code, cells: row.cells, color: row.color,
  }));
  return h("div", { class: "space-y-6" },
    h("div", { class: "card p-5 overflow-x-auto" },
      h("h3", { class: "font-display text-lg mb-1", text: "Code by document" }),
      h("p", { class: "text-sm text-inkfaint mb-4" },
        "How often each code is applied in each case. Read a row for spread across "
        + "cases, a column for what dominates one interview."),
      heatmap(table.columns, rows, { cell: 34, labelWidth: 220 })),
    h("div", { class: "card overflow-x-auto" },
      h("table", { class: "row-hover" },
        h("thead", null, h("tr", null,
          h("th", { text: "Code" }),
          ...table.columns.map((column) => h("th", { class: "text-right", text: column })),
          h("th", { class: "text-right", text: "Total" }),
          h("th", { class: "text-right", text: "Cases" }))),
        h("tbody", null, ...table.rows.map((row) => h("tr", null,
          h("td", null, h("div", { class: "flex items-center gap-2" },
            h("span", { class: "code-swatch", style: "background:" + row.color }),
            h("span", { text: row.code }))),
          ...row.cells.map((cell) => h("td", { class: "text-right tabular",
                                               text: cell || "·" })),
          h("td", { class: "text-right tabular font-medium", text: String(row.total) }),
          h("td", { class: "text-right tabular", text: String(row.documents) })))))));
}

// --- retrieval ------------------------------------------------------------

async function retrievalView(project) {
  const codebook = await api.get("/projects/" + project.id + "/codebook");
  const grounded = codebook.filter((code) => code.groundedness > 0)
    .sort((a, b) => b.groundedness - a.groundedness);
  const chosen = new Set();
  const operator = h("select", { class: "select" },
    h("option", { value: "any" }, "any of these codes (OR)"),
    h("option", { value: "all" }, "all of these codes (AND)"),
    h("option", { value: "none" }, "none of these codes (NOT)"),
    h("option", { value: "only" }, "exactly these codes"));
  const scope = h("select", { class: "select" },
    h("option", { value: "quotation" }, "within a quotation"),
    h("option", { value: "document" }, "anywhere in the document"));
  const results = h("div", { class: "space-y-3" });
  const summary = h("p", { class: "text-sm text-inkfaint" });

  const chips = h("div", { class: "flex flex-wrap gap-2 mb-4",
    style: "max-height:12rem;overflow-y:auto" },
    ...grounded.slice(0, 60).map((code) => {
      const chip = h("button", { class: "code-chip",
        style: "background:" + code.color + "14;color:" + code.color,
        onClick: () => {
          if (chosen.has(code.id)) {
            chosen.delete(code.id);
            chip.style.outline = "";
          } else {
            chosen.add(code.id);
            chip.style.outline = "2px solid " + code.color;
          }
        } },
        h("span", { class: "code-swatch", style: "background:" + code.color }),
        h("span", { text: code.name + " (" + code.groundedness + ")" }));
      return chip;
    }));

  async function run() {
    if (!chosen.size) {
      summary.textContent = "Choose at least one code.";
      return;
    }
    summary.textContent = "Retrieving…";
    try {
      const data = await api.post("/projects/" + project.id + "/queries/retrieve", {
        operator: operator.value, scope: scope.value, code_ids: Array.from(chosen),
      });
      summary.textContent = data.count + " quotations match.";
      results.replaceChildren(...data.results.slice(0, 60).map((quotation) =>
        h("div", { class: "card p-4" },
          h("p", { class: "quote mb-2", text: "“" + quotation.text + "”" }),
          h("div", { class: "flex flex-wrap gap-2" },
            ...quotation.codes.map((code) => h("span", {
              class: "code-chip", style: "background:" + code.color + "14;color:" + code.color },
              h("span", { class: "code-swatch", style: "background:" + code.color }),
              h("span", { text: code.label })))))));
    } catch (error) {
      summary.textContent = error.message;
    }
  }

  return h("div", { class: "space-y-6" },
    h("div", { class: "card p-5" },
      h("h3", { class: "font-display text-lg mb-1", text: "Retrieve quotations" }),
      h("p", { class: "text-sm text-inkfaint mb-4",
               text: "Boolean retrieval across the codebook — the query tool a CAQDAS "
                     + "workbench lives on." }),
      chips,
      h("div", { class: "flex gap-3 items-end flex-wrap" },
        h("div", { style: "min-width:14rem" }, h("span", { class: "label", text: "Match" }), operator),
        h("div", { style: "min-width:14rem" }, h("span", { class: "label", text: "Scope" }), scope),
        h("button", { class: "btn btn-primary", onClick: run }, "Run query")),
      h("div", { class: "mt-3" }, summary)),
    results);
}

// --- word frequency -------------------------------------------------------

async function wordsView(project) {
  const data = await api.get("/projects/" + project.id + "/word-frequency");
  if (!data.words.length) return empty("No text to count yet.");
  const cloud = data.words.slice(0, 70).map((word) => ({
    term: word.term, count: word.count, weight: word.weight,
    color: word.documents >= data.documents.length ? "#2B4570" : "#6B6D76",
  }));
  const rows = data.words.slice(0, 60).map((word) => h("tr", null,
    h("td", { text: word.term }),
    h("td", { class: "text-right tabular", text: num(word.count) }),
    h("td", { class: "text-right tabular", text: String(word.documents) }),
    h("td", { class: "text-right tabular", text: word.weight.toFixed(1) }),
    h("td", { class: "text-right" },
      h("button", { class: "btn btn-sm", onClick: async () => {
        try {
          const result = await api.post("/projects/" + project.id + "/auto-code/search",
                                        { term: word.term, code_name: word.term });
          toast(result.applications + " quotations coded as “" + result.code.name + "”.");
        } catch (error) {
          toast(error.message, "error");
        }
      } }, "Code every mention"))));

  return h("div", { class: "space-y-6" },
    h("div", { class: "card p-5" },
      h("h3", { class: "font-display text-lg mb-1", text: "What the corpus keeps saying" }),
      h("p", { class: "text-sm text-inkfaint mb-2" },
        num(data.total_words) + " content words. Darker terms appear in every document; "
        + "size is keyness, not raw frequency."),
      wordCloud(cloud, { height: 340 })),
    h("div", { class: "card overflow-x-auto" },
      h("table", { class: "row-hover" },
        h("thead", null, h("tr", null,
          h("th", { text: "Term" }),
          h("th", { class: "text-right", text: "Count" }),
          h("th", { class: "text-right", text: "Documents" }),
          h("th", { class: "text-right", text: "Keyness" }),
          h("th", null, ""))),
        h("tbody", null, ...rows))));
}

const TOOL_VIEWS = {
  cooccurrence: coOccurrenceView,
  codedoc: codeDocumentView,
  retrieve: retrievalView,
  words: wordsView,
};
