// Inter-coder agreement — but the second coder is the machine.
// Percent agreement, Cohen's kappa and Krippendorff's alpha over the quotations
// both you and the automatic pass have coded.

import { api } from "../api.js";
import { ring, stackedBar } from "../charts.js";
import { empty, h, num } from "../ui.js";

export async function agreementPanel(project) {
  const [data, comparisons] = await Promise.all([
    api.get("/projects/" + project.id + "/agreement"),
    api.get("/projects/" + project.id + "/model-comparisons").catch(() => []),
  ]);

  const machineSection = secondPassSection(comparisons);

  if (!data.comparable_quotations) {
    return h("div", { class: "space-y-6" },
      h("div", { class: "card p-6" },
        h("h3", { class: "font-display text-xl mb-2", text: "You versus the machine" }),
        h("p", { class: "text-sm text-inkfaint leading-relaxed mb-4", text: data.note }),
        h("div", { class: "grid grid-3 gap-3" },
          tile("Machine-coded quotations", num(data.auto_quotations)),
          tile("Hand-coded quotations", num(data.human_quotations)),
          tile("Coded by both", "0")),
        h("p", { class: "text-sm mt-4" },
          "To make this work: open the ",
          h("strong", { text: "Workbench" }),
          ", click a passage the machine already highlighted, and add or change its "
          + "codes. Coding the same quotation is what makes the two coders comparable.")),
      machineSection);
  }

  const alpha = data.krippendorff_alpha;
  const kappa = data.cohens_kappa;

  const disagreements = data.disagreements.length
    ? h("div", { class: "card overflow-x-auto" },
        h("table", { class: "row-hover" },
          h("thead", null, h("tr", null,
            h("th", { text: "Machine coded it" }),
            h("th", { text: "You coded it" }))),
          h("tbody", null, ...data.disagreements.map((row) => h("tr", null,
            h("td", { class: "text-inkfaint", text: row.auto.join(", ") || "—" }),
            h("td", { text: row.human.join(", ") || "—" }))))))
    : empty("No disagreements on the shared quotations.");

  return h("div", { class: "space-y-6" },
    h("div", { class: "card p-6" },
      h("h3", { class: "font-display text-xl mb-1", text: "You versus the machine" }),
      h("p", { class: "text-sm text-inkfaint mb-5",
               text: "Computed over the " + data.comparable_quotations + " quotation"
                     + (data.comparable_quotations === 1 ? "" : "s")
                     + " that carry both automatic and hand coding." }),
      h("div", { class: "grid grid-4 gap-6 items-center" },
        h("div", null,
          ring(data.exact_agreement, "exact match", "#2F6F4E"),
          h("p", { class: "text-xs text-inkfaint text-center mt-2",
                   text: "identical code sets" })),
        h("div", null,
          ring(data.partial_agreement, "any overlap", "#2B4570"),
          h("p", { class: "text-xs text-inkfaint text-center mt-2",
                   text: "at least one code shared" })),
        tile("Cohen's kappa", kappa === null ? "—" : kappa.toFixed(3),
             "chance-corrected, single label"),
        tile("Krippendorff's alpha", alpha === null ? "—" : alpha.toFixed(3),
             "nominal, the field standard")),
      h("div", { class: "mt-5" },
        stackedBar([
          { label: "Exact agreement", value: Math.round(data.exact_agreement * 100),
            color: "#2F6F4E" },
          { label: "Partial overlap", value: Math.round(
            (data.partial_agreement - data.exact_agreement) * 100), color: "#8A6D3B" },
          { label: "No overlap", value: Math.round((1 - data.partial_agreement) * 100),
            color: "#B5541B" },
        ])),
      h("p", { class: "text-sm leading-relaxed mt-4", text: data.note })),

    h("div", null,
      h("h3", { class: "font-display text-xl mb-1", text: "Where you disagree" }),
      h("p", { class: "text-sm text-inkfaint mb-3",
               text: "These are the quotations worth arguing about — and usually the "
                     + "ones that sharpen a code definition." }),
      disagreements),

    machineSection);
}

function tile(label, value, note) {
  return h("div", { class: "stat" },
    h("div", { class: "stat-value", text: String(value) }),
    h("div", { class: "stat-label", text: label }),
    note ? h("p", { class: "text-xs text-inkfaint mt-1", text: note }) : null);
}

function secondPassSection(comparisons) {
  if (!comparisons.length) {
    return empty("No second-pass check yet.", "Run an analysis first.");
  }
  const agreed = comparisons.filter((item) => item.agreement).length;
  return h("div", null,
    h("h3", { class: "font-display text-xl mb-1", text: "Theme stability" }),
    h("p", { class: "text-sm text-inkfaint mb-3",
             text: "Every theme is re-derived under a different clustering configuration. "
                   + "A theme that does not survive is a property of the parameters, not "
                   + "of the corpus." }),
    h("div", { class: "grid grid-3 gap-3 mb-4" },
      tile("Themes checked", num(comparisons.length)),
      tile("Reproduced", num(agreed)),
      tile("Unstable", num(comparisons.length - agreed))),
    h("div", { class: "card divide-y" }, ...comparisons.map((item) =>
      h("div", { class: "p-4" },
        h("div", { class: "flex items-center justify-between gap-4" },
          h("span", { class: "font-medium", text: item.theme_name || "—" }),
          h("span", { class: item.agreement ? "badge badge-confirmed" : "badge badge-rejected",
                      text: item.agreement ? "reproduced" : "unstable" })),
        h("p", { class: "text-xs text-inkfaint mt-1 mono",
                 text: item.primary_model + " vs " + item.secondary_model }),
        item.disagreement_notes
          ? h("p", { class: "text-sm mt-2", text: item.disagreement_notes }) : null))));
}
