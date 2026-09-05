// Network editor: drag objects onto a canvas and draw typed relations between
// them. Layouts are saved, so a network is a working object, not a screenshot.

import { api } from "../api.js";
import { dialog, empty, field, h, toast } from "../ui.js";

const KIND_COLOR = {
  code: "#2B4570", theme: "#2F6F4E", document: "#4F5D66",
  quotation: "#8A6D3B", memo: "#5B4B8A",
};

export async function networkPanel(project) {
  const [targetData, links, networks] = await Promise.all([
    api.get("/projects/" + project.id + "/link-targets"),
    api.get("/projects/" + project.id + "/links"),
    api.get("/projects/" + project.id + "/networks"),
  ]);
  const targets = targetData.targets;
  const relations = targetData.relations;
  const byKey = new Map(targets.map((target) => [target.type + ":" + target.id, target]));

  const state = {
    nodes: new Map(),          // key -> {key, target, x, y}
    links: links,
    linking: null,
    networkId: networks.length ? networks[0].id : null,
    name: networks.length ? networks[0].name : "Untitled network",
  };

  const canvas = h("div", { class: "relative", style: "height:30rem;background:"
    + "radial-gradient(circle at 1px 1px, var(--hairline) 1px, transparent 0);"
    + "background-size:22px 22px;overflow:hidden;border-radius:var(--radius)" });
  const edgeLayer = h("div", { class: "absolute", style: "inset:0;pointer-events:none" });
  canvas.appendChild(edgeLayer);

  function loadLayout(layout) {
    state.nodes.clear();
    for (const node of (layout && layout.nodes) || []) {
      const target = byKey.get(node.key);
      if (target) state.nodes.set(node.key, { key: node.key, target, x: node.x, y: node.y });
    }
  }

  if (networks.length) loadLayout(networks[0].layout);
  // A saved layout can point at codes that have since been merged or deleted;
  // rather than showing an empty canvas, fall back to seeding it.
  if (!state.nodes.size) {
    const linked = new Set();
    for (const link of links) {
      linked.add(link.source_type + ":" + link.source_id);
      linked.add(link.target_type + ":" + link.target_id);
    }
    const seeds = targets.filter((target) => linked.has(target.type + ":" + target.id))
      .concat(targets.filter((target) => target.type === "theme").slice(0, 4))
      .slice(0, 8);
    seeds.forEach((target, i) => {
      const angle = (i / Math.max(seeds.length, 1)) * Math.PI * 2;
      state.nodes.set(target.type + ":" + target.id, {
        key: target.type + ":" + target.id, target,
        x: 360 + Math.cos(angle) * 190, y: 220 + Math.sin(angle) * 130,
      });
    });
  }

  function draw() {
    Array.from(canvas.querySelectorAll("[data-node]")).forEach((node) => node.remove());
    const parts = [];
    for (const link of state.links) {
      const a = state.nodes.get(link.source_type + ":" + link.source_id);
      const b = state.nodes.get(link.target_type + ":" + link.target_id);
      if (!a || !b) continue;
      const mx = (a.x + b.x) / 2;
      const my = (a.y + b.y) / 2;
      parts.push('<line x1="' + a.x + '" y1="' + a.y + '" x2="' + b.x + '" y2="' + b.y
        + '" stroke="#6B6D76" stroke-opacity="0.55" stroke-width="1.4"/>');
      parts.push('<circle cx="' + mx + '" cy="' + my + '" r="3" fill="#6B6D76"/>');
      parts.push('<text x="' + mx + '" y="' + (my - 7) + '" font-size="10" fill="#6B6D76"'
        + ' text-anchor="middle">' + escapeXml(link.relation) + "</text>");
    }
    edgeLayer.innerHTML = '<svg width="100%" height="100%" style="overflow:visible">'
      + parts.join("") + "</svg>";

    for (const node of state.nodes.values()) {
      canvas.appendChild(nodeChip(node));
    }
  }

  function nodeChip(node) {
    const color = KIND_COLOR[node.target.type] || "#2B4570";
    const chip = h("div", {
      dataset: { node: node.key },
      class: "card p-2 absolute",
      style: "left:" + node.x + "px;top:" + node.y + "px;transform:translate(-50%,-50%);"
        + "cursor:grab;max-width:12rem;border-color:" + color + "55;background:var(--surface);"
        + "box-shadow:var(--shadow-sm);user-select:none",
    },
      h("div", { class: "flex items-center gap-2" },
        h("span", { class: "code-swatch", style: "background:" + color }),
        h("span", { class: "text-xs", style: "white-space:nowrap;overflow:hidden;"
          + "text-overflow:ellipsis;max-width:9rem", text: node.target.label })),
      h("div", { class: "text-xs text-inkfaint", text: node.target.type }));

    chip.addEventListener("pointerdown", (event) => {
      if (state.linking) return;
      event.preventDefault();
      chip.setPointerCapture(event.pointerId);
      chip.style.cursor = "grabbing";
      const rect = canvas.getBoundingClientRect();
      const move = (moveEvent) => {
        node.x = Math.max(20, Math.min(moveEvent.clientX - rect.left, rect.width - 20));
        node.y = Math.max(20, Math.min(moveEvent.clientY - rect.top, rect.height - 20));
        chip.style.left = node.x + "px";
        chip.style.top = node.y + "px";
        drawEdgesOnly();
      };
      const up = () => {
        chip.style.cursor = "grab";
        chip.removeEventListener("pointermove", move);
        chip.removeEventListener("pointerup", up);
      };
      chip.addEventListener("pointermove", move);
      chip.addEventListener("pointerup", up);
    });

    chip.addEventListener("click", () => {
      if (!state.linking) return;
      if (state.linking === node.key) return;
      relationDialog(project, state.nodes.get(state.linking), node, relations, async (relation) => {
        try {
          const source = state.nodes.get(state.linking).target;
          const updated = await api.post("/projects/" + project.id + "/links", {
            source_type: source.type, source_id: source.id,
            target_type: node.target.type, target_id: node.target.id, relation,
          });
          state.links = updated;
          state.linking = null;
          drawToolbar();
          draw();
          toast("Link created.");
        } catch (error) {
          toast(error.message, "error");
        }
      });
    });
    return chip;
  }

  function drawEdgesOnly() {
    const parts = [];
    for (const link of state.links) {
      const a = state.nodes.get(link.source_type + ":" + link.source_id);
      const b = state.nodes.get(link.target_type + ":" + link.target_id);
      if (!a || !b) continue;
      parts.push('<line x1="' + a.x + '" y1="' + a.y + '" x2="' + b.x + '" y2="' + b.y
        + '" stroke="#6B6D76" stroke-opacity="0.55" stroke-width="1.4"/>');
    }
    edgeLayer.innerHTML = '<svg width="100%" height="100%" style="overflow:visible">'
      + parts.join("") + "</svg>";
  }

  const toolbar = h("div", { class: "flex items-center gap-2 mb-3 flex-wrap" });

  function drawToolbar() {
    toolbar.replaceChildren(
      h("button", { class: "btn btn-sm", onClick: () => addNodeDialog(targets, state, draw) },
        "Add object"),
      h("button", { class: "btn btn-sm" + (state.linking ? " btn-primary" : ""),
        onClick: () => {
          if (state.linking) {
            state.linking = null;
          } else {
            const first = state.nodes.keys().next().value;
            state.linking = first || null;
            if (!first) toast("Add two objects first.", "error");
          }
          drawToolbar();
        } },
        state.linking ? "Linking from “" + shortLabel(state.nodes.get(state.linking)) + "” — click a target"
                      : "Draw a relation"),
      h("button", { class: "btn btn-sm", onClick: async () => {
        try {
          const saved = await api.post("/projects/" + project.id + "/networks", {
            id: state.networkId, name: state.name,
            layout: { nodes: Array.from(state.nodes.values()).map((node) => ({
              key: node.key, x: Math.round(node.x), y: Math.round(node.y) })) },
          });
          state.networkId = saved[0].id;
          toast("Network saved.");
        } catch (error) {
          toast(error.message, "error");
        }
      } }, "Save layout"),
      h("span", { class: "text-xs text-inkfaint",
                  text: state.nodes.size + " objects · " + state.links.length + " relations" }));
  }

  function shortLabel(node) {
    if (!node) return "";
    return node.target.label.length > 22 ? node.target.label.slice(0, 20) + "…"
      : node.target.label;
  }

  const linkTable = state.links.length
    ? h("div", { class: "card overflow-x-auto mt-6" },
        h("table", { class: "row-hover" },
          h("thead", null, h("tr", null,
            h("th", { text: "From" }), h("th", { text: "Relation" }),
            h("th", { text: "To" }), h("th", null, ""))),
          h("tbody", null, ...state.links.map((link) => h("tr", null,
            h("td", { text: link.source_label }),
            h("td", { class: "text-inkfaint", text: link.relation }),
            h("td", { text: link.target_label }),
            h("td", { class: "text-right" },
              h("button", { class: "btn btn-sm btn-danger", onClick: async () => {
                await api.del("/projects/" + project.id + "/links/" + link.id);
                state.links = state.links.filter((other) => other.id !== link.id);
                draw();
                toast("Link removed.");
              } }, "Remove")))))))
    : empty("No relations yet.",
            "Add two objects, press “Draw a relation”, then click the target.");

  drawToolbar();
  draw();

  return h("div", null,
    h("p", { class: "text-sm text-inkfaint mb-3" },
      "Codes, themes, documents, quotations and memos can all be placed here and "
      + "connected with typed relations — is cause of, contradicts, is part of."),
    toolbar,
    h("div", { class: "card overflow-hidden" }, canvas),
    linkTable);
}

