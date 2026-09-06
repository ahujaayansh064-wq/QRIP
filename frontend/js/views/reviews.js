// Review intelligence: turn Google Maps (or pasted) reviews into an executive
// report — KPIs, trend, bottlenecks, journey matrix and competitor comparison.

import { api } from "../api.js";
import { session } from "../app.js";
import { barChart, donutChart, groupedBars, heatmap, radarChart } from "../charts.js";
import {
  badge, empty, field, h, header, link, navigate, num, pct, toast, when,
} from "../ui.js";
import { createSource } from "./reviewinput.js";

const LEDGER = "#2B4570";
const GREEN = "#2F6F4E";
const AMBER = "#8A6D3B";
const RED = "#B5541B";
const SENTIMENT_COLOUR = { positive: GREEN, neutral: AMBER, negative: RED };
const OPEN_Q = "\u201c";
const CLOSE_Q = "\u201d";

const PASTE_HINT =
  "One review per line or per paragraph. Optionally lead with the star rating and "
  + "put the age in brackets:\n5 | Lovely staff, seen on time (2 weeks ago)\n"
  + "1 | Waited 40 minutes and nobody explained why (a month ago)\n\n"
  + "JSON and CSV are accepted too — any columns named rating / review / date / "
  + "reviewer are picked up automatically.";

export async function reviewsView(jobId) {
  const body = h("div", { class: "max-w-7xl mx-auto px-6 py-10" });
  const page = h("div", { class: "min-h-screen bg-paper" },
    header(session.user, "review intelligence", () => session.signOut()),
    body);

  if (jobId) {
    await openJob(body, jobId);
  } else {
    await openStart(body);
  }
  return page;
}

// --- start screen ---------------------------------------------------------

async function openStart(body) {
  const [engine, jobs] = await Promise.all([
    api.get("/reviews/engine").catch(() => ({ reasoning: {}, providers: {} })),
    api.get("/jobs").catch(() => []),
  ]);

  body.replaceChildren(
    h("div", { class: "mb-8" },
      h("p", { class: "eyebrow mb-2", text: "Review intelligence" }),
      h("h1", { class: "font-display text-4xl mb-3",
                text: "Turn a pile of reviews into a decision" }),
      h("p", { class: "text-inkfaint leading-relaxed", style: "max-width:46rem",
               text: "Every review is coded sentence by sentence with the same engine "
                     + "QRIP uses on research interviews — emotion, intent, valence, "
                     + "confidence and an alternative reading — then rolled up into an "
                     + "executive report with charts, an operational bottleneck audit "
                     + "and a competitor comparison." })),
    inputPanel(engine),
    jobsPanel(jobs));
}

function inputPanel(engine) {
  const primary = createSource({ nameLabel: "Your business", rows: "10" });
  const competitors = [];
  const competitorList = h("div", { class: "space-y-4" });
  const status = h("p", { class: "text-sm text-warn" });
  const submit = h("button", { class: "btn btn-primary btn-lg", type: "submit" },
                   "Run analysis");

  function drawCompetitors() {
    competitorList.replaceChildren(...competitors.map((entry, index) => h("div", {
      class: "card p-4" },
      h("div", { class: "flex items-center justify-between mb-3" },
        h("span", { class: "eyebrow", text: "Competitor " + (index + 1) }),
        h("button", { class: "btn btn-sm btn-danger", type: "button", onClick: () => {
          competitors.splice(index, 1);
          drawCompetitors();
        } }, "Remove")),
      entry.node)));
    if (!competitors.length) {
      competitorList.replaceChildren(h("p", { class: "text-sm text-inkfaint",
        text: "No competitors yet. Add as many as you like — each one is analysed "
              + "separately, and every dimension is learned from whichever rival "
              + "actually leads it." }));
    }
  }

  function addCompetitor() {
    competitors.push(createSource({
      nameLabel: "Competitor name", rows: "6",
      placeholder: "Competitor " + (competitors.length + 1),
      modes: ["paste", "upload", "url", "form"],
    }));
    drawCompetitors();
  }

  drawCompetitors();

  const form = h("form", { class: "card p-6 mb-8", onSubmit: async (event) => {
    event.preventDefault();
    status.textContent = "";
    submit.disabled = true;
    submit.textContent = "Analysing…";
    const source = primary.payload();
    const payload = {
      mode: primary.state.mode === "demo" ? "demo"
        : primary.state.mode === "url" ? "url" : "paste",
      business_name: source.name,
      business_url: source.url || "",
      business_reviews: source.reviews || "",
      business_review_rows: source.rows || [],
      competitors: competitors.map((entry) => {
        const value = entry.payload();
        return { name: value.name, url: value.url || "",
                 reviews: value.reviews || "", rows: value.rows || [] };
      }),
    };
    try {
      const job = await api.post("/analyze", payload);
      navigate("/reviews/" + job.job_id);
    } catch (error) {
      status.textContent = error.message;
      submit.disabled = false;
      submit.textContent = "Run analysis";
    }
  } },
    engineBanner(engine),
    h("div", { class: "mb-6" }, primary.node),
    h("div", { class: "flex items-center justify-between mb-3 mt-8" },
      h("h3", { class: "font-display text-xl", text: "Competitors" }),
      h("button", { class: "btn btn-sm", type: "button", onClick: addCompetitor },
        "Add a competitor")),
    competitorList,
    h("div", { class: "flex items-center justify-between mt-6 gap-4 flex-wrap" },
      status, submit));

  return form;
}


