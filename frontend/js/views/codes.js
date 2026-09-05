// Code manager: groundedness, density, colours, definitions, groups, merging.
// Machine-made and hand-made codes sit in one list, marked but not separated.

import { api } from "../api.js";
import { PALETTE } from "../palette.js";
import { dialog, empty, field, h, toast } from "../ui.js";

export async function codesPanel(project, refresh) {
  const [codebook, groups, suggestions] = await Promise.all([
    api.get("/projects/" + project.id + "/codebook"),
    api.get("/projects/" + project.id + "/code-groups").catch(() => []),
    api.get("/projects/" + project.id + "/codebook/suggestions").catch(() => []),
  ]);
  if (!codebook.length) {
    return empty("The codebook is empty.",
                 "Run an analysis, or code a passage by hand in the Workbench.");
  }

  const selected = new Set();
  const state = { sort: "groundedness", query: "", showAuto: true, showUser: true };
  const tableWrap = h("div", { class: "card overflow-x-auto" });
  const toolbar = h("div", { class: "flex items-end gap-3 mb-4 flex-wrap" });
  const maxGrounded = Math.max(...codebook.map((code) => code.groundedness), 1);

  async function reload() {
    const fresh = await api.get("/projects/" + project.id + "/codebook");
    codebook.length = 0;
    codebook.push(...fresh);
    draw();
    if (refresh) refresh({ silent: true });
  }

  function draw() {
    const rows = codebook
      .filter((code) => (code.created_by === "user" ? state.showUser : state.showAuto))
      .filter((code) => !state.query
        || code.name.toLowerCase().includes(state.query)
        || (code.definition || "").toLowerCase().includes(state.query))
      .sort((a, b) => {
        if (state.sort === "name") return a.name.localeCompare(b.name);
        if (state.sort === "density") return b.density - a.density;
        if (state.sort === "participants") return b.participants - a.participants;
        return b.groundedness - a.groundedness;
      });

    tableWrap.replaceChildren(h("table", { class: "row-hover" },
      h("thead", null, h("tr", null,
        h("th", null, ""),
        h("th", { text: "Code" }),
        h("th", { class: "text-right", text: "Grounded" }),
        h("th", { class: "text-right", text: "Density" }),
        h("th", { class: "text-right", text: "Cases" }),
        h("th", { text: "Groups" }),
        h("th", { text: "Source" }),
        h("th", null, ""))),
      h("tbody", null, ...rows.map((code) => codeRow(code)))));
  }

  function codeRow(code) {
    const check = h("input", { type: "checkbox", checked: selected.has(code.id),
      onChange: (event) => {
        if (event.target.checked) selected.add(code.id);
        else selected.delete(code.id);
        drawToolbar();
      } });
    const width = Math.round((code.groundedness / maxGrounded) * 100);
    return h("tr", null,
      h("td", null, check),
      h("td", null,
        h("div", { class: "flex items-center gap-2" },
          h("button", { class: "code-swatch", title: "Change colour",
            style: "background:" + code.color + ";cursor:pointer;width:.7rem;height:.7rem",
            onClick: () => colourDialog(project, code, reload) }),
          h("button", { class: "font-medium", style: "text-align:left",
            title: "Rename this code",
            onClick: () => renameDialog(project, code, reload), text: code.name })),
        code.definition
          ? h("p", { class: "text-xs text-inkfaint mt-1", text: code.definition })
          : null),
      h("td", { class: "text-right tabular", style: "min-width:6rem" },
        h("div", { class: "flex items-center gap-2 justify-end" },
          h("span", { text: String(code.groundedness) }),
          h("span", { class: "meter", style: "width:3rem" },
            h("span", { style: "width:" + width + "%;background:" + code.color })))),
      h("td", { class: "text-right tabular", text: String(code.density) }),
      h("td", { class: "text-right tabular", text: String(code.participants) }),
      h("td", { class: "text-xs text-inkfaint", text: (code.groups || []).join(", ") || "—" }),
      h("td", null, h("span", {
        class: "badge " + (code.created_by === "user" ? "badge-user" : "badge-auto"),
        text: code.created_by === "user" ? "you" : code.created_by })),
      h("td", { class: "text-right" },
        h("button", { class: "btn btn-sm", onClick: () => defineDialog(project, code, reload) },
          "Define"),
        " ",
        h("button", { class: "btn btn-sm btn-danger", onClick: async () => {
          if (!confirm("Delete “" + code.name + "” and all " + code.groundedness
                       + " of its applications?")) return;
          try {
            await api.del("/projects/" + project.id + "/codebook/" + code.id);
            toast("Code deleted.");
            await reload();
          } catch (error) {
            toast(error.message, "error");
          }
        } }, "Delete")));
  }

  function drawToolbar() {
    const search = h("input", { class: "input", placeholder: "Filter codes…",
      value: state.query });
    search.addEventListener("input", () => {
      state.query = search.value.trim().toLowerCase();
      draw();
    });
    const sort = h("select", { class: "select", onChange: (event) => {
      state.sort = event.target.value;
      draw();
    } }, ...[["groundedness", "Groundedness"], ["density", "Density"],
             ["participants", "Cases"], ["name", "Name"]]
      .map(([value, label]) => h("option", { value, selected: state.sort === value }, label)));

    toolbar.replaceChildren(
      h("div", { style: "min-width:16rem;flex:1" }, field("Filter", search)),
      h("div", null, field("Sort by", sort)),
      h("label", { class: "flex items-center gap-2 text-sm pb-2" },
        h("input", { type: "checkbox", checked: state.showAuto, onChange: (event) => {
          state.showAuto = event.target.checked;
          draw();
        } }), "Machine"),
      h("label", { class: "flex items-center gap-2 text-sm pb-2" },
        h("input", { type: "checkbox", checked: state.showUser, onChange: (event) => {
          state.showUser = event.target.checked;
          draw();
        } }), "Hand coded"),
      h("button", { class: "btn btn-sm", onClick: () => createDialog(project, reload) },
        "New code"),
      h("button", { class: "btn btn-sm", disabled: selected.size < 2, onClick: async () => {
        const ids = Array.from(selected);
        const keep = codebook.filter((code) => ids.includes(code.id))
          .sort((a, b) => b.groundedness - a.groundedness)[0];
        if (!confirm("Merge " + ids.length + " codes into “" + keep.name + "”?")) return;
        try {
          await api.post("/projects/" + project.id + "/codebook/merge",
                         { keep_id: keep.id, merge_ids: ids });
          selected.clear();
          toast("Codes merged.");
          await reload();
          drawToolbar();
        } catch (error) {
          toast(error.message, "error");
        }
      } }, "Merge selected (" + selected.size + ")"),
      h("button", { class: "btn btn-sm", disabled: selected.size < 1, onClick: () =>
        groupDialog(project, Array.from(selected), reload) }, "Group selected"));
  }

  const suggestionPanel = suggestions.length
    ? h("div", { class: "card p-5 mb-6" },
        h("h3", { class: "font-display text-lg mb-1", text: "Codes that look like duplicates" }),
        h("p", { class: "text-sm text-inkfaint mb-3" },
          "An automatic first pass always over-produces codes. These pairs share most "
          + "of their wording — merging is usually the right call, and it is reversible "
          + "only by re-running, so check first."),
        h("div", { class: "space-y-2" }, ...suggestions.slice(0, 6).map((pair) =>
          h("div", { class: "flex items-center justify-between gap-4" },
            h("span", { class: "text-sm" }, pair.a, h("span", { class: "text-inkfaint" }, "  ·  "),
              pair.b),
            h("button", { class: "btn btn-sm", onClick: async () => {
              try {
                await api.post("/projects/" + project.id + "/codebook/merge",
                               { keep_id: pair.keep_id, merge_ids: [pair.merge_id] });
                toast("Merged.");
                await reload();
              } catch (error) {
                toast(error.message, "error");
              }
            } }, "Merge")))))
    : null;

  const groupPanel = h("div", { class: "card p-5 mt-6" },
    h("h3", { class: "font-display text-lg mb-3", text: "Code groups" }),
    groups.length
      ? h("div", { class: "flex flex-wrap gap-2" }, ...groups.map((group) =>
          h("span", { class: "code-chip", style: "background:var(--ledgerlight)" },
            h("span", { text: group.name }),
            h("span", { class: "text-xs text-inkfaint",
                        text: (group.code_ids || []).length + " codes" }),
            h("button", { class: "btn-ghost", style: "padding:0 2px", onClick: async () => {
              await api.del("/projects/" + project.id + "/code-groups/" + group.id);
              toast("Group removed.");
              if (refresh) refresh();
            } }, "×"))))
      : h("p", { class: "text-sm text-inkfaint",
                 text: "No groups yet. Select codes above and group them." }));

  drawToolbar();
  draw();
  return h("div", null, suggestionPanel, toolbar, tableWrap, groupPanel);
}

