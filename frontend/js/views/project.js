// The project workspace: transcripts, coding, themes, the six methodologies,
// contradictions, second-pass agreement, controls, audit trail and exports.

import { api } from "../api.js";
import { session } from "../app.js";
import {
  badge, dialog, empty, field, h, header, link, meter, navigate, num, pct,
  sectionTitle, stat, toast, valenceColor, when,
} from "../ui.js";
import { methodologyLabel, METHODOLOGIES } from "./projects.js";
import { renderMethodology } from "./methodologies.js";
import { barChart, codeNetwork, counter, ring, stackedBar } from "../charts.js";
import { workbenchPanel } from "./workbench.js";
import { codesPanel as codeManagerPanel } from "./codes.js";
import { queriesPanel } from "./queries.js";
import { memosPanel } from "./memos.js";
import { networkPanel } from "./network.js";
import { agreementPanel } from "./agreement.js";

const TABS = [
  ["overview", "Overview"],
  ["workbench", "Coding"],
  ["documents", "Documents"],
  ["codes", "Codes"],
  ["quotations", "Quotations"],
  ["themes", "Themes"],
  ["methods", "Methodologies"],
  ["queries", "Queries"],
  ["memos", "Memos"],
  ["networks", "Networks"],
  ["contradictions", "Contradictions"],
  ["agreement", "Agreement"],
  ["controls", "Controls"],
  ["audit", "Audit trail"],
  ["exports", "Export"],
];

export async function projectView(projectId) {
  let project;
  try {
    project = await api.get("/projects/" + projectId);
  } catch (error) {
    toast(error.message, "error");
    navigate("/projects");
    return null;
  }

  const panel = h("div", { class: "mt-6" });
  const statusLine = h("div", { class: "text-sm text-inkfaint" });
  const countStrip = h("div", { class: "flex flex-wrap gap-4 mt-4" });
  const tabBar = h("nav", { class: "tabs" });
  let active = location.hash.replace("#", "") || "overview";
  let pollTimer = null;

  const runButton = h("button", { class: "btn btn-primary", onClick: runAnalysis },
                      "Run analysis");

  function setTab(key) {
    active = key;
    history.replaceState({}, "", location.pathname + "#" + key);
    for (const node of tabBar.children) {
      node.className = "tab" + (node.dataset.tab === key ? " tab-active" : "");
    }
    panel.replaceChildren(h("p", { class: "text-sm text-inkfaint", text: "Loading…" }));
    renderPanel(key);
  }

  for (const [key, label] of TABS) {
    tabBar.appendChild(h("button", { class: "tab", dataset: { tab: key },
                                     onClick: () => setTab(key) }, label));
  }

  async function renderPanel(key) {
    try {
      const node = await PANELS[key](project, refresh);
      if (active === key) panel.replaceChildren(node);
    } catch (error) {
      if (active === key) {
        panel.replaceChildren(empty("Could not load this view.", error.message));
      }
    }
  }

  // A silent refresh updates the header counts without rebuilding the panel —
  // the workbench must not lose its place every time a code is applied.
  async function refresh(options) {
    project = await api.get("/projects/" + projectId);
    renderStatus();
    await renderCounts();
    if (!options || !options.silent) setTab(active);
  }

  async function renderCounts() {
    try {
      const counts = await api.get("/projects/" + projectId + "/overview");
      countStrip.replaceChildren(
        countChip("documents", counts.documents),
        countChip("quotations", counts.quotations),
        countChip("codes", counts.codes),
        countChip("applications", counts.applications),
        countChip("hand coded", counts.hand_coded, counts.hand_coded > 0),
        countChip("themes", counts.themes),
        countChip("memos", counts.memos),
        countChip("relations", counts.links));
    } catch (error) {
      countStrip.replaceChildren();
    }
  }

  function renderStatus() {
    statusLine.replaceChildren();
    if (project.analysis_in_progress) {
      statusLine.appendChild(h("span", { class: "flex items-center gap-2" },
        h("span", { class: "spinner" }),
        h("span", { text: (project.analysis_stage || "working") + " · "
                          + pct(project.analysis_progress) })));
      runButton.disabled = true;
      runButton.textContent = "Analysis running…";
    } else {
      runButton.disabled = false;
      runButton.textContent = project.last_analysis_at ? "Re-run analysis" : "Run analysis";
      if (project.last_analysis_error) {
        statusLine.appendChild(h("span", { class: "text-warn",
          text: "Last run failed: " + project.last_analysis_error }));
      } else if (project.last_analysis_at) {
        statusLine.appendChild(h("span", {
          text: "Last analysed " + when(project.last_analysis_at) }));
      } else {
        statusLine.appendChild(h("span", {
          text: "No analysis has been run yet." }));
      }
    }
  }

  async function poll() {
    try {
      const status = await api.get("/projects/" + projectId + "/analysis/status");
      project.analysis_in_progress = status.analysis_in_progress;
      project.analysis_stage = status.stage;
      project.analysis_progress = status.progress;
      project.last_analysis_error = status.last_analysis_error;
      project.last_analysis_at = status.last_analysis_at;
      renderStatus();
      if (!status.analysis_in_progress) {
        clearInterval(pollTimer);
        pollTimer = null;
        if (status.last_analysis_error) toast(status.last_analysis_error, "error");
        else toast("Analysis complete: " + num(status.theme_count) + " themes from "
                   + num(status.code_count) + " codes.");
        await refresh();
      }
    } catch (error) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  }

  async function runAnalysis() {
    runButton.disabled = true;
    try {
      await api.post("/projects/" + projectId + "/analysis/run");
      project.analysis_in_progress = true;
      project.analysis_stage = "queued";
      project.analysis_progress = 0;
      renderStatus();
      if (!pollTimer) pollTimer = setInterval(poll, 900);
    } catch (error) {
      toast(error.message, "error");
      runButton.disabled = false;
    }
  }

  renderStatus();
  renderCounts();
  if (project.analysis_in_progress && !pollTimer) pollTimer = setInterval(poll, 900);
  setTab(active);

  return h("div", { class: "min-h-screen bg-paper" },
    header(session.user, "project", () => session.signOut()),
    h("main", { class: "max-w-7xl mx-auto px-6 py-10" },
      h("div", { class: "flex items-start justify-between gap-6 mb-6" },
        h("div", { class: "max-w-3xl" },
          link("/projects", { class: "text-xs uppercase tracking-wide text-inkfaint" },
               "← All projects"),
          h("h1", { class: "font-display text-3xl mt-2 mb-2", text: project.name }),
          project.research_question
            ? h("p", { class: "text-base leading-relaxed", text: project.research_question })
            : null,
          project.description
            ? h("p", { class: "text-sm text-inkfaint mt-2", text: project.description })
            : null,
          h("p", { class: "text-xs uppercase tracking-wide text-inkfaint mt-3",
                   text: "Lead methodology · " + methodologyLabel(project.methodology) }),
          countStrip),
        h("div", { class: "text-right space-y-2 shrink-0" }, runButton, statusLine)),
      tabBar,
      panel));
}