function engineBanner(engine) {
  const reasoning = (engine && engine.reasoning) || {};
  if (reasoning.available) {
    return h("div", { class: "card p-4 mb-6",
      style: "background:var(--confidencelight);border-color:transparent" },
      h("p", { class: "text-sm text-confidence" },
        "Reasoning engine: ", h("strong", { text: reasoning.model }),
        " — reviews are coded and themed by meaning in context."));
  }
  return h("div", { class: "card p-4 mb-6",
    style: "background:var(--warnlight);border-color:transparent" },
    h("p", { class: "text-sm text-warn mb-1",
             text: "Claude is not configured, so this run will use the local "
                   + "lexicon engine." }),
    h("p", { class: "text-xs", text: reasoning.reason || "" }),
    h("p", { class: "text-xs mt-2",
             text: "The lexicon matches words rather than meaning, which is what "
                   + "produced weak themes previously. Set ANTHROPIC_API_KEY on the "
                   + "server and pip install anthropic for the intended quality." }));
}


function providerBanner(providers) {
  const configured = Object.entries(providers.providers || {})
    .filter(([, enabled]) => enabled).map(([name]) => name);
  if (configured.length) {
    return h("div", { class: "card p-4", style: "background:var(--confidencelight);"
      + "border-color:transparent" },
      h("p", { class: "text-sm text-confidence",
               text: "Ready: reviews will be fetched via " + configured.join(", ") + "." }));
  }
  return h("div", { class: "card p-4", style: "background:var(--warnlight);"
    + "border-color:transparent" },
    h("p", { class: "text-sm text-warn mb-1", text: "No review provider is configured." }),
    h("p", { class: "text-xs", text: providers.note || "" }),
    h("p", { class: "text-xs mt-2",
             text: "Scraping maps.google.com directly is not supported: it needs a "
                   + "headless browser and breaches Google's terms. Paste the reviews "
                   + "instead — it needs no key and takes seconds." }));
}

function jobsPanel(jobs) {
  if (!jobs.length) {
    return empty("No reports yet.", "Your generated reports will be listed here.");
  }
  return h("div", null,
    h("h2", { class: "font-display text-xl mb-3", text: "Recent reports" }),
    h("div", { class: "card divide-y" }, ...jobs.map((job) =>
      h("div", { class: "p-4 flex items-center justify-between gap-4" },
        h("div", null,
          h("p", { class: "font-medium", text: job.business_name }),
          h("p", { class: "text-xs text-inkfaint",
                   text: job.review_count + " reviews"
                         + (job.competitor_name ? " · vs " + job.competitor_name : "")
                         + " · " + when(job.created_at) })),
        h("div", { class: "flex items-center gap-2" },
          h("span", { class: "badge " + (job.status === "complete" ? "badge-confirmed"
            : job.status === "failed" ? "badge-rejected" : "badge-review"),
            text: job.status }),
          link("/reviews/" + job.job_id, { class: "btn btn-sm" }, "Open"))))));
}

// --- job screen -----------------------------------------------------------

