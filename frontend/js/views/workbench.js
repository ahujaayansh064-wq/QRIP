// The coding workbench: a document reader with every quotation highlighted in
// its code's colour, select-to-code, and an inspector for the open quotation.
// Machine coding and hand coding appear here as the same kind of object.

import { api } from "../api.js";
import { badge, empty, h, toast } from "../ui.js";

export async function workbenchPanel(project, refresh) {
  const documents = await api.get("/projects/" + project.id + "/transcripts");
  if (!documents.length) {
    return empty("No documents yet.",
                 "Upload transcripts on the Documents tab, then code them here.");
  }

  const state = {
    documentId: documents[0].id,
    document: null,
    quotations: [],
    codebook: [],
    selected: null,
    filterCodeId: null,
  };

  const rail = h("div", { class: "workbench-rail" });
  const main = h("div", { class: "workbench-main relative" });
  const side = h("div", { class: "workbench-side" });
  const root = h("div", null,
    h("div", { class: "flex items-center justify-between mb-3 flex-wrap gap-3" },
      h("p", { class: "text-sm text-inkfaint" },
        "Select any passage to code it. Click a highlight to open it. ",
        h("span", { class: "text-ink", text: "Your coding survives every re-run." })),
      h("div", { class: "flex gap-2" },
        h("button", { class: "btn btn-sm", onClick: () => searchCodeDialog(project, load) },
          "Auto-code a search term"))),
    h("div", { class: "workbench" }, rail, main, side));

  async function load() {
    main.replaceChildren(h("div", { class: "p-6" },
      h("div", { class: "skeleton", style: "height:1rem;width:60%" })));
    const data = await api.get("/projects/" + project.id + "/documents/"
                               + state.documentId + "/reader");
    state.document = data.document;
    state.quotations = data.quotations;
    state.codebook = data.codebook;
    if (state.selected) {
      state.selected = state.quotations.find((q) => q.id === state.selected.id) || null;
    }
    drawRail();
    drawReader();
    drawSide();
  }

  function drawRail() {
    const counts = new Map();
    for (const quotation of state.quotations) {
      counts.set(state.documentId, (counts.get(state.documentId) || 0) + 1);
    }
    rail.replaceChildren(
      h("p", { class: "eyebrow px-3 py-3", text: "Documents" }),
      ...documents.map((doc) => h("button", {
        class: "rail-item" + (doc.id === state.documentId ? " is-active" : ""),
        onClick: async () => {
          state.documentId = doc.id;
          state.selected = null;
          await load();
        } },
        h("div", { class: "flex items-center justify-between gap-2" },
          h("span", { class: "font-medium", text: doc.participant_label }),
          h("span", { class: "text-xs text-inkfaint",
                      text: doc.id === state.documentId ? state.quotations.length + "q" : "" })),
        h("div", { class: "text-xs text-inkfaint line-clamp-2", text: doc.filename }))),
      h("p", { class: "eyebrow px-3 py-3", text: "Filter by code" }),
      h("div", { class: "px-3 pb-4" },
        h("select", { class: "select", onChange: (event) => {
          state.filterCodeId = event.target.value || null;
          drawReader();
          drawSide();
        } },
          h("option", { value: "" }, "All codes"),
          ...state.codebook
            .filter((code) => code.groundedness > 0)
            .sort((a, b) => b.groundedness - a.groundedness)
            .map((code) => h("option", { value: code.id, selected: code.id === state.filterCodeId },
              code.name + " (" + code.groundedness + ")")))));
  }

  // --- reader ---------------------------------------------------------------

  function visibleQuotations() {
    if (!state.filterCodeId) return state.quotations;
    return state.quotations.filter((quotation) =>
      quotation.codes.some((code) => code.code_id === state.filterCodeId));
  }

  function drawReader() {
    const text = state.document.raw_text;
    const spans = buildSpans(text, visibleQuotations());
    const body = h("div", { class: "reader", dataset: { reader: "1" } });
    for (const span of spans) {
      const fragment = text.slice(span.start, span.end);
      if (!span.quotations.length) {
        body.appendChild(h("span", { dataset: { start: String(span.start) }, text: fragment }));
        continue;
      }
      const top = span.quotations[span.quotations.length - 1];
      const color = top.codes.length ? top.codes[0].color : "#6B6D76";
      const layered = span.quotations.length > 1;
      const mark = h("mark", {
        dataset: { start: String(span.start), quotation: top.id },
        title: top.codes.map((code) => code.label).join(" · ") || "Uncoded quotation",
        style: "background:" + color + (layered ? "33" : "22")
          + (layered ? ";box-shadow:inset 0 -2px 0 " + color + "66" : ""),
        class: state.selected && span.quotations.some((q) => q.id === state.selected.id)
          ? "is-active" : "",
        onClick: (event) => {
          event.stopPropagation();
          state.selected = top;
          drawReader();
          drawSide();
        },
        text: fragment,
      });
      body.appendChild(mark);
    }
    body.addEventListener("mouseup", onSelectText);
    main.replaceChildren(readerHeader(), body);
  }

  function readerHeader() {
    const doc = state.document;
    return h("div", { class: "flex items-center justify-between px-6 py-3 border-b"
                             + " border-hairline sticky top-0 bg-surface", style: "z-index:2" },
      h("div", null,
        h("span", { class: "font-medium", text: doc.participant_label }),
        h("span", { class: "text-inkfaint text-sm", text: " · " + doc.filename })),
      h("div", { class: "flex items-center gap-3 text-xs text-inkfaint" },
        h("span", { text: visibleQuotations().length + " quotations shown" }),
        h("span", { text: doc.char_count + " characters" })));
  }

  function onSelectText() {
    const selection = window.getSelection();
    if (!selection || selection.isCollapsed) return;
    const range = selection.getRangeAt(0);
    const start = offsetOf(range.startContainer, range.startOffset);
    const end = offsetOf(range.endContainer, range.endOffset);
    if (start === null || end === null || end - start < 2) return;
    openCoder(Math.min(start, end), Math.max(start, end), range);
  }

  function offsetOf(node, offset) {
    let element = node.nodeType === 3 ? node.parentElement : node;
    while (element && !element.dataset.start) element = element.parentElement;
    if (!element) return null;
    const base = Number(element.dataset.start);
    const range = document.createRange();
    range.selectNodeContents(element);
    range.setEnd(node, offset);
    return base + range.toString().length;
  }

  // --- the coding popup -----------------------------------------------------

  function openCoder(start, end, range) {
    closeCoder();
    const snippet = state.document.raw_text.slice(start, end);
    const search = h("input", { class: "input", placeholder: "Search or create a code…" });
    const list = h("div", { class: "coder-list" });
    let highlighted = 0;

    function options() {
      const query = search.value.trim().toLowerCase();
      const matches = state.codebook
        .filter((code) => !query || code.name.toLowerCase().includes(query))
        .sort((a, b) => b.groundedness - a.groundedness)
        .slice(0, 40);
      list.replaceChildren();
      if (query) {
        list.appendChild(coderOption("＋ Create “" + search.value.trim() + "”", "#2B4570",
          () => applyNew(search.value.trim())));
      }
      const inVivo = snippet.trim().split(/\s+/).slice(0, 6).join(" ");
      if (!query && inVivo.length > 3) {
        list.appendChild(coderOption("❝ In vivo: “" + inVivo + "”", "#8A6D3B",
          () => applyNew(inVivo)));
      }
      for (const code of matches) {
        list.appendChild(coderOption(code.name + "  (" + code.groundedness + ")",
          code.color, () => applyExisting(code)));
      }
      highlighted = 0;
      mark();
    }

    function mark() {
      Array.from(list.children).forEach((child, i) => {
        child.classList.toggle("is-highlighted", i === highlighted);
      });
    }

    function coderOption(label, color, action) {
      return h("button", { class: "coder-option w-full", onClick: action },
        h("span", { class: "code-swatch", style: "background:" + color }),
        h("span", { class: "flex-1", text: label }));
    }

    async function applyExisting(code) {
      await create({ code_ids: [code.id] });
    }
    async function applyNew(name) {
      await create({ code_names: [name] });
    }
    async function create(payload) {
      closeCoder();
      try {
        await api.post("/projects/" + project.id + "/quotations",
          Object.assign({ document_id: state.documentId, start, end }, payload));
        toast("Quotation coded.");
        await load();
        if (refresh) refresh({ silent: true });
      } catch (error) {
        toast(error.message, "error");
      }
    }

    search.addEventListener("input", options);
    search.addEventListener("keydown", (event) => {
      if (event.key === "ArrowDown") {
        highlighted = Math.min(highlighted + 1, list.children.length - 1);
        mark();
        event.preventDefault();
      } else if (event.key === "ArrowUp") {
        highlighted = Math.max(highlighted - 1, 0);
        mark();
        event.preventDefault();
      } else if (event.key === "Enter") {
        event.preventDefault();
        const target = list.children[highlighted];
        if (target) target.click();
      } else if (event.key === "Escape") {
        closeCoder();
      }
    });

    const popup = h("div", { class: "coder-popup", dataset: { coder: "1" } },
      h("div", { class: "p-3 border-b border-hairline" },
        h("p", { class: "text-xs text-inkfaint mb-2 line-clamp-3",
                 text: "“" + snippet.slice(0, 160) + (snippet.length > 160 ? "…" : "") + "”" }),
        search),
      list,
      h("div", { class: "p-2 border-t border-hairline flex justify-between items-center" },
        h("span", { class: "text-xs text-inkfaint", text: (end - start) + " characters" }),
        h("button", { class: "btn btn-sm", onClick: closeCoder }, "Cancel")));

    const box = range.getBoundingClientRect();
    const host = main.getBoundingClientRect();
    popup.style.left = Math.max(8, Math.min(box.left - host.left, host.width - 330)) + "px";
    popup.style.top = (box.bottom - host.top + main.scrollTop + 8) + "px";
    main.appendChild(popup);
    options();
    search.focus();
    setTimeout(() => document.addEventListener("mousedown", outsideCoder), 0);
  }

  function outsideCoder(event) {
    const popup = main.querySelector("[data-coder]");
    if (popup && !popup.contains(event.target)) closeCoder();
  }

  function closeCoder() {
    const popup = main.querySelector("[data-coder]");
    if (popup) popup.remove();
    document.removeEventListener("mousedown", outsideCoder);
  }

  // --- inspector ------------------------------------------------------------

  function drawSide() {
    side.replaceChildren(
      state.selected ? inspector(state.selected) : marginList());
  }

  function marginList() {
    const quotations = visibleQuotations();
    return h("div", null,
      h("p", { class: "eyebrow px-3 py-3", text: "Margin · " + quotations.length + " quotations" }),
      h("div", { class: "divide-y" }, ...quotations.slice(0, 200).map((quotation) =>
        h("button", { class: "rail-item", onClick: () => {
          state.selected = quotation;
          drawReader();
          drawSide();
          const mark = main.querySelector('[data-quotation="' + quotation.id + '"]');
          if (mark) mark.scrollIntoView({ block: "center", behavior: "smooth" });
        } },
          h("div", { class: "flex flex-wrap gap-1 mb-1" },
            ...quotation.codes.slice(0, 3).map((code) => h("span", {
              class: "code-chip",
              style: "background:" + code.color + "14;color:" + code.color },
              h("span", { class: "code-swatch", style: "background:" + code.color }),
              h("span", { text: code.label }))),
            quotation.codes.length ? null
              : h("span", { class: "text-xs text-inkfaint", text: "uncoded" })),
          h("p", { class: "text-xs text-inkfaint line-clamp-2", text: quotation.text })))));
  }

  function inspector(quotation) {
    const comment = h("textarea", { class: "textarea", rows: "3",
      placeholder: "Comment on this quotation…", value: quotation.comment || "" });

    const codeSelect = h("select", { class: "select" },
      h("option", { value: "" }, "Add a code…"),
      ...state.codebook.sort((a, b) => b.groundedness - a.groundedness)
        .map((code) => h("option", { value: code.id }, code.name)));

    codeSelect.addEventListener("change", async (event) => {
      if (!event.target.value) return;
      try {
        await api.post("/projects/" + project.id + "/quotations/" + quotation.id + "/codes",
                       { code_id: event.target.value });
        await load();
        if (refresh) refresh({ silent: true });
      } catch (error) {
        toast(error.message, "error");
      }
    });

    const newCode = h("input", { class: "input", placeholder: "…or type a new code and press Enter" });
    newCode.addEventListener("keydown", async (event) => {
      if (event.key !== "Enter" || !newCode.value.trim()) return;
      event.preventDefault();
      try {
        await api.post("/projects/" + project.id + "/quotations/" + quotation.id + "/codes",
                       { name: newCode.value.trim() });
        toast("Code applied.");
        await load();
        if (refresh) refresh({ silent: true });
      } catch (error) {
        toast(error.message, "error");
      }
    });

    return h("div", { class: "p-4 space-y-4" },
      h("div", { class: "flex items-center justify-between" },
        h("p", { class: "eyebrow", text: "Quotation" }),
        h("button", { class: "btn btn-sm btn-ghost", onClick: () => {
          state.selected = null;
          drawReader();
          drawSide();
        } }, "Close")),
      h("p", { class: "quote", text: "“" + quotation.text + "”" }),
      h("div", { class: "flex items-center gap-2 flex-wrap text-xs text-inkfaint" },
        h("span", { class: "badge " + (quotation.created_by === "user" ? "badge-user" : "badge-auto"),
                    text: quotation.created_by === "user" ? "hand coded" : "machine" }),
        h("span", { text: "chars " + quotation.start_offset + "–" + quotation.end_offset })),

      h("div", null,
        h("p", { class: "eyebrow mb-2", text: "Codes" }),
        h("div", { class: "flex flex-wrap gap-2 mb-3" },
          ...quotation.codes.map((code) => h("span", {
            class: "code-chip",
            style: "background:" + code.color + "14;color:" + code.color },
            h("span", { class: "code-swatch", style: "background:" + code.color }),
            h("span", { text: code.label }),
            h("button", { class: "btn-ghost", style: "padding:0 2px;line-height:1",
              title: "Remove this code",
              onClick: async () => {
                try {
                  await api.del("/projects/" + project.id + "/quotations/" + quotation.id
                                + "/codes/" + code.code_id);
                  await load();
                  if (refresh) refresh({ silent: true });
                } catch (error) {
                  toast(error.message, "error");
                }
              } }, "×"))),
          quotation.codes.length ? null
            : h("span", { class: "text-sm text-inkfaint", text: "No codes yet." })),
        codeSelect,
        h("div", { class: "mt-2" }, newCode)),

      h("div", null,
        h("p", { class: "eyebrow mb-2", text: "Comment" }),
        comment,
        h("button", { class: "btn btn-sm mt-2", onClick: async () => {
          try {
            await api.patch("/projects/" + project.id + "/quotations/" + quotation.id,
                            { comment: comment.value });
            toast("Comment saved.");
            await load();
          } catch (error) {
            toast(error.message, "error");
          }
        } }, "Save comment")),

      h("button", { class: "btn btn-sm btn-danger w-full", onClick: async () => {
        try {
          await api.del("/projects/" + project.id + "/quotations/" + quotation.id);
          state.selected = null;
          toast("Quotation deleted.");
          await load();
          if (refresh) refresh({ silent: true });
        } catch (error) {
          toast(error.message, "error");
        }
      } }, "Delete quotation"));
  }

  await load();
  return root;
}