// --- dialogs ---------------------------------------------------------------

function createDialog(project, reload) {
  const name = h("input", { class: "input", placeholder: "Code name" });
  const definition = h("textarea", { class: "textarea", rows: "3",
    placeholder: "When does this code apply? What is it not?" });
  const modal = dialog("New code", [
    field("Name", name),
    field("Definition", definition, "A code without a definition is a code you will "
      + "apply inconsistently."),
  ], [h("button", { class: "btn btn-primary", onClick: async () => {
    try {
      await api.post("/projects/" + project.id + "/codebook",
                     { name: name.value.trim(), definition: definition.value.trim() });
      modal.remove();
      toast("Code created.");
      await reload();
    } catch (error) {
      toast(error.message, "error");
    }
  } }, "Create")]);
}

function renameDialog(project, code, reload) {
  const name = h("input", { class: "input", value: code.name });
  const modal = dialog("Rename code", [
    field("Name", name),
    h("p", { class: "text-sm text-inkfaint",
             text: "All " + code.groundedness + " applications follow the new name." }),
  ], [h("button", { class: "btn btn-primary", onClick: async () => {
    try {
      await api.patch("/projects/" + project.id + "/codebook/" + code.id,
                      { name: name.value.trim() });
      modal.remove();
      await reload();
    } catch (error) {
      toast(error.message, "error");
    }
  } }, "Rename")]);
}