async function openJob(body, jobId) {
  let payload;
  try {
    payload = await api.get("/report/" + jobId);
  } catch (error) {
    toast(error.message, "error");
    navigate("/reviews");
    return;
  }

  if (payload.status !== "complete") {
    renderProgress(body, payload, jobId);
    return;
  }
  renderReport(body, payload);
}

function renderProgress(body, job, jobId) {
  const stage = h("p", { class: "text-lg", text: job.stage || "queued" });
  const bar = h("div", { style: "height:6px;background:var(--hairline);border-radius:99px;"
    + "overflow:hidden" }, h("div", { style: "height:100%;background:var(--ledger);"
    + "width:" + Math.round((job.progress || 0) * 100) + "%;transition:width .4s" }));
  const note = h("p", { class: "text-sm text-inkfaint" });

  body.replaceChildren(h("div", { class: "card p-8", style: "max-width:38rem;margin:3rem auto" },
    h("div", { class: "flex items-center gap-3 mb-4" },
      h("span", { class: "spinner" }),
      h("h1", { class: "font-display text-2xl", text: job.business_name })),
    stage, h("div", { class: "mt-3 mb-3" }, bar), note));

  const timer = setInterval(async () => {
    if (!body.isConnected) {
      clearInterval(timer);
      return;
    }
    try {
      const status = await api.get("/report/" + jobId + "/status");
      stage.textContent = status.stage || status.status;
      bar.firstChild.style.width = Math.round((status.progress || 0) * 100) + "%";
      note.textContent = status.review_count + " reviews"
        + (status.competitor_review_count
          ? " · " + status.competitor_review_count + " competitor reviews" : "");
      if (status.status === "complete") {
        clearInterval(timer);
        const full = await api.get("/report/" + jobId);
        renderReport(body, full);
      } else if (status.status === "failed") {
        clearInterval(timer);
        body.replaceChildren(empty("That analysis failed.", status.error || ""));
      }
    } catch (error) {
      clearInterval(timer);
    }
  }, 700);
}

function renderReport(body, job) {
  const report = job.report;
  const primary = report.primary;
  const comparison = report.comparison;

  body.replaceChildren(
    reportHeader(job, report),
    sectionDashboard(primary, report),
    sectionThemes(primary),
    sectionTemporal(primary),
    sectionBottlenecks(primary),
    sectionFramework(primary),
    comparison ? sectionCompetitor(primary, report.competitor, comparison) : null,
    sectionEvidence(primary),
    methodNote(report));
}

function reportHeader(job, report) {
  function download(kind, label) {
    const button = h("button", { class: "btn", onClick: async () => {
      button.disabled = true;
      const original = button.textContent;
      button.textContent = "Preparing…";
      try {
        await api.download("/report/" + job.job_id + "/" + kind, "QRIP_review." + kind);
      } catch (error) {
        toast(error.message, "error");
      } finally {
        button.disabled = false;
        button.textContent = original;
      }
    } }, label);
    return button;
  }

  return h("div", { class: "flex items-start justify-between gap-6 mb-8 flex-wrap" },
    h("div", null,
      link("/reviews", { class: "text-xs uppercase tracking-wide text-inkfaint" },
           "← All reports"),
      h("h1", { class: "font-display text-4xl mt-2 mb-2", text: report.primary.label }),
      h("p", { class: "text-sm text-inkfaint",
               text: report.primary.kpis.total_reviews + " reviews · "
                     + report.primary.kpis.coded_units + " coded statements · "
                     + report.meta.source_label
                     + (report.competitor ? " · benchmarked against "
                        + report.competitor.label : "") })),
    h("div", { class: "flex gap-2 flex-wrap" },
      download("pdf", "Download PDF report"),
      download("excel", "Download .xlsx"),
      download("codebook", "Download codebook")));
}

// --- 1. dashboard ---------------------------------------------------------

