// Usage and cost ledger.

import { api } from "../api.js";
import { session } from "../app.js";
import { empty, h, header, money, num, stat, toast, when } from "../ui.js";

export async function usageView() {
  let summary = null;
  try {
    summary = await api.get("/usage");
  } catch (error) {
    toast(error.message, "error");
    summary = { logs: [], total_calls: 0, total_input_tokens: 0, total_output_tokens: 0,
                total_estimated_cost_usd: 0, failure_count: 0 };
  }

  const download = h("button", { class: "btn", onClick: async () => {
    download.disabled = true;
    try {
      await api.download("/usage/export/xlsx", "QRIP_usage_master.xlsx");
    } catch (error) {
      toast(error.message, "error");
    } finally {
      download.disabled = false;
    }
  } }, "Download master spreadsheet (.xlsx)");

  const rows = summary.logs.map((log) => h("tr", null,
    h("td", { class: "text-inkfaint", text: when(log.created_at) }),
    h("td", { text: log.user_name || log.user_email || "—" }),
    h("td", { text: log.project_name || "—" }),
    h("td", { text: log.operation }),
    h("td", { class: "mono", text: log.model }),
    h("td", { class: "tabular text-right", text: num(log.input_tokens) }),
    h("td", { class: "tabular text-right", text: num(log.output_tokens) }),
    h("td", { class: "tabular text-right", text: num(log.total_tokens) }),
    h("td", { class: "tabular text-right", text: money(log.estimated_cost_usd) }),
    h("td", { class: log.success ? "text-confidence" : "text-warn",
              title: log.error_message || "", text: log.success ? "ok" : "failed" })));

  return h("div", { class: "min-h-screen bg-paper" },
    header(session.user, "usage & cost", () => session.signOut()),
    h("main", { class: "max-w-7xl mx-auto px-6 py-10" },
      h("div", { class: "flex items-end justify-between mb-6" },
        h("div", null,
          h("h1", { class: "font-display text-3xl mb-1", text: "Usage & cost" }),
          h("p", { class: "text-sm text-inkfaint",
                   text: "Every analysis call, what it cost and whether it succeeded." })),
        download),
      h("div", { class: "grid grid-5 gap-3 mb-8" },
        stat("Total calls", num(summary.total_calls)),
        stat("Input tokens", num(summary.total_input_tokens)),
        stat("Output tokens", num(summary.total_output_tokens)),
        stat("Est. cost (USD)", money(summary.total_estimated_cost_usd)),
        stat("Failures", num(summary.failure_count),
             summary.failure_count > 0 ? "warn" : null)),
      summary.logs.length
        ? h("div", { class: "card overflow-x-auto" },
            h("table", null,
              h("thead", null, h("tr", null,
                h("th", { text: "When" }), h("th", { text: "User" }),
                h("th", { text: "Project" }), h("th", { text: "Operation" }),
                h("th", { text: "Model" }),
                h("th", { class: "text-right", text: "In" }),
                h("th", { class: "text-right", text: "Out" }),
                h("th", { class: "text-right", text: "Total" }),
                h("th", { class: "text-right", text: "Cost" }),
                h("th", { text: "Status" }))),
              h("tbody", null, ...rows)))
        : empty("No usage recorded yet.",
                "Run an analysis and every call will be logged here with its token cost.")));
}