function defineDialog(project, code, reload) {
  const definition = h("textarea", { class: "textarea", rows: "5",
    value: code.definition || "" });
  const modal = dialog("Define “" + code.name + "”", [
    field("Definition", definition),
  ], [h("button", { class: "btn btn-primary", onClick: async () => {
    await api.patch("/projects/" + project.id + "/codebook/" + code.id,
                    { definition: definition.value });
    modal.remove();
    toast("Definition saved.");
    await reload();
  } }, "Save")]);
}

function colourDialog(project, code, reload) {
  const swatches = PALETTE.map((color) => h("button", {
    class: "code-swatch", style: "background:" + color + ";width:1.6rem;height:1.6rem;"
      + "cursor:pointer;border:2px solid " + (color === code.color ? "var(--ink)" : "transparent"),
    onClick: async () => {
      await api.patch("/projects/" + project.id + "/codebook/" + code.id, { color });
      modal.remove();
      await reload();
    } }));
  const modal = dialog("Colour for “" + code.name + "”",
    [h("div", { class: "flex flex-wrap gap-3" }, ...swatches)]);
}

function groupDialog(project, codeIds, reload) {
  const name = h("input", { class: "input", placeholder: "e.g. Access and waiting" });
  const modal = dialog("Group " + codeIds.length + " codes", [
    field("Group name", name),
    h("p", { class: "text-sm text-inkfaint",
             text: "Groups are for filtering and comparison; a code can be in several." }),
  ], [h("button", { class: "btn btn-primary", onClick: async () => {
    try {
      await api.post("/projects/" + project.id + "/code-groups",
                     { name: name.value.trim(), code_ids: codeIds });
      modal.remove();
      toast("Group created.");
      await reload();
    } catch (error) {
      toast(error.message, "error");
    }
  } }, "Create group")]);
}