function sectionDashboard(primary, report) {
  const kpis = primary.kpis;
  const segments = [
    { label: "Positive", value: kpis.positive, color: GREEN },
    { label: "Neutral", value: kpis.neutral, color: AMBER },
    { label: "Negative", value: kpis.negative, color: RED },
  ];
  const total = kpis.total_reviews || 1;

  const findings = [];
  if (primary.bottlenecks.length) {
    findings.push(primary.bottlenecks[0].issue + " is the largest friction point, raised by "
      + primary.bottlenecks[0].reviewers + " reviewer(s).");
  }
  const worst = primary.content.summary.filter((entry) => entry.mean_valence < -0.1)[0];
  if (worst) findings.push("Most negative category: " + worst.category + ".");
  const best = primary.content.summary.filter((entry) => entry.mean_valence > 0.2)[0];
  if (best) findings.push("Strongest asset: " + best.category + ".");
  const ratingGap = primary.contradictions.filter((item) => item.kind === "rating-vs-text");
  if (ratingGap.length) {
    findings.push(ratingGap.length + " review(s) carry a star rating that contradicts "
      + "the text — the average rating flatters you.");
  }
  if (report.comparison) findings.push(report.comparison.headline);

  return section("1", "Executive dashboard",
    h("div", { class: "grid grid-4 gap-3 mb-6" },
      kpiTile(String(kpis.net_sentiment_score), "Net sentiment score",
              "positive minus negative share",
              kpis.net_sentiment_score > 20 ? GREEN
                : kpis.net_sentiment_score < 0 ? RED : AMBER),
      kpiTile(num(kpis.total_reviews), "Reviews analysed",
              kpis.coded_units + " statements coded", LEDGER),
      kpiTile(kpis.average_rating ? kpis.average_rating.toFixed(2) : "—",
              "Average star rating", "as published", LEDGER),
      kpiTile(pct(kpis.negative_ratio), "Negative sentiment",
              kpis.negative + " of " + kpis.total_reviews + " reviews",
              kpis.negative_ratio > 0.3 ? RED : AMBER)),
    h("div", { class: "grid grid-2 gap-4" },
      h("div", { class: "card p-5" },
        h("p", { class: "eyebrow mb-3", text: "Sentiment valence" }),
        h("div", { class: "flex items-center gap-6 flex-wrap" },
          donutChart(segments, { size: 200, centre: String(kpis.net_sentiment_score),
                                 centreLabel: "NSS" }),
          h("div", { class: "flex-1", style: "min-width:11rem" },
            ...segments.map((segment) => h("div", { class: "mb-3" },
              h("div", { class: "flex items-center justify-between text-sm mb-1" },
                h("span", { class: "flex items-center gap-2" },
                  h("span", { class: "code-swatch", style: "background:" + segment.color }),
                  segment.label),
                h("span", { class: "text-inkfaint tabular",
                            text: segment.value + " · " + pct(segment.value / total) })),
              h("div", { class: "meter" },
                h("span", { style: "width:" + (segment.value / total) * 100 + "%;background:"
                  + segment.color }))))))),
      h("div", { class: "card p-5" },
        h("p", { class: "eyebrow mb-3", text: "What this says" }),
        h("ul", { class: "space-y-2" }, ...findings.map((finding) =>
          h("li", { class: "text-sm leading-relaxed", text: "· " + finding }))))));
}

function kpiTile(value, label, note, accent) {
  return h("div", { class: "card p-4", style: "border-top:3px solid " + accent },
    h("div", { class: "font-display text-3xl", style: "color:" + accent, text: value }),
    h("div", { class: "stat-label", text: label }),
    h("div", { class: "text-xs text-inkfaint mt-2", text: note }));
}

// --- 2. thematic framework -------------------------------------------------