// Split the document at every quotation boundary so overlapping quotations can
// share a run of text without either one being lost.
export function buildSpans(text, quotations) {
  const points = new Set([0, text.length]);
  for (const quotation of quotations) {
    points.add(Math.max(0, Math.min(quotation.start_offset, text.length)));
    points.add(Math.max(0, Math.min(quotation.end_offset, text.length)));
  }
  const ordered = Array.from(points).sort((a, b) => a - b);
  const spans = [];
  for (let i = 0; i < ordered.length - 1; i += 1) {
    const start = ordered[i];
    const end = ordered[i + 1];
    if (end <= start) continue;
    const covering = quotations.filter((quotation) =>
      quotation.start_offset <= start && quotation.end_offset >= end);
    spans.push({ start, end, quotations: covering });
  }
  return spans;
}

function searchCodeDialog(project, reload) {
  const term = h("input", { class: "input", placeholder: "e.g. referral" });
  const name = h("input", { class: "input", placeholder: "Code name (defaults to the term)" });
  const whole = h("input", { type: "checkbox", checked: true });
  const status = h("p", { class: "text-sm text-inkfaint" });

  const run = async () => {
    if (!term.value.trim()) return;
    status.textContent = "Coding…";
    try {
      const result = await api.post("/projects/" + project.id + "/auto-code/search", {
        term: term.value.trim(), code_name: name.value.trim() || term.value.trim(),
        whole_word: whole.checked,
      });
      status.textContent = result.applications + " quotations coded as “"
        + result.code.name + "”.";
      await reload();
    } catch (error) {
      status.textContent = error.message;
    }
  };

  import("../ui.js").then(({ dialog }) => {
    dialog("Auto-code a search term", [
      h("p", { class: "text-sm text-inkfaint" },
        "Every occurrence is captured as a quotation covering its sentence, and coded. "
        + "This is the classic CAQDAS text search, and it runs across all documents."),
      h("label", { class: "field" }, h("span", { class: "label", text: "Search term" }), term),
      h("label", { class: "field" }, h("span", { class: "label", text: "Code name" }), name),
      h("label", { class: "flex items-center gap-2 text-sm" }, whole, "Whole words only"),
      status,
    ], [h("button", { class: "btn btn-primary", onClick: run }, "Code all occurrences")]);
  });
}
