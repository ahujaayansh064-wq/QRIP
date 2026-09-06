// The input form: how reviews get into the tool.
//
// Four ways in, and any number of competitors. Each competitor is an
// independent source, so one can be pasted while another is an Outscraper
// export — which is how real benchmarking actually arrives.

import { api } from "../api.js";
import { field, h, toast } from "../ui.js";

export const PASTE_HINT =
  "Paste reviews in the block format:\n\n"
  + "*(Review 001)*\n"
  + "*Anitha Reddy (2 weeks ago)*\n\n"
  + "The coaching is excellent and the courts are spotless...\n\n"
  + "Plain lines (5 | Great staff (2 weeks ago)), CSV and JSON are also accepted.";

const MODES = [
  ["paste", "Paste reviews"],
  ["upload", "Outscraper file"],
  ["url", "Google Maps URL"],
  ["form", "Add one by one"],
  ["demo", "Demo data"],
];

export function createSource(options) {
  const settings = options || {};
  const state = {
    mode: settings.mode || "paste",
    name: "",
    url: "",
    text: "",
    rows: [],
    uploaded: null,
  };

  const nameInput = h("input", { class: "input",
    placeholder: settings.placeholder || "Business name" });
  nameInput.addEventListener("input", () => { state.name = nameInput.value.trim(); });

  const tabs = h("div", { class: "tabs mb-4" });
  const panel = h("div");
  const summary = h("p", { class: "text-xs text-inkfaint mt-2" });

  const pasteArea = h("textarea", { class: "textarea", rows: settings.rows || "10",
    placeholder: PASTE_HINT });
  pasteArea.addEventListener("input", () => { state.text = pasteArea.value; });

  const urlInput = h("input", { class: "input",
    placeholder: "https://www.google.com/maps/place/..." });
  urlInput.addEventListener("input", () => { state.url = urlInput.value.trim(); });

  const fileInput = h("input", { class: "file-input", type: "file",
    accept: ".xlsx,.csv" });
  fileInput.addEventListener("change", async () => {
    const file = fileInput.files && fileInput.files[0];
    if (!file) return;
    summary.textContent = "Reading " + file.name + "…";
    const body = new FormData();
    body.append("file", file);
    try {
      const result = await api.postForm("/reviews/parse-upload", body);
      state.uploaded = result.reviews;
      if (!state.name && result.business_name) {
        state.name = result.business_name;
        nameInput.value = result.business_name;
      }
      summary.textContent = result.count + " reviews read"
        + (result.business_name ? " for " + result.business_name : "")
        + " · " + result.dated + " dated · e.g. " + result.reviewers.slice(0, 3).join(", ");
    } catch (error) {
      state.uploaded = null;
      summary.textContent = error.message;
    }
  });

  // one-at-a-time entry
  const rowRating = h("select", { class: "select", style: "width:6.5rem" },
    h("option", { value: "" }, "Stars"),
    ...[5, 4, 3, 2, 1].map((value) => h("option", { value: String(value) },
                                        value + " *")));
  const rowReviewer = h("input", { class: "input", placeholder: "Reviewer name" });
  const rowWhen = h("input", { class: "input", placeholder: "e.g. 3 months ago" });
  const rowText = h("textarea", { class: "textarea", rows: "2",
    placeholder: "What did they say?" });
  const rowList = h("div", { class: "space-y-2 mb-3" });

  function drawRows() {
    if (!state.rows.length) {
      rowList.replaceChildren(h("p", { class: "text-sm text-inkfaint",
        text: "No reviews added yet." }));
      return;
    }
    rowList.replaceChildren(...state.rows.map((row, index) => h("div", {
      class: "card p-3 flex items-start justify-between gap-3" },
      h("div", null,
        h("div", { class: "flex items-center gap-2 mb-1" },
          row.rating ? h("span", { class: "badge badge-review",
                                   text: row.rating + " *" }) : null,
          h("span", { class: "text-sm font-medium", text: row.reviewer }),
          row.relative_time ? h("span", { class: "text-xs text-inkfaint",
                                          text: row.relative_time }) : null),
        h("p", { class: "text-sm text-inkfaint", text: row.text })),
      h("button", { class: "btn btn-sm btn-danger", type: "button", onClick: () => {
        state.rows.splice(index, 1);
        drawRows();
      } }, "Remove"))));
  }

  function setMode(mode) {
    state.mode = mode;
    for (const node of tabs.children) {
      node.className = "tab" + (node.dataset.mode === mode ? " tab-active" : "");
    }
    summary.textContent = "";
    if (mode === "paste") {
      panel.replaceChildren(field("Reviews", pasteArea,
        "Reviewer names are read from the attribution line and shown throughout "
        + "the report."));
    } else if (mode === "upload") {
      panel.replaceChildren(
        field("Outscraper export (.xlsx or .csv)", fileInput,
              "Export reviews from Outscraper and drop the file here. Names, "
              + "ratings, dates and owner replies are all read from it."));
    } else if (mode === "url") {
      panel.replaceChildren(field("Google Maps URL", urlInput,
        "Needs OUTSCRAPER_KEY, SERPAPI_KEY or GOOGLE_MAPS_API_KEY configured on "
        + "the server. Without one, export from Outscraper and use the file tab."));
    } else if (mode === "form") {
      panel.replaceChildren(
        rowList,
        h("div", { class: "card p-4" },
          h("div", { class: "flex gap-3 mb-3 flex-wrap" },
            h("div", { style: "width:6.5rem" }, field("Rating", rowRating)),
            h("div", { class: "flex-1", style: "min-width:11rem" },
              field("Reviewer", rowReviewer)),
            h("div", { class: "flex-1", style: "min-width:11rem" },
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
      panel.replaceChildren(h("p", { class: "text-sm text-inkfaint",
        text: "Uses the bundled sample dataset so you can see the whole report "
              + "without supplying data." }));
    }
  }

  const allowed = settings.modes || MODES.map(([mode]) => mode);
  for (const [mode, label] of MODES) {
    if (!allowed.includes(mode)) continue;
    tabs.appendChild(h("button", { class: "tab", dataset: { mode }, type: "button",
                                   onClick: () => setMode(mode) }, label));
  }
  setMode(state.mode);

  return {
    state,
    nameInput,
    node: h("div", null,
      settings.hideName ? null : h("div", { class: "mb-4" },
        field(settings.nameLabel || "Business name", nameInput)),
      tabs, panel, summary),
    payload() {
      const out = { name: state.name };
      if (state.mode === "url") out.url = state.url;
      if (state.mode === "paste") out.reviews = state.text;
      if (state.mode === "form") out.rows = state.rows;
      if (state.mode === "upload") out.rows = state.uploaded || [];
      return out;
    },
    describe() {
      if (state.mode === "paste") return state.text.trim() ? "pasted" : "";
      if (state.mode === "url") return state.url ? "URL" : "";
      if (state.mode === "form") return state.rows.length + " added";
      if (state.mode === "upload") {
        return state.uploaded ? state.uploaded.length + " from file" : "";
      }
      return "demo";
    },
  };
}