function sectionThemes(primary) {
  const themes = primary.themes || [];
  const engine = (primary.engine || {}).reasoning;
  if (!themes.length) {
    return section("2", "Thematic framework",
                   empty("No themes were produced for this corpus."));
  }
  const cards = themes.map((theme) => h("div", { class: "card p-5" },
    h("div", { class: "flex items-start justify-between gap-3 mb-2" },
      h("h3", { class: "font-display text-xl", text: theme.theme }),
      badge(theme.status || "candidate")),
    h("div", { class: "flex gap-4 text-xs text-inkfaint mb-3 tabular" },
      h("span", { text: (theme.evidence_count || 0) + " statements" }),
      h("span", { text: (theme.participants || []).length + " reviewers" }),
      h("span", { text: "coverage " + pct(theme.coverage || 0) }),
      h("span", { text: "confidence " + Number(theme.confidence || 0).toFixed(2) })),
    h("div", { class: "meter mb-3" },
      h("span", { style: "width:" + (theme.coverage || 0) * 100 + "%;background:"
        + (SENTIMENT_COLOUR[theme.sentiment] || AMBER) })),
    theme.description
      ? h("p", { class: "text-sm leading-relaxed mb-3", text: theme.description })
      : null,
    ...(theme.quotes || []).slice(0, 2).map((quote) => h("div", { class: "mb-2" },
      h("p", { class: "quote", text: OPEN_Q + quote.text + CLOSE_Q }),
      h("p", { class: "text-xs text-inkfaint mt-1",
               text: (quote.rating ? quote.rating + " stars \u00b7 " : "")
                     + (quote.reviewer || "") }))),
    theme.alternative_interpretation
      ? h("div", { class: "bg-ledgerlight p-3 rounded-card" },
          h("p", { class: "text-xs uppercase tracking-wide text-ledger mb-1",
                   text: "Alternative reading" }),
          h("p", { class: "text-sm", text: theme.alternative_interpretation }))
      : null));

  return section("2", "Thematic framework",
    h("p", { class: "text-sm text-inkfaint mb-4",
             text: engine === "claude"
               ? "Codes were sorted into themes by meaning rather than shared words, "
                 + "by Claude Opus 5 reasoning over the whole codebook."
               : "This run used the local fallback engine, which groups by word "
                 + "similarity. Treat the groupings as provisional." }),
    h("div", { class: "grid grid-2 gap-4" }, ...cards));
}


function sentimentTrendCard(primary) {
  const trend = primary.sentiment_trend || {};
  const points = trend.points || [];
  if (points.length < 2) return null;
  return h("div", { class: "card p-5 mb-4" },
    h("p", { class: "eyebrow mb-1", text: "How sentiment has moved" }),
    h("p", { class: "text-sm text-inkfaint mb-3",
             text: "Coded sentiment of what reviewers wrote, oldest period on the "
                   + "left. Star ratings move in whole numbers and lag behind." }),
    lineChart(points.map((point) => point.mean_sentiment),
              points.map((point) => point.label)),
    h("p", { class: "text-sm mt-3", text: trend.note || "" }));
}


function lineChart(values, labels) {
  const width = 720;
  const height = 190;
  const left = 34;
  const plotHeight = height - 34 - 14;
  const plotWidth = width - left - 14;
  const parts = [];
  for (let step = 0; step <= 4; step += 1) {
    const y = 14 + plotHeight - (plotHeight * step) / 4;
    const value = (-1 + (2 * step) / 4).toFixed(1);
    parts.push('<line x1="' + left + '" y1="' + y + '" x2="' + (left + plotWidth)
      + '" y2="' + y + '" stroke="#EDEBE4"/>');
    parts.push('<text x="' + (left - 6) + '" y="' + (y + 3)
      + '" font-size="9" fill="#6B6D76" text-anchor="end">' + value + "</text>");
  }
  const zero = 14 + plotHeight / 2;
  parts.push('<line x1="' + left + '" y1="' + zero + '" x2="' + (left + plotWidth)
    + '" y2="' + zero + '" stroke="#C9C5B8" stroke-width="1.2"/>');

  const step = plotWidth / Math.max(values.length - 1, 1);
  const coords = values.map((value, index) => {
    const clamped = Math.max(-1, Math.min(1, Number(value) || 0));
    return [left + index * step, 14 + plotHeight - ((clamped + 1) / 2) * plotHeight];
  });
  const path = coords.map((point, index) =>
    (index ? "L" : "M") + point[0].toFixed(1) + " " + point[1].toFixed(1)).join(" ");
  parts.push('<path d="' + path + '" fill="none" stroke="#2B4570" stroke-width="2.2"'
    + ' stroke-dasharray="2000" stroke-dashoffset="2000">'
    + '<animate attributeName="stroke-dashoffset" from="2000" to="0" dur="1.1s"'
    + ' fill="freeze"/></path>');
  coords.forEach((point, index) => {
    parts.push('<circle cx="' + point[0].toFixed(1) + '" cy="' + point[1].toFixed(1)
      + '" r="4" fill="#2B4570"><title>' + escapeText(labels[index]) + ": "
      + Number(values[index]).toFixed(2) + "</title></circle>");
    parts.push('<text x="' + point[0].toFixed(1) + '" y="' + (height - 12)
      + '" font-size="10" fill="#6B6D76" text-anchor="middle">'
      + escapeText(labels[index]) + "</text>");
  });
  return h("div", { class: "overflow-x-auto", html:
    '<svg viewBox="0 0 ' + width + " " + height + '" width="100%"'
    + ' xmlns="http://www.w3.org/2000/svg" style="min-width:520px">'
    + parts.join("") + "</svg>" });
}