function addNodeDialog(targets, state, draw) {
  const search = h("input", { class: "input", placeholder: "Search codes, themes, documents…" });
  const list = h("div", { class: "coder-list", style: "max-height:18rem" });

  function options() {
    const query = search.value.trim().toLowerCase();
    const matches = targets
      .filter((target) => !state.nodes.has(target.type + ":" + target.id))
      .filter((target) => !query || target.label.toLowerCase().includes(query))
      .slice(0, 60);
    list.replaceChildren(...matches.map((target) => h("button", {
      class: "coder-option w-full", onClick: () => {
        const key = target.type + ":" + target.id;
        state.nodes.set(key, { key, target,
          x: 120 + Math.random() * 480, y: 80 + Math.random() * 280 });
        modal.remove();
        draw();
      } },
      h("span", { class: "code-swatch",
                  style: "background:" + (KIND_COLOR[target.type] || "#2B4570") }),
      h("span", { class: "flex-1", text: target.label }),
      h("span", { class: "text-xs text-inkfaint", text: target.type }))));
  }

  search.addEventListener("input", options);
  const modal = dialog("Add an object to the network", [search, list]);
  options();
  search.focus();
}

function relationDialog(project, source, target, relations, onPick) {
  const select = h("select", { class: "select" },
    ...relations.map((relation) => h("option", { value: relation }, relation)));
  const modal = dialog("Relation", [
    h("p", { class: "text-sm" },
      h("strong", { text: source.target.label }),
      h("span", { class: "text-inkfaint", text: "  →  " }),
      h("strong", { text: target.target.label })),
    field("Relation", select),
  ], [h("button", { class: "btn btn-primary", onClick: () => {
    modal.remove();
    onPick(select.value);
  } }, "Create link")]);
}

function escapeXml(text) {
  return String(text).replace(/[&<>"]/g, (character) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[character]));
}
