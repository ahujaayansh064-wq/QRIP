// Analytic memos, attachable to any object in the project.

import { api } from "../api.js";
import { empty, field, h, toast, when } from "../ui.js";

const KINDS = [
  ["analytic", "Analytic"],
  ["method", "Method"],
  ["reflexive", "Reflexive"],
  ["theoretical", "Theoretical"],
  ["todo", "To do"],
];

export async function memosPanel(project) {
  const [memos, targetData] = await Promise.all([
    api.get("/projects/" + project.id + "/memos"),
    api.get("/projects/" + project.id + "/link-targets"),
  ]);
  const byKey = new Map(targetData.targets.map((t) => [t.type + ":" + t.id, t]));

  const list = h("div", { class: "space-y-3" });
  const editorSlot = h("div");
  let current = null;

  async function reload() {
    const fresh = await api.get("/projects/" + project.id + "/memos");
    memos.length = 0;
    memos.push(...fresh);
    drawList();
  }

  function drawList() {
    if (!memos.length) {
      list.replaceChildren(empty("No memos yet.",
        "A memo is where the thinking goes that is not a code: hunches, decisions, "
        + "questions for the next interview."));
      return;
    }
    list.replaceChildren(...memos.map((memo) => h("div", {
      class: "card p-4 card-hover", onClick: () => open(memo) },
      h("div", { class: "flex items-center justify-between gap-3 mb-1" },
        h("h3", { class: "font-display text-lg", text: memo.title }),
        h("span", { class: "badge badge-review", text: memo.kind })),
      h("p", { class: "text-sm text-inkfaint line-clamp-3", text: memo.body || "Empty." }),
      h("div", { class: "flex items-center gap-3 mt-2 text-xs text-inkfaint" },
        h("span", { text: "updated " + when(memo.updated_at) }),
        memo.links.length
          ? h("span", { text: memo.links.length + " linked object(s)" }) : null))));
  }

  function open(memo) {
    current = memo;
    const title = h("input", { class: "input", value: memo ? memo.title : "" });
    const body = h("textarea", { class: "textarea", rows: "12",
      value: memo ? memo.body : "", placeholder: "What are you noticing, and why does it matter?" });
    const kind = h("select", { class: "select" }, ...KINDS.map(([value, label]) =>
      h("option", { value, selected: memo && memo.kind === value }, label)));

    const linked = new Set((memo ? memo.links : []).map((link) => link.type + ":" + link.id));
    const linkPicker = h("select", { class: "select" },
      h("option", { value: "" }, "Attach to an object…"),
      ...targetData.targets.slice(0, 250).map((target) =>
        h("option", { value: target.type + ":" + target.id },
          target.type + " · " + target.label.slice(0, 60))));
    const linkList = h("div", { class: "flex flex-wrap gap-2" });

    function drawLinks() {
      linkList.replaceChildren(...Array.from(linked).map((key) => {
        const target = byKey.get(key);
        return h("span", { class: "code-chip", style: "background:var(--ledgerlight)" },
          h("span", { text: target ? target.label.slice(0, 40) : key }),
          h("button", { class: "btn-ghost", style: "padding:0 2px", onClick: () => {
            linked.delete(key);
            drawLinks();
          } }, "×"));
      }));
    }
    linkPicker.addEventListener("change", () => {
      if (linkPicker.value) {
        linked.add(linkPicker.value);
        linkPicker.value = "";
        drawLinks();
      }
    });
    drawLinks();

    async function save() {
      const payload = {
        title: title.value.trim(), body: body.value, kind: kind.value,
        links: Array.from(linked).map((key) => {
          const [type, id] = key.split(":");
          return { type, id };
        }),
      };
      if (!payload.title) {
        toast("A memo needs a title.", "error");
        return;
      }
      try {
        if (memo) {
          await api.patch("/projects/" + project.id + "/memos/" + memo.id, payload);
        } else {
          await api.post("/projects/" + project.id + "/memos", payload);
        }
        toast("Memo saved.");
        editorSlot.replaceChildren();
        current = null;
        await reload();
      } catch (error) {
        toast(error.message, "error");
      }
    }

    editorSlot.replaceChildren(h("div", { class: "card p-5 mb-6" },
      h("div", { class: "flex items-center justify-between mb-4" },
        h("h3", { class: "font-display text-xl", text: memo ? "Edit memo" : "New memo" }),
        h("div", { class: "flex gap-2" },
          memo ? h("button", { class: "btn btn-sm btn-danger", onClick: async () => {
            if (!confirm("Delete this memo?")) return;
            await api.del("/projects/" + project.id + "/memos/" + memo.id);
            editorSlot.replaceChildren();
            toast("Memo deleted.");
            await reload();
          } }, "Delete") : null,
          h("button", { class: "btn btn-sm", onClick: () => {
            editorSlot.replaceChildren();
            current = null;
          } }, "Cancel"),
          h("button", { class: "btn btn-sm btn-primary", onClick: save }, "Save memo"))),
      h("div", { class: "grid grid-2 gap-4 mb-4" },
        field("Title", title),
        field("Kind", kind)),
      field("Memo", body),
      h("div", { class: "mt-4" },
        h("span", { class: "label", text: "Attached to" }),
        linkList,
        h("div", { class: "mt-2" }, linkPicker))));
    editorSlot.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  drawList();

  return h("div", null,
    h("div", { class: "flex items-center justify-between mb-4" },
      h("p", { class: "text-sm text-inkfaint",
               text: "Memos are part of the audit trail: they record why the analysis "
                     + "went the way it did." }),
      h("button", { class: "btn btn-primary btn-sm", onClick: () => open(null) }, "New memo")),
    editorSlot,
    list);
}