function escapeText(value) {
  return String(value === null || value === undefined ? "" : value)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}


// --- 3. temporal ----------------------------------------------------------

function sectionTemporal(primary) {
  const series = primary.temporal.series;
  if (!series.length) {
    return section("3", "Temporal and sentiment trend",
                   empty("No dated reviews, so no trend can be shown."));
  }
  const groups = series.map((entry) => entry.bucket);
  const rows = series.map((entry) => h("tr", null,
    h("td", { text: entry.bucket }),
    h("td", { class: "text-right tabular", text: String(entry.total) }),
    h("td", { class: "text-right tabular text-confidence", text: String(entry.positive) }),
    h("td", { class: "text-right tabular", text: String(entry.neutral) }),
    h("td", { class: "text-right tabular text-warn", text: String(entry.negative) }),
    h("td", { class: "text-right tabular",
              text: entry.average_rating ? entry.average_rating.toFixed(2) : "—" }),
    h("td", { class: "text-right tabular", text: pct(entry.negative_ratio) })));

  return section("3", "Temporal and sentiment trend distribution",
    sentimentTrendCard(primary),
    h("div", { class: "card p-5 mb-4" },
      groupedBars(groups, [
        { name: "Positive", color: GREEN, values: series.map((entry) => entry.positive) },
        { name: "Neutral", color: AMBER, values: series.map((entry) => entry.neutral) },
        { name: "Negative", color: RED, values: series.map((entry) => entry.negative) },
      ], { height: 260 })),
    h("p", { class: "text-sm leading-relaxed mb-4", text: primary.temporal.reading }),
    h("div", { class: "card overflow-x-auto" }, h("table", { class: "row-hover" },
      h("thead", null, h("tr", null,
        h("th", { text: "Period" }),
        h("th", { class: "text-right", text: "Reviews" }),
        h("th", { class: "text-right", text: "Positive" }),
        h("th", { class: "text-right", text: "Neutral" }),
        h("th", { class: "text-right", text: "Negative" }),
        h("th", { class: "text-right", text: "Avg rating" }),
        h("th", { class: "text-right", text: "Negative share" }))),
      h("tbody", null, ...rows))));
}

// --- 3. bottlenecks -------------------------------------------------------

function sectionBottlenecks(primary) {
  const bottlenecks = primary.bottlenecks;
  const contradictions = primary.contradictions;

  const cards = bottlenecks.map((entry) => h("div", { class: "card p-5" },
    h("div", { class: "flex items-start justify-between gap-3 mb-2" },
      h("div", null,
        h("h3", { class: "font-display text-lg", text: entry.issue }),
        h("p", { class: "text-xs text-inkfaint",
                 text: entry.reviewers + " reviewer(s) · " + entry.mentions
                       + " statements · " + pct(entry.coverage) + " of reviews"
                       + (entry.mean_rating ? " · avg " + entry.mean_rating + "★" : "") })),
      h("span", { class: "badge " + (entry.severity_band === 3 ? "badge-rejected"
        : entry.severity_band === 2 ? "badge-candidate" : "badge-review"),
        text: "severity " + entry.severity_band })),
    h("div", { class: "meter meter-warn mb-3" },
      h("span", { style: "width:" + entry.severity * 100 + "%" })),
    ...entry.evidence.map((item) => h("div", { class: "mb-2" },
      h("p", { class: "quote", text: "“" + item.text + "”" }),
      h("p", { class: "text-xs text-inkfaint mt-1",
               text: (item.rating ? item.rating + "★ · " : "") + item.reviewer
                     + " · " + item.bucket })))));

  const contradictionRows = contradictions.map((item) => h("tr", null,
    h("td", { text: item.theme }),
    h("td", null, h("span", { class: "badge " + (item.severity === 3 ? "badge-rejected"
      : item.severity === 2 ? "badge-candidate" : "badge-review"),
      text: String(item.severity) })),
    h("td", { class: "text-inkfaint", text: item.kind }),
    h("td", { text: item.description })));

  return section("4", "Operational bottleneck audit",
    h("p", { class: "text-sm text-inkfaint mb-4",
             text: "Friction ranked by severity: how negative the language is, how many "
                   + "separate reviewers raise it, and how often explicit failure words "
                   + "appear." }),
    bottlenecks.length
      ? h("div", { class: "grid grid-2 gap-4 mb-8" }, ...cards)
      : empty("No sustained negative pattern found."),
    h("h3", { class: "font-display text-xl mb-3", text: "Contradictions matrix" }),
    contradictions.length
      ? h("div", { class: "card overflow-x-auto" }, h("table", { class: "row-hover" },
          h("thead", null, h("tr", null,
            h("th", { text: "Theme" }), h("th", { text: "Severity" }),
            h("th", { text: "Type" }), h("th", { text: "Description" }))),
          h("tbody", null, ...contradictionRows)))
      : empty("No internal contradictions detected."));
}