function countChip(label, value, highlight) {
  return h("div", { class: "flex items-baseline gap-1" },
    h("span", { class: "font-display text-lg" + (highlight ? " text-confidence" : ""),
                text: String(value) }),
    h("span", { class: "text-xs text-inkfaint", text: label }));
}


// --- panels ---------------------------------------------------------------

const PANELS = {
  overview: overviewPanel,
  workbench: workbenchPanel,
  documents: transcriptsPanel,
  codes: codeManagerPanel,
  quotations: quotationsPanel,
  themes: themesPanel,
  methods: methodsPanel,
  queries: queriesPanel,
  memos: memosPanel,
  networks: networkPanel,
  contradictions: contradictionsPanel,
  agreement: agreementPanel,
  controls: controlsPanel,
  audit: auditPanel,
  exports: exportsPanel,
};

async function overviewPanel(project) {
  const [data, overview, cooccurrence] = await Promise.all([
    api.get("/projects/" + project.id + "/dashboard"),
    api.get("/projects/" + project.id + "/overview").catch(() => null),
    api.get("/projects/" + project.id + "/queries/co-occurrence").catch(() => null),
  ]);
  if (!data.code_count) {
    return empty("Nothing coded yet.",
                 "Upload documents, then run an analysis — or start coding by hand "
                 + "in the Coding tab.");
  }

  const emotions = Object.entries(data.emotion_distribution || {})
    .sort((a, b) => b[1] - a[1]);
  const emotionTotal = emotions.reduce((sum, entry) => sum + entry[1], 0) || 1;
  const hand = overview ? overview.hand_coded : 0;
  const machine = overview ? Math.max(overview.applications - hand, 0) : data.code_count;

  const tiles = h("div", { class: "grid grid-5 gap-3" },
    animatedStat("Documents", data.interview_count),
    animatedStat("Quotations", overview ? overview.quotations : data.code_count),
    animatedStat("Codes", overview ? overview.codes : 0),
    animatedStat("Themes", data.theme_count),
    animatedStat("Contradictions", data.contradiction_count));

  const confidenceCard = h("div", { class: "card p-5" },
    sectionTitle("Coding confidence", "Mean across every coded segment."),
    h("div", { class: "flex items-center gap-5" },
      ring(data.average_confidence, "mean", "#2F6F4E"),
      h("div", null,
        h("p", { class: "text-sm text-inkfaint leading-relaxed",
                 text: num(data.negative_case_count) + " segments run against their theme "
                       + "and are kept as counter-cases rather than dropped." }),
        h("p", { class: "text-sm text-inkfaint leading-relaxed mt-2",
                 text: "Confidence is a property of the evidence, not of the machine's "
                       + "mood: hedged, short or negated segments score lower." }))));

  const provenanceCard = h("div", { class: "card p-5" },
    sectionTitle("Who did the coding",
                 "Machine and hand coding live in the same objects."),
    stackedBar([
      { label: "Machine", value: machine, color: "#2B4570" },
      { label: "You", value: hand, color: "#2F6F4E" },
    ], { height: 26 }),
    h("div", { class: "flex gap-6 mt-3" },
      legend("#2B4570", "Machine", machine),
      legend("#2F6F4E", "Hand coded", hand)),
    h("p", { class: "text-sm text-inkfaint mt-3",
             text: hand
               ? "Your coding takes part in the next analysis — themes are built from "
                 + "both."
               : "Nothing hand coded yet. Open the Coding tab and select a passage; the "
                 + "machine's pass is a starting point, not a verdict." }));

  const affectCard = h("div", { class: "card p-5" },
    sectionTitle("Affective register", "Distribution of coded emotion."),
    h("div", { class: "space-y-2" }, ...emotions.slice(0, 7).map((entry) => h("div", null,
      h("div", { class: "flex justify-between text-xs mb-1" },
        h("span", { text: entry[0] }),
        h("span", { class: "text-inkfaint tabular",
                    text: entry[1] + " · " + pct(entry[1] / emotionTotal) })),
      meter(entry[1] / emotionTotal)))));

  const networkCard = cooccurrence && cooccurrence.nodes.length
    ? h("div", { class: "card p-5" },
        sectionTitle("How the codebook hangs together",
                     "Codes joined where they share quotations or documents."),
        codeNetwork(cooccurrence.nodes.slice(0, 18),
          cooccurrence.edges.slice(0, 70).map((edge) => ({
            source: edge.source, target: edge.target,
            weight: edge.quotation_overlap * 3 + edge.document_overlap })),
          { size: 640, height: 480 }))
    : null;

  const themeList = h("div", null,
    sectionTitle("Themes by coverage"),
    h("div", { class: "card divide-y" }, ...data.themes.slice(0, 8).map((theme) =>
      h("div", { class: "p-4" },
        h("div", { class: "flex items-center justify-between gap-3 mb-1" },
          h("span", { class: "font-display text-lg", text: theme.name }),
          badge(theme.status)),
        h("p", { class: "text-sm text-inkfaint line-clamp-2",
                 text: theme.description || "" }),
        h("div", { class: "flex gap-6 text-xs text-inkfaint mt-2 tabular" },
          h("span", { text: theme.participant_count + " participants" }),
          h("span", { text: theme.quote_count + " quotations" }),
          h("span", { text: "confidence " + theme.confidence.toFixed(2) }),
          h("span", { text: "coverage " + pct(theme.coverage, 1) }))))));

  return h("div", { class: "space-y-8" },
    tiles,
    h("div", { class: "grid grid-2 gap-4" }, confidenceCard, provenanceCard),
    h("div", { class: "grid grid-2 gap-4" }, affectCard,
      h("div", { class: "card p-5" },
        sectionTitle("Participants", "Coded segments per case."),
        barChart(participantCounts(data), { labelWidth: 90, rowHeight: 24 }))),
    networkCard,
    themeList);
}

