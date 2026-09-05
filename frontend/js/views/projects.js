// Project list and creation.

import { api } from "../api.js";
import { session } from "../app.js";
import { empty, field, h, header, link, navigate, toast, when } from "../ui.js";

export const METHODOLOGIES = [
  ["thematic", "Thematic analysis"],
  ["grounded_theory", "Grounded theory"],
  ["ipa", "Interpretative phenomenological analysis"],
  ["framework", "Framework analysis"],
  ["narrative", "Narrative analysis"],
  ["content", "Content analysis"],
];

export function methodologyLabel(key) {
  const found = METHODOLOGIES.find(([value]) => value === key);
  return found ? found[1] : (key || "—");
}

function countRow(counts) {
  const pairs = [["documents", counts.documents], ["quotations", counts.quotations],
                 ["codes", counts.codes], ["themes", counts.themes]];
  const shown = pairs.filter((pair) => pair[1]);
  if (!shown.length) {
    return h("p", { class: "text-xs text-inkfaint mt-4", text: "Nothing uploaded yet." });
  }
  return h("div", { class: "flex flex-wrap gap-4 mt-4" }, ...shown.map((pair) =>
    h("div", { class: "flex items-baseline gap-1" },
      h("span", { class: "font-display text-lg", text: String(pair[1]) }),
      h("span", { class: "text-xs text-inkfaint",
                  text: pair[1] === 1 ? pair[0].replace(/s$/, "") : pair[0] }))));
}

export async function projectsView() {
  let projects = [];
  try {
    projects = await api.get("/projects");
  } catch (error) {
    toast(error.message, "error");
  }

  const listWrap = h("div", { class: "grid grid-auto gap-4" });
  const formWrap = h("div");
  let formOpen = false;

  function renderList() {
    listWrap.replaceChildren();
    if (!projects.length) {
      listWrap.appendChild(empty(
        "No projects yet.",
        "Create one, upload interview transcripts, then run an analysis."));
      return;
    }
    for (const project of projects) {
      listWrap.appendChild(link("/projects/" + project.id, { class: "card card-hover p-5 block" },
        h("h2", { class: "font-display text-lg mb-1", text: project.name }),
        h("p", { class: "text-xs uppercase tracking-wide text-inkfaint mb-3",
                 text: methodologyLabel(project.methodology) }),
        h("p", { class: "text-sm text-inkfaint line-clamp-2",
                 text: project.research_question || "No research question recorded." }),
        countRow(project.counts || {}),
        h("div", { class: "flex items-center gap-3 mt-3 text-xs text-inkfaint" },
          project.analysis_in_progress
            ? h("span", { class: "flex items-center gap-2" },
                h("span", { class: "spinner" }), "Analysis running")
            : h("span", { text: "Created " + when(project.created_at) }),
          project.last_analysis_error
            ? h("span", { class: "text-warn", text: "Last run failed" }) : null)));
    }
  }

  const toggle = h("button", { class: "btn btn-primary", onClick: () => {
    formOpen = !formOpen;
    toggle.textContent = formOpen ? "Cancel" : "New project";
    renderForm();
  } }, "New project");

  function renderForm() {
    formWrap.replaceChildren();
    if (!formOpen) return;

    const name = h("input", { class: "input", required: true,
                              placeholder: "e.g. Patient experience of referral delays" });
    const question = h("textarea", { class: "textarea", rows: "2",
      placeholder: "What are you trying to understand?" });
    const description = h("textarea", { class: "textarea", rows: "2",
      placeholder: "Sample, setting, anything a reader would need to interpret the findings." });
    const methodology = h("select", { class: "select" },
      ...METHODOLOGIES.map(([value, label]) => h("option", { value }, label)));
    const error = h("p", { class: "text-sm text-warn" });
    const submit = h("button", { class: "btn btn-primary", type: "submit" }, "Create project");

    formWrap.appendChild(h("form", { class: "card p-6 mb-8 space-y-4", onSubmit: async (event) => {
      event.preventDefault();
      error.textContent = "";
      submit.disabled = true;
      submit.textContent = "Creating…";
      try {
        const project = await api.post("/projects", {
          name: name.value.trim(),
          research_question: question.value.trim(),
          description: description.value.trim(),
          methodology: methodology.value,
        });
        navigate("/projects/" + project.id);
      } catch (err) {
        error.textContent = err.message || "Could not create project.";
        submit.disabled = false;
        submit.textContent = "Create project";
      }
    } },
      field("Project name", name),
      field("Research question", question),
      field("Primary methodology", methodology,
            "Every methodology runs on each analysis; this one leads the report."),
      field("Description", description),
      error,
      h("div", { class: "flex justify-end" }, submit)));
  }

  renderList();

  return h("div", { class: "min-h-screen bg-paper" },
    header(session.user, "projects", () => session.signOut()),
    h("main", { class: "max-w-7xl mx-auto px-6 py-10" },
      h("div", { class: "flex items-end justify-between mb-8" },
        h("div", null,
          h("h1", { class: "font-display text-3xl mb-1", text: "Projects" }),
          h("p", { class: "text-sm text-inkfaint",
                   text: "Interview corpora, coded and analysed six ways." })),
        toggle),
      formWrap,
      listWrap));
}