// --- 4. framework ---------------------------------------------------------

function sectionFramework(primary) {
  const framework = primary.framework;
  const stages = framework.synthesis.map((entry) => h("div", { class: "card p-5" },
    h("div", { class: "flex items-center justify-between gap-3 mb-1" },
      h("h3", { class: "font-display text-lg", text: entry.stage }),
      h("span", { class: "text-xs text-inkfaint",
                  text: pct(entry.coverage || 0) + " of reviewers" })),
    h("div", { class: "meter mb-3" },
      h("span", { style: "width:" + (entry.coverage || 0) * 100 + "%;background:"
        + (SENTIMENT_COLOUR[entry.sentiment] || AMBER) })),
    h("p", { class: "text-sm text-inkfaint leading-relaxed mb-2", text: entry.reading }),
    entry.quote
      ? h("div", null,
          h("p", { class: "quote", text: "“" + entry.quote + "”" }),
          h("p", { class: "text-xs text-inkfaint mt-1", text: entry.quote_reviewer || "" }))
      : null));

  const matrixRows = framework.rows.map((row) => ({
    label: row.reviewer,
    cells: row.cells.map((cell) => cell.count),
    color: LEDGER,
  }));

  return section("5", "Framework matrix: the customer journey",
    h("div", { class: "grid grid-3 gap-4 mb-6" }, ...stages),
    h("div", { class: "card p-5 overflow-x-auto" },
      h("p", { class: "eyebrow mb-3", text: "Reviewer × journey stage" }),
      heatmap(framework.stages, matrixRows, { cell: 34, labelWidth: 130 })));
}

// --- 5. competitor --------------------------------------------------------