function participantCounts(data) {
  const counts = new Map();
  for (const theme of data.themes) {
    for (const code of theme.codes) {
      counts.set(code.participant_label, (counts.get(code.participant_label) || 0) + 1);
    }
  }
  return Array.from(counts.entries())
    .sort((a, b) => b[1] - a[1])
    .map((entry) => ({ label: entry[0], value: entry[1], color: "#2B4570" }));
}

function legend(color, label, value) {
  return h("div", { class: "flex items-center gap-2" },
    h("span", { class: "code-swatch", style: "background:" + color }),
    h("span", { class: "text-sm", text: label }),
    h("span", { class: "text-sm text-inkfaint tabular", text: String(value) }));
}

function animatedStat(label, value) {
  return h("div", { class: "stat" },
    h("div", { class: "stat-value" }, counter(Number(value) || 0)),
    h("div", { class: "stat-label", text: label }));
}

function graph(data) {
  const width = 900;
  const height = 420;
  const themes = data.graph_nodes.filter((n) => n.kind === "theme").slice(0, 14);
  const people = data.graph_nodes.filter((n) => n.kind === "participant");
  const pos = new Map();
  people.forEach((node, i) => {
    const angle = (i / Math.max(people.length, 1)) * Math.PI * 2 - Math.PI / 2;
    pos.set(node.id, [width / 2 + Math.cos(angle) * 390, height / 2 + Math.sin(angle) * 185]);
  });
  themes.forEach((node, i) => {
    const angle = (i / Math.max(themes.length, 1)) * Math.PI * 2;
    const radius = themes.length > 6 ? 130 : 80;
    pos.set(node.id, [width / 2 + Math.cos(angle) * radius,
                      height / 2 + Math.sin(angle) * radius * 0.62]);
  });

  const parts = [];
  for (const edge of data.graph_edges) {
    if (edge.kind !== "contributes") continue;
    const a = pos.get(edge.source);
    const b = pos.get(edge.target);
    if (!a || !b) continue;
    const opacity = Math.min(0.5, 0.12 + edge.weight * 0.06);
    parts.push(`<line x1="${a[0]}" y1="${a[1]}" x2="${b[0]}" y2="${b[1]}"
      stroke="#2B4570" stroke-opacity="${opacity}" stroke-width="${Math.min(3, 0.6 + edge.weight * 0.25)}"/>`);
  }
  for (const node of themes) {
    const [x, y] = pos.get(node.id);
    const r = Math.max(6, Math.min(22, 5 + node.size * 0.7));
    const fill = node.status === "confirmed" ? "#2F6F4E"
      : node.status === "candidate" ? "#8A6D3B" : "#2B4570";
    const label = node.label.length > 26 ? node.label.slice(0, 24) + "…" : node.label;
    parts.push(`<circle cx="${x}" cy="${y}" r="${r}" fill="${fill}" fill-opacity="0.85"/>`);
    parts.push(`<text x="${x}" y="${y + r + 12}" text-anchor="middle" font-size="11"
      fill="#1C1D21">${escapeXml(label)}</text>`);
  }
  for (const node of people) {
    const [x, y] = pos.get(node.id);
    parts.push(`<circle cx="${x}" cy="${y}" r="5" fill="#1C1D21"/>`);
    parts.push(`<text x="${x}" y="${y - 11}" text-anchor="middle" font-size="11"
      fill="#6B6D76">${escapeXml(node.label)}</text>`);
  }

  return h("div", { class: "overflow-x-auto" }, h("div", {
    html: `<svg viewBox="0 0 ${width} ${height}" width="100%" style="min-width:720px"
      xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Thematic map">${parts.join("")}</svg>`,
  }));
}

