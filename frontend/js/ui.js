// Small DOM helpers and the shared chrome (header, badges, meters, toasts).

export function h(tag, props = {}, ...children) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(props || {})) {
    if (value === null || value === undefined || value === false) continue;
    if (key === "class") el.className = value;
    else if (key === "html") el.innerHTML = value;
    else if (key === "text") el.textContent = value;
    else if (key === "dataset") Object.assign(el.dataset, value);
    else if (key.startsWith("on") && typeof value === "function") {
      el.addEventListener(key.slice(2).toLowerCase(), value);
    } else if (key === "value") el.value = value;
    else if (key === "checked" || key === "disabled" || key === "required"
             || key === "selected" || key === "multiple") el[key] = Boolean(value);
    else el.setAttribute(key, value);
  }
  append(el, children);
  return el;
}

function append(parent, children) {
  for (const child of children.flat(4)) {
    if (child === null || child === undefined || child === false) continue;
    parent.appendChild(child instanceof Node ? child : document.createTextNode(String(child)));
  }
}

export function clear(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
  return node;
}

export function navigate(path) {
  if (path !== location.pathname) history.pushState({}, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

export function link(href, props, ...children) {
  return h("a", {
    href,
    ...props,
    onClick: (event) => {
      if (event.metaKey || event.ctrlKey || event.shiftKey) return;
      event.preventDefault();
      navigate(href);
    },
  }, ...children);
}

// --- chrome --------------------------------------------------------------

export function header(user, title, onSignOut) {
  return h("header", { class: "header" },
    h("div", { class: "max-w-7xl mx-auto px-6 h-16 flex items-center justify-between" },
      h("div", { class: "flex items-center gap-3" },
        link("/projects", { class: "flex items-center gap-2" },
          h("span", { class: "dot" }),
          h("span", { class: "font-display text-lg tracking-tight", text: "QRIP" })),
        title ? h("span", { class: "text-hairline", text: "/" }) : null,
        title ? h("span", { class: "text-sm text-inkfaint", text: title }) : null),
      user ? h("div", { class: "flex items-center gap-4" },
        link("/projects", { class: "text-sm text-inkfaint", text: "Projects" }),
        link("/reviews", { class: "text-sm text-inkfaint", text: "Review intelligence" }),
        user.role === "owner"
          ? link("/usage", { class: "text-sm text-inkfaint hover-ledger", text: "Usage & cost" })
          : null,
        h("span", { class: "text-sm text-inkfaint md-hide", text: user.email }),
        h("button", { class: "btn btn-sm", onClick: onSignOut }, "Sign out")) : null));
}

export function badge(status) {
  const label = String(status || "candidate");
  return h("span", { class: "badge badge-" + label, text: label });
}

export function meter(value, kind = "") {
  const pct = Math.max(0, Math.min(1, Number(value) || 0)) * 100;
  return h("div", { class: "meter " + kind }, h("span", { style: "width:" + pct + "%" }));
}

export function stat(label, value, accent) {
  return h("div", { class: "stat" },
    h("div", { class: "stat-value" + (accent ? " text-" + accent : ""), text: value }),
    h("div", { class: "stat-label", text: label }));
}

export function empty(message, hint) {
  return h("div", { class: "card p-6 text-center" },
    h("p", { class: "text-inkfaint text-sm", text: message }),
    hint ? h("p", { class: "text-inkfaint text-xs mt-2", text: hint }) : null);
}

export function sectionTitle(text, note) {
  return h("div", { class: "mb-3" },
    h("h2", { class: "font-display text-xl", text }),
    note ? h("p", { class: "text-sm text-inkfaint mt-1", text: note }) : null);
}

export function field(label, control, hint) {
  return h("label", { class: "field" },
    h("span", { class: "label", text: label }),
    control,
    hint ? h("span", { class: "text-xs text-inkfaint block mt-1", text: hint }) : null);
}

let toastTimer = null;
export function toast(message, kind = "") {
  document.querySelectorAll(".toast").forEach((node) => node.remove());
  const node = h("div", { class: "toast " + (kind === "error" ? "toast-error" : ""), text: message });
  document.body.appendChild(node);
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => node.remove(), 4200);
}

export function dialog(title, body, actions) {
  const backdrop = h("div", { class: "dialog-backdrop", onClick: (event) => {
    if (event.target === backdrop) backdrop.remove();
  } });
  backdrop.appendChild(h("div", { class: "dialog" },
    h("div", { class: "p-5 border-b border-hairline flex items-center justify-between" },
      h("h3", { class: "font-display text-lg", text: title }),
      h("button", { class: "btn btn-sm", onClick: () => backdrop.remove() }, "Close")),
    h("div", { class: "p-5 space-y-4" }, body),
    actions ? h("div", { class: "p-5 border-t border-hairline flex justify-end gap-2" }, actions) : null));
  document.body.appendChild(backdrop);
  return backdrop;
}

// --- formatting ----------------------------------------------------------

export function pct(value, digits = 0) {
  return (Number(value || 0) * 100).toFixed(digits) + "%";
}

export function num(value) {
  return new Intl.NumberFormat().format(Number(value || 0));
}

export function money(value) {
  return "$" + Number(value || 0).toFixed(Number(value) < 1 ? 4 : 2);
}

export function when(iso) {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString(undefined, {
    day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

export function titleCase(text) {
  return String(text || "").replace(/[_-]+/g, " ").replace(/^\w/, (c) => c.toUpperCase());
}

export function valenceColor(value) {
  const v = Number(value || 0);
  if (v <= -0.2) return "warn";
  if (v >= 0.2) return "confidence";
  return "inkfaint";
}