function sectionCompetitor(primary, competitor, comparison) {
  const axes = comparison.radar.map((entry) => entry.dimension);
  const rows = comparison.radar.map((entry) => h("tr", null,
    h("td", { text: entry.dimension }),
    h("td", { class: "text-right tabular", text: entry.primary.toFixed(1) }),
    h("td", { class: "text-right tabular", text: entry.competitor.toFixed(1) }),
    h("td", { class: "text-right tabular text-" + (entry.gap >= 0 ? "confidence" : "warn"),
              text: (entry.gap > 0 ? "+" : "") + entry.gap.toFixed(1) }),
    h("td", { class: "text-right tabular",
              text: entry.primary_mentions + " / " + entry.competitor_mentions })));

  const adoption = comparison.adoption_parameters.map((entry) => h("div", { class: "card p-5" },
    h("div", { class: "flex items-start justify-between gap-3 mb-2" },
      h("h3", { class: "font-display text-lg", text: entry.parameter }),
      h("span", { class: "badge badge-candidate", text: "gap " + entry.gap })),
    h("p", { class: "text-sm leading-relaxed mb-3", text: entry.recommendation }),
    entry.evidence
      ? h("div", null,
          h("p", { class: "eyebrow mb-1", text: "Their customers say" }),
          h("p", { class: "quote", text: "“" + entry.evidence.text + "”" }))
      : null,
    entry.your_evidence
      ? h("div", { class: "mt-3" },
          h("p", { class: "eyebrow mb-1", text: "Yours say" }),
          h("p", { class: "quote", text: "“" + entry.your_evidence.text + "”" }))
      : null));

  return section("6", "Competitor cross-comparison",
    h("p", { class: "text-base leading-relaxed mb-4", text: comparison.headline }),
    h("div", { class: "grid grid-2 gap-4 mb-6" },
      h("div", { class: "card p-5 flex justify-center" },
        radarChart(axes, [
          { name: primary.label, color: LEDGER,
            values: comparison.radar.map((entry) => entry.primary) },
          { name: competitor.label, color: AMBER,
            values: comparison.radar.map((entry) => entry.competitor) },
        ], { size: 460 })),
      h("div", { class: "card overflow-x-auto" }, h("table", { class: "row-hover" },
        h("thead", null, h("tr", null,
          h("th", { text: "Dimension" }),
          h("th", { class: "text-right", text: "You" }),
          h("th", { class: "text-right", text: "Them" }),
          h("th", { class: "text-right", text: "Gap" }),
          h("th", { class: "text-right", text: "Mentions" }))),
        h("tbody", null, ...rows)))),
    h("h3", { class: "font-display text-xl mb-3", text: "Adoption parameters" }),
    adoption.length
      ? h("div", { class: "grid grid-2 gap-4" }, ...adoption)
      : empty("No competitor strength stands out as something you lack."));
}

// --- evidence and method --------------------------------------------------

function sectionEvidence(primary) {
  const categories = primary.content.summary.filter((entry) => entry.mentions > 0);
  return section("7", "Content counts and coded evidence",
    h("div", { class: "grid grid-2 gap-4" },
      h("div", { class: "card p-5" },
        h("p", { class: "eyebrow mb-3", text: "Mentions by category" }),
        barChart(categories.map((entry) => ({
          label: entry.category, value: entry.mentions,
          color: SENTIMENT_COLOUR[entry.sentiment] || AMBER,
          display: entry.mentions + " (" + entry.mean_valence + ")",
        })))),
      h("div", { class: "card p-5" },
        h("p", { class: "eyebrow mb-3", text: "Themes found" }),
        h("div", { class: "space-y-2", style: "max-height:22rem;overflow-y:auto" },
          ...primary.themes.slice(0, 12).map((theme) => h("div", null,
            h("div", { class: "flex items-center justify-between gap-2" },
              h("span", { class: "text-sm font-medium", text: theme.theme }),
              badge(theme.status)),
            h("p", { class: "text-xs text-inkfaint",
                     text: theme.quote_count + " statements · "
                           + theme.reviewers.length + " reviewers · "
                           + theme.sentiment })))))));
}

function methodNote(report) {
  return h("div", { class: "card p-6 mt-8" },
    h("h3", { class: "font-display text-lg mb-2", text: "Method and limitations" }),
    h("p", { class: "text-sm text-inkfaint leading-relaxed mb-2",
             text: "Each review is split into sentences and coded individually — an "
                   + "emotion, a discourse intent, a valence from -1 to +1, a confidence "
                   + "score and an alternative reading. Review-level sentiment blends the "
                   + "text (65%) with the star rating (35%), which is why a five-star "
                   + "review full of complaint still registers as negative and shows up "
                   + "in the contradictions matrix." }),
    h("p", { class: "text-sm text-inkfaint leading-relaxed",
             text: "Limitations: review text is self-selected and skews to extremes; "
                   + "relative timestamps are normalised to approximate dates, so period "
                   + "boundaries are indicative; and the engine is lexicon-driven, so it "
                   + "reads sarcasm poorly. Every number here traces back to a quotation "
                   + "in the workbook." }),
    h("p", { class: "text-xs text-inkfaint mt-3",
             text: "Engine: " + report.meta.engine + " · generated "
                   + when(report.meta.generated_at) }));
}

function section(number, title, ...children) {
  return h("section", { class: "mb-12" },
    h("div", { class: "flex items-baseline gap-3 mb-4 pb-2 border-b border-hairline" },
      h("span", { class: "font-display text-2xl text-hairline", text: number }),
      h("h2", { class: "font-display text-2xl", text: title })),
    ...children);
}
