// Review intelligence: turn Google Maps (or pasted) reviews into an executive
// report — KPIs, trend, bottlenecks, journey matrix and competitor comparison.

import { api } from "../api.js";
import { session } from "../app.js";
import { barChart, donutChart, groupedBars, heatmap, radarChart } from "../charts.js";
import {
  badge, empty, field, h, header, link, navigate, num, pct, toast, when,
} from "../ui.js";

const LEDGER = "#2B4570";
const GREEN = "#2F6F4E";
const AMBER = "#8A6D3B";
const RED = "#B5541B";
const SENTIMENT_COLOUR = { positive: GREEN, neutral: AMBER, negative: RED };

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
  const [providers, jobs] = await Promise.all([
    api.get("/review-providers").catch(() => ({ providers: {}, any: false, note: "" })),
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
    inputPanel(providers),
    jobsPanel(jobs));
}

function inputPanel(providers) {
  const state = { mode: "paste", rows: [] };
  const businessName = h("input", { class: "input", placeholder: "e.g. Riverside Dental Studio" });
  const competitorName = h("input", { class: "input", placeholder: "Optional" });
  const businessUrl = h("input", { class: "input",
    placeholder: "https://www.google.com/maps/place/..." });
  const competitorUrl = h("input", { class: "input", placeholder: "Optional" });
  const businessPaste = h("textarea", { class: "textarea", rows: "9",
    placeholder: "Paste the reviews for your business here" });
  const competitorPaste = h("textarea", { class: "textarea", rows: "6",
    placeholder: "Optional — paste a competitor's reviews to unlock the comparison" });
  const status = h("p", { class: "text-sm text-warn" });
  const submit = h("button", { class: "btn btn-primary btn-lg", type: "submit" },
                   "Generate report");

  const tabs = h("div", { class: "tabs mb-5" });
  const panel = h("div");

  const rowsList = h("div", { class: "space-y-2 mb-3" });
  const rowRating = h("select", { class: "select", style: "width:7rem" },
    h("option", { value: "" }, "Stars"),
    ...[5, 4, 3, 2, 1].map((value) => h("option", { value: String(value) }, value + " ★")));
  const rowReviewer = h("input", { class: "input", placeholder: "Reviewer (optional)" });
  const rowWhen = h("input", { class: "input", placeholder: "e.g. 3 months ago" });
  const rowText = h("textarea", { class: "textarea", rows: "2",
    placeholder: "What did they say?" });

  function drawRows() {
    rowsList.replaceChildren(...state.rows.map((row, index) => h("div", {
      class: "card p-3 flex items-start justify-between gap-3" },
      h("div", null,
        h("div", { class: "flex items-center gap-2 mb-1" },
          row.rating ? h("span", { class: "badge badge-review", text: row.rating + " ★" }) : null,
          h("span", { class: "text-sm font-medium", text: row.reviewer || "Anonymous" }),
          row.relative_time
            ? h("span", { class: "text-xs text-inkfaint", text: row.relative_time }) : null),
        h("p", { class: "text-sm text-inkfaint", text: row.text })),
      h("button", { class: "btn btn-sm btn-danger", onClick: () => {
        state.rows.splice(index, 1);
        drawRows();
      } }, "Remove"))));
    if (!state.rows.length) {
      rowsList.replaceChildren(h("p", { class: "text-sm text-inkfaint",
        text: "No reviews added yet. Fill the fields below and press Add review." }));
    }
  }

  function setMode(mode) {
    state.mode = mode;
    for (const node of tabs.children) {
      node.className = "tab" + (node.dataset.mode === mode ? " tab-active" : "");
    }
    if (mode === "paste") {
      panel.replaceChildren(
        field("Your reviews", businessPaste, PASTE_HINT),
        h("div", { class: "mt-4" },
          field("Competitor reviews", competitorPaste,
                "Optional. Adding these turns on the radar comparison and the "
                + "adoption recommendations.")));
    } else if (mode === "url") {
      panel.replaceChildren(
        providerBanner(providers),
        h("div", { class: "grid grid-2 gap-4 mt-4" },
          field("Google Maps URL", businessUrl,
                "Paste the listing URL — the place id is read out of it."),
          field("Competitor Maps URL", competitorUrl, "Optional.")));
    } else if (mode === "form") {
      panel.replaceChildren(
        h("p", { class: "text-sm text-inkfaint mb-3",
                 text: "Add reviews one at a time. Useful for a handful of reviews you "
                       + "have in front of you, or for reviews from somewhere other "
                       + "than Google." }),
        rowsList,
        h("div", { class: "card p-4" },
          h("div", { class: "flex gap-3 mb-3 flex-wrap" },
            h("div", { style: "width:7rem" }, field("Rating", rowRating)),
            h("div", { class: "flex-1", style: "min-width:12rem" },
              field("Reviewer", rowReviewer)),
            h("div", { class: "flex-1", style: "min-width:12rem" },
              field("When", rowWhen))),
          field("Review", rowText),
          h("div", { class: "flex justify-end mt-3" },
            h("button", { class: "btn btn-sm", type: "button", onClick: () => {
              if (!rowText.value.trim()) {
                toast("Type the review text first.", "error");
                return;
              }
              state.rows.push({
                rating: rowRating.value || null,
                reviewer: rowReviewer.value.trim() || "Anonymous",
                relative_time: rowWhen.value.trim() || null,
                text: rowText.value.trim(),
              });
              rowText.value = "";
              rowReviewer.value = "";
              drawRows();
            } }, "Add review"))));
      drawRows();
    } else {
      panel.replaceChildren(h("div", { class: "card p-5" },
        h("h3", { class: "font-display text-lg mb-2", text: "Demo dataset" }),
        h("p", { class: "text-sm text-inkfaint",
                 text: "15 reviews for a dental practice and 10 for a competitor, "
                       + "written to contain the things this tool looks for: a pricing "
                       + "surprise, a booking failure, a five-star review full of "
                       + "complaint, and a competitor who is simply better organised." })));
    }
  }

  for (const [mode, label] of [["paste", "Paste reviews"], ["url", "Google Maps URL"],
                               ["form", "Add one by one"], ["demo", "Use demo data"]]) {
    tabs.appendChild(h("button", { class: "tab", dataset: { mode }, type: "button",
                                   onClick: () => setMode(mode) }, label));
  }

  const form = h("form", { class: "card p-6 mb-8", onSubmit: async (event) => {
    event.preventDefault();
    status.textContent = "";
    submit.disabled = true;
    submit.textContent = "Analysing…";
    const payload = {
      mode: state.mode,
      business_name: businessName.value.trim(),
      competitor_name: competitorName.value.trim(),
      business_url: businessUrl.value.trim(),
      competitor_url: competitorUrl.value.trim(),
      business_reviews: businessPaste.value,
      competitor_reviews: competitorPaste.value,
      business_review_rows: state.mode === "form" ? state.rows : [],
    };
    try {
      const job = await api.post("/analyze", payload);
      navigate("/reviews/" + job.job_id);
    } catch (error) {
      status.textContent = error.message;
      submit.disabled = false;
      submit.textContent = "Generate report";
    }
  } },
    h("div", { class: "grid grid-2 gap-4 mb-5" },
      field("Business name", businessName),
      field("Competitor name", competitorName)),
    tabs,
    panel,
    h("div", { class: "flex items-center justify-between mt-5 gap-4 flex-wrap" },
      status,
      submit));

  setMode("paste");
  return form;
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
    h("div", { class: "flex gap-2" },
      download("pdf", "Download PDF report"),
      download("excel", "Download .xlsx")));
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

// --- 2. temporal ----------------------------------------------------------

function sectionTemporal(primary) {
  const series = primary.temporal.series;
  if (!series.length) {
    return section("2", "Temporal and sentiment trend",
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

  return section("2", "Temporal and sentiment trend distribution",
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

  return section("3", "Operational bottleneck audit",
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

  return section("4", "Framework matrix: the customer journey",
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

  return section("5", "Competitor cross-comparison",
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
  return section("6", "Content counts and coded evidence",
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