function escapeXml(text) {
  return String(text).replace(/[&<>"]/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

async function transcriptsPanel(project, refresh) {
  const transcripts = await api.get("/projects/" + project.id + "/transcripts");

  const label = h("input", { class: "input", placeholder: "P7 or a pseudonym" });
  const file = h("input", { class: "file-input", type: "file", required: true,
                            accept: ".txt,.md,.docx,.rtf,.csv,.vtt" });
  const submit = h("button", { class: "btn btn-primary", type: "submit" }, "Upload");

  const form = h("form", { class: "card p-5 mb-6", onSubmit: async (event) => {
    event.preventDefault();
    if (!file.files || !file.files[0]) return;
    const body = new FormData();
    body.append("participant_label", label.value.trim());
    body.append("file", file.files[0]);
    submit.disabled = true;
    submit.textContent = "Uploading…";
    try {
      await api.postForm("/projects/" + project.id + "/transcripts", body);
      toast("Transcript uploaded.");
      await refresh();
    } catch (error) {
      toast(error.message, "error");
    } finally {
      submit.disabled = false;
      submit.textContent = "Upload";
    }
  } },
    h("div", { class: "flex gap-4 items-end flex-wrap" },
      h("div", { class: "flex-1" }, field("Participant label", label,
        "Leave blank and the next label in sequence is used.")),
      h("div", { class: "flex-1" }, field("Transcript file", file,
        ".txt, .md, .vtt or .docx — speaker labels like “P1:” and “Interviewer:” are detected.")),
      submit));

  const rows = transcripts.map((transcript) => h("tr", null,
    h("td", { class: "font-medium", text: transcript.participant_label }),
    h("td", { class: "text-inkfaint", text: transcript.filename }),
    h("td", { class: "tabular text-right", text: num(transcript.char_count) }),
    h("td", null, h("span", {
      class: transcript.status === "processed" ? "text-confidence"
        : transcript.status === "failed" ? "text-warn" : "text-inkfaint",
      text: transcript.status })),
    h("td", { class: "text-inkfaint", text: when(transcript.created_at) }),
    h("td", { class: "text-right" },
      h("button", { class: "btn btn-sm", onClick: () => showTranscript(project, transcript) },
        "Read"),
      " ",
      h("button", { class: "btn btn-sm btn-danger", onClick: async () => {
        try {
          await api.del("/projects/" + project.id + "/transcripts/" + transcript.id);
          toast("Transcript removed.");
          await refresh();
        } catch (error) {
          toast(error.message, "error");
        }
      } }, "Delete"))));

  return h("div", null, form,
    transcripts.length
      ? h("div", { class: "card overflow-x-auto" }, h("table", null,
          h("thead", null, h("tr", null,
            h("th", { text: "Participant" }), h("th", { text: "File" }),
            h("th", { class: "text-right", text: "Characters" }),
            h("th", { text: "Status" }), h("th", { text: "Uploaded" }),
            h("th", null))),
          h("tbody", null, ...rows)))
      : empty("No transcripts yet.", "Upload interview transcripts to begin."));
}

async function showTranscript(project, transcript) {
  const detail = await api.get("/projects/" + project.id + "/transcripts/" + transcript.id);
  const codes = detail.codes || [];
  dialog(detail.participant_label + " · " + detail.filename, [
    h("p", { class: "text-xs uppercase tracking-wide text-inkfaint",
             text: codes.length + " codes from this transcript" }),
    codes.length ? h("div", { class: "space-y-3" }, ...codes.slice(0, 12).map((code) =>
      h("div", { class: "border-l-2 border-hairline pl-3" },
        h("p", { class: "text-sm font-medium", text: code.label }),
        h("p", { class: "text-sm text-inkfaint", text: code.quote_text }))))
      : null,
    h("div", { class: "border-t border-hairline pt-3" },
      h("p", { class: "text-xs uppercase tracking-wide text-inkfaint mb-2", text: "Transcript" }),
      h("pre", { class: "text-sm leading-relaxed",
                 style: "white-space:pre-wrap;font-family:inherit",
                 text: detail.raw_text })),
  ]);
}

async function themesPanel(project, refresh) {
  const [themes, suggestions] = await Promise.all([
    api.get("/projects/" + project.id + "/themes"),
    api.get("/projects/" + project.id + "/themes/merge-suggestions").catch(() => []),
  ]);
  if (!themes.length) {
    return empty("No themes yet.", "Run an analysis to cluster codes into themes.");
  }

  const selected = new Set();
  const mergeBar = h("div", { class: "card p-4 mb-4 hidden" });

  function renderMergeBar() {
    mergeBar.className = selected.size >= 2 ? "card p-4 mb-4" : "card p-4 mb-4 hidden";
    mergeBar.replaceChildren(
      h("div", { class: "flex items-center justify-between gap-4 flex-wrap" },
        h("span", { class: "text-sm",
                    text: selected.size + " themes selected for merge" }),
        h("button", { class: "btn btn-primary btn-sm", onClick: async () => {
          const ids = [...selected];
          const name = prompt("Name for the merged theme:",
            themes.find((t) => t.id === ids[0]).name);
          if (name === null) return;
          try {
            await api.post("/projects/" + project.id + "/themes/merge",
                           { theme_ids: ids, new_name: name.trim() });
            toast("Themes merged.");
            await refresh();
          } catch (error) {
            toast(error.message, "error");
          }
        } }, "Merge selected")));
  }

  const cards = themes.map((theme) => themeCard(project, theme, refresh, selected, renderMergeBar));

  return h("div", { class: "space-y-6" },
    suggestions.length
      ? h("div", { class: "card p-5" },
          sectionTitle("Merge suggestions",
            "Theme pairs that sit just below the clustering cut, or that share vocabulary."),
          h("div", { class: "space-y-3" }, ...suggestions.slice(0, 5).map((s) =>
            h("div", { class: "flex items-start justify-between gap-4" },
              h("div", null,
                h("p", { class: "text-sm font-medium",
                         text: s.theme_a_name + "  ·  " + s.theme_b_name }),
                h("p", { class: "text-xs text-inkfaint", text: s.rationale })),
              h("button", { class: "btn btn-sm shrink-0", onClick: async () => {
                try {
                  await api.post("/projects/" + project.id + "/themes/merge",
                    { theme_ids: [s.theme_a_id, s.theme_b_id] });
                  toast("Themes merged.");
                  await refresh();
                } catch (error) { toast(error.message, "error"); }
              } }, "Merge")))))
      : null,
    mergeBar,
    ...cards);
}

function themeCard(project, theme, refresh, selected, renderMergeBar) {
  const checkbox = h("input", { type: "checkbox", onChange: (event) => {
    if (event.target.checked) selected.add(theme.id);
    else selected.delete(theme.id);
    renderMergeBar();
  } });

  const statusSelect = h("select", { class: "select", style: "width:auto",
    onChange: async (event) => {
      try {
        await api.patch("/projects/" + project.id + "/themes/" + theme.id + "/status",
                        { status: event.target.value });
        toast("Status updated.");
        await refresh();
      } catch (error) { toast(error.message, "error"); }
    } },
    ...["confirmed", "review", "candidate", "rejected"].map((value) =>
      h("option", { value, selected: value === theme.status }, value)));

  const quotes = theme.codes.slice(0, 4);
  const counterCases = theme.codes.filter((code) => code.is_negative_case).slice(0, 2);

  return h("div", { class: "card p-5" },
    h("div", { class: "flex items-start justify-between gap-4 mb-3" },
      h("div", { class: "flex items-start gap-3" },
        checkbox,
        h("div", null,
          h("h3", { class: "font-display text-xl", text: theme.name }),
          h("div", { class: "flex gap-4 text-xs text-inkfaint mt-1 tabular" },
            h("span", { text: theme.participant_count + " participants" }),
            h("span", { text: theme.quote_count + " quotations" }),
            h("span", { text: "coverage " + pct(theme.coverage, 1) }),
            theme.contradiction_count
              ? h("span", { class: "text-warn",
                            text: theme.contradiction_count + " contradictions" })
              : null))),
      h("div", { class: "flex items-center gap-2 shrink-0" }, badge(theme.status), statusSelect)),

    h("div", { class: "mb-3" },
      h("div", { class: "flex justify-between text-xs text-inkfaint mb-1" },
        h("span", { text: "Confidence" }),
        h("span", { class: "tabular", text: theme.confidence.toFixed(2) })),
      meter(theme.confidence, "meter-confidence")),

    theme.description ? h("p", { class: "text-sm leading-relaxed mb-3",
                                 text: theme.description }) : null,

    quotes.length ? h("div", { class: "space-y-3 mb-3" }, ...quotes.map((code) =>
      h("div", null,
        h("p", { class: "quote", text: "“" + code.quote_text + "”" }),
        h("p", { class: "text-xs text-inkfaint mt-1" },
          code.participant_label + " · " + code.label + " · " + code.emotion
          + " · confidence " + code.confidence.toFixed(2),
          code.is_negative_case
            ? h("span", { class: "text-warn", text: "  · counter-case" }) : null)))) : null,

    counterCases.length
      ? h("div", { class: "bg-warnlight p-3 rounded-card mb-3" },
          h("p", { class: "text-xs uppercase tracking-wide text-warn mb-1",
                   text: "Counter-cases retained" }),
          ...counterCases.map((code) => h("p", { class: "text-sm",
            text: code.participant_label + ": " + code.quote_text })))
      : null,

    theme.alternative_interpretation
      ? h("div", { class: "bg-ledgerlight p-3 rounded-card mb-3" },
          h("p", { class: "text-xs uppercase tracking-wide text-ledger mb-1",
                   text: "Alternative interpretation" }),
          h("p", { class: "text-sm", text: theme.alternative_interpretation }))
      : null,

    theme.merged_from && theme.merged_from.length
      ? h("p", { class: "text-xs text-inkfaint mb-3",
                 text: "Merged from " + theme.merged_from.map((m) => m.name).join(", ") })
      : null,

    h("div", { class: "flex gap-2 flex-wrap" },
      h("button", { class: "btn btn-sm", onClick: async () => {
        const name = prompt("Rename theme:", theme.name);
        if (!name) return;
        try {
          await api.patch("/projects/" + project.id + "/themes/" + theme.id + "/rename",
                          { name: name.trim() });
          toast("Theme renamed.");
          await refresh();
        } catch (error) { toast(error.message, "error"); }
      } }, "Rename"),
      h("button", { class: "btn btn-sm", onClick: () => splitDialog(project, theme, refresh) },
        "Split…")));
}

function splitDialog(project, theme, refresh) {
  const name = h("input", { class: "input", placeholder: "Name for the new theme" });
  const boxes = theme.codes.map((code) => {
    const box = h("input", { type: "checkbox", value: code.id });
    return h("label", { class: "flex items-start gap-3 py-2 border-b border-hairline" },
      box,
      h("span", null,
        h("span", { class: "text-sm font-medium block", text: code.label }),
        h("span", { class: "text-sm text-inkfaint", text: code.quote_text })));
  });
  const modal = dialog("Split “" + theme.name + "”", [
    h("p", { class: "text-sm text-inkfaint",
             text: "Choose the codes that belong to a separate theme." }),
    field("New theme name", name),
    h("div", { style: "max-height:22rem;overflow-y:auto" }, ...boxes),
  ], [
    h("button", { class: "btn btn-primary", onClick: async () => {
      const ids = boxes.map((row) => row.querySelector("input"))
        .filter((box) => box.checked).map((box) => box.value);
      if (!name.value.trim() || !ids.length) {
        toast("Name the new theme and select at least one code.", "error");
        return;
      }
      try {
        await api.post("/projects/" + project.id + "/themes/split",
          { new_theme_name: name.value.trim(), code_ids_for_new_theme: ids });
        modal.remove();
        toast("Theme split.");
        await refresh();
      } catch (error) { toast(error.message, "error"); }
    } }, "Create theme"),
  ]);
}

async function quotationsPanel(project) {
  const [quotations, applications, themes] = await Promise.all([
    api.get("/projects/" + project.id + "/quotations"),
    api.get("/projects/" + project.id + "/codes"),
    api.get("/projects/" + project.id + "/themes").catch(() => []),
  ]);
  if (!quotations.length) {
    return empty("No quotations yet.",
                 "Run an analysis, or code a passage by hand in the Workbench.");
  }

  const themeNames = new Map(themes.map((theme) => [theme.id, theme.name]));
  const reading = new Map();
  for (const application of applications) {
    if (application.meaning_unit_id) reading.set(application.meaning_unit_id, application);
  }

  const search = h("input", { class: "input",
    placeholder: "Filter by text, code, participant…" });
  const onlyHand = h("input", { type: "checkbox" });
  const onlyCounter = h("input", { type: "checkbox" });
  const count = h("span", { class: "text-sm text-inkfaint pb-2" });
  const body = h("div", { class: "space-y-3" });

  function draw() {
    const query = search.value.trim().toLowerCase();
    const rows = quotations.filter((quotation) => {
      const detail = reading.get(quotation.id);
      if (onlyHand.checked && quotation.created_by !== "user") return false;
      if (onlyCounter.checked && !(detail && detail.is_negative_case)) return false;
      if (!query) return true;
      const haystack = quotation.text + " "
        + quotation.codes.map((code) => code.label).join(" ");
      return haystack.toLowerCase().includes(query);
    });
    count.textContent = rows.length + " of " + quotations.length + " quotations";
    body.replaceChildren(...rows.slice(0, 200).map((quotation) =>
      quotationCard(quotation, reading.get(quotation.id), themeNames)));
  }

  search.addEventListener("input", draw);
  onlyHand.addEventListener("change", draw);
  onlyCounter.addEventListener("change", draw);
  draw();

  return h("div", null,
    h("div", { class: "flex items-end gap-4 mb-4 flex-wrap" },
      h("div", { class: "flex-1", style: "min-width:18rem" }, field("Search", search)),
      h("label", { class: "flex items-center gap-2 text-sm pb-2" }, onlyHand, "Hand coded only"),
      h("label", { class: "flex items-center gap-2 text-sm pb-2" }, onlyCounter,
        "Counter-cases only"),
      count),
    body);
}

function quotationCard(quotation, detail, themeNames) {
  const chips = quotation.codes.map((code) => h("span", {
    class: "code-chip", style: "background:" + code.color + "14;color:" + code.color },
    h("span", { class: "code-swatch", style: "background:" + code.color }),
    h("span", { text: code.label })));

  const meta = [
    h("span", { class: "badge " + (quotation.created_by === "user" ? "badge-user" : "badge-auto"),
                text: quotation.created_by === "user" ? "hand coded" : "machine" }),
  ];
  if (detail) {
    meta.push(h("span", { text: detail.participant_label }));
    if (detail.theme_id) {
      meta.push(h("span", { text: "theme: " + (themeNames.get(detail.theme_id) || "—") }));
    }
    if (detail.emotion) meta.push(h("span", { text: detail.emotion + " · " + detail.intent }));
    meta.push(h("span", { class: "text-" + valenceColor(detail.valence),
                          text: "valence " + Number(detail.valence).toFixed(2) }));
    meta.push(h("span", { text: "confidence " + Number(detail.confidence).toFixed(2) }));
    if (detail.is_negative_case) {
      meta.push(h("span", { class: "text-warn", text: "counter-case" }));
    }
  }

  const alternatives = detail && detail.alternative_interpretations
    && detail.alternative_interpretations.length
    ? h("details", { class: "mt-2" },
        h("summary", { class: "text-xs text-ledger", style: "cursor:pointer",
                       text: "Alternative readings" }),
        h("ul", { class: "mt-2 space-y-1" }, ...detail.alternative_interpretations.map(
          (alternative) => h("li", { class: "text-sm text-inkfaint", text: "· " + alternative }))))
    : null;

  return h("div", { class: "card p-4" },
    h("p", { class: "quote mb-2", text: "“" + quotation.text + "”" }),
    h("div", { class: "flex flex-wrap gap-2 mb-2" }, ...chips),
    h("div", { class: "flex flex-wrap gap-3 text-xs text-inkfaint" }, ...meta),
    quotation.comment
      ? h("p", { class: "text-sm mt-2", text: "Comment: " + quotation.comment }) : null,
    alternatives);
}


async function methodsPanel(project) {
  const available = await api.get("/projects/" + project.id + "/methodologies");
  if (!available.length) {
    return empty("No methodology output yet.",
                 "Run an analysis — all six methodologies run over the same coded corpus.");
  }
  const keys = METHODOLOGIES.map(([key]) => key)
    .filter((key) => available.some((item) => item.methodology === key));
  let current = keys.includes(project.methodology) ? project.methodology : keys[0];

  const bar = h("div", { class: "flex gap-2 flex-wrap mb-6" });
  const body = h("div");

  async function show(key) {
    current = key;
    for (const node of bar.children) {
      node.className = "btn btn-sm" + (node.dataset.key === key ? " btn-primary" : "");
    }
    body.replaceChildren(h("p", { class: "text-sm text-inkfaint", text: "Loading…" }));
    const payload = await api.get("/projects/" + project.id + "/methodology/" + key);
    if (current === key) body.replaceChildren(renderMethodology(key, payload));
  }

  for (const key of keys) {
    bar.appendChild(h("button", { class: "btn btn-sm", dataset: { key },
                                  onClick: () => show(key) }, methodologyLabel(key)));
  }
  await show(current);
  return h("div", null, bar, body);
}

async function contradictionsPanel(project) {
  const items = await api.get("/projects/" + project.id + "/contradictions");
  if (!items.length) {
    return empty("No contradictions detected.",
                 "Raise contradiction sensitivity on the Controls tab to widen the net.");
  }
  return h("div", { class: "space-y-3" },
    h("p", { class: "text-sm text-inkfaint",
             text: "Places where similar material is spoken about in opposing terms — "
                   + "between cases, or within a single account." }),
    ...items.map((item) => h("div", { class: "card p-4" },
      h("div", { class: "flex items-center justify-between gap-4 mb-2" },
        h("span", { class: "text-xs uppercase tracking-wide text-inkfaint",
                    text: item.theme_name || "Across themes" }),
        h("span", { class: "text-xs tabular text-warn",
                    text: "severity " + Number(item.severity).toFixed(2) })),
      meter(item.severity, "meter-warn"),
      h("p", { class: "text-sm leading-relaxed mt-3", text: item.description }))));
}

async function controlsPanel(project, refresh) {
  const similarity = h("input", { class: "input", type: "number", step: "0.01", min: "0.05",
                                  max: "0.95", value: project.similarity_threshold });
  const confidence = h("input", { class: "input", type: "number", step: "0.01", min: "0",
                                  max: "1", value: project.confidence_threshold });
  const minQuotes = h("input", { class: "input", type: "number", min: "1", max: "50",
                                 value: project.min_supporting_quotations });
  const minParticipants = h("input", { class: "input", type: "number", min: "1", max: "50",
                                       value: project.participant_frequency_threshold });
  const sensitivity = h("input", { class: "input", type: "number", step: "0.05", min: "0",
                                   max: "1", value: project.contradiction_sensitivity });
  const granularity = h("select", { class: "select" },
    ...["clause", "sentence", "utterance"].map((value) =>
      h("option", { value, selected: value === project.coding_granularity }, value)));

  const save = h("button", { class: "btn btn-primary", type: "submit" }, "Save controls");

  return h("form", { class: "card p-6 space-y-4", style: "max-width:46rem",
    onSubmit: async (event) => {
      event.preventDefault();
      save.disabled = true;
      try {
        await api.patch("/projects/" + project.id + "/controls", {
          similarity_threshold: Number(similarity.value),
          confidence_threshold: Number(confidence.value),
          min_supporting_quotations: Number(minQuotes.value),
          participant_frequency_threshold: Number(minParticipants.value),
          contradiction_sensitivity: Number(sensitivity.value),
          coding_granularity: granularity.value,
        });
        toast("Controls saved. Re-run the analysis to apply them.");
        await refresh();
      } catch (error) {
        toast(error.message, "error");
      } finally {
        save.disabled = false;
      }
    } },
    sectionTitle("Analysis controls",
      "These are the analytic decisions a researcher normally makes silently. "
      + "Changing them changes the findings, so every change is written to the audit trail."),
    h("div", { class: "grid grid-2 gap-4" },
      field("Similarity threshold", similarity,
            "How close two codes must be to sit in the same theme. Lower = fewer, broader themes."),
      field("Confidence threshold", confidence,
            "Minimum confidence for a theme to be marked confirmed."),
      field("Minimum supporting quotations", minQuotes,
            "How much evidence a theme needs before it counts."),
      field("Participant frequency threshold", minParticipants,
            "How many separate participants a theme must appear in."),
      field("Contradiction sensitivity", sensitivity,
            "Higher values surface subtler tensions, at the cost of more noise."),
      field("Coding granularity", granularity,
            "Clause is finest, utterance treats a whole turn as one unit.")),
    h("div", { class: "flex justify-end" }, save));
}

async function auditPanel(project) {
  const entries = await api.get("/projects/" + project.id + "/audit-log");
  if (!entries.length) return empty("Nothing recorded yet.");
  return h("div", null,
    h("p", { class: "text-sm text-inkfaint mb-4",
             text: "Every decision that shaped these findings — uploads, control changes, "
                   + "renames, merges, splits and analysis runs." }),
    h("div", { class: "card overflow-x-auto" }, h("table", null,
      h("thead", null, h("tr", null,
        h("th", { text: "When" }), h("th", { text: "Action" }),
        h("th", { text: "Entity" }), h("th", { text: "Detail" }))),
      h("tbody", null, ...entries.map((entry) => h("tr", null,
        h("td", { class: "text-inkfaint", text: when(entry.created_at) }),
        h("td", { class: "mono", text: entry.action }),
        h("td", { text: entry.entity_type }),
        h("td", { class: "text-inkfaint text-xs",
                  text: JSON.stringify(entry.details) })))))));
}

async function exportsPanel(project) {
  function button(label, path, filename, note) {
    const btn = h("button", { class: "btn", onClick: async () => {
      btn.disabled = true;
      const original = btn.textContent;
      btn.textContent = "Preparing…";
      try {
        await api.download(path, filename);
      } catch (error) {
        toast(error.message, "error");
      } finally {
        btn.disabled = false;
        btn.textContent = original;
      }
    } }, label);
    return h("div", { class: "card p-5" },
      h("h3", { class: "font-display text-lg mb-1", text: label }),
      h("p", { class: "text-sm text-inkfaint mb-4", text: note }),
      btn);
  }
  const base = "/projects/" + project.id + "/export/";
  return h("div", { class: "grid grid-3 gap-4" },
    button("Workbook (.xlsx)", base + "xlsx", "QRIP_project.xlsx",
      "Project settings, themes, the full codebook with quotations, contradictions, "
      + "second-pass agreement, the framework matrix, content counts and the audit trail."),
    button("Report (.docx)", base + "docx", "QRIP_project.docx",
      "A written report: corpus and method, themes with defining quotations and "
      + "alternative readings, contradictions, all six methodology sections, reflexive note."),
    button("Report (.pdf)", base + "pdf", "QRIP_project.pdf",
      "The same report as a typeset PDF for circulation."));
}
