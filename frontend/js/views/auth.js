// Sign in and account creation.

import { api, setToken } from "../api.js";
import { field, h, link, navigate, toast } from "../ui.js";

function shell(children) {
  return h("div", { class: "min-h-screen flex items-center justify-center bg-paper px-6" },
    h("div", { class: "w-full max-w-sm" },
      h("div", { class: "mb-8 text-center" },
        h("div", { class: "inline-flex items-center gap-2 mb-3" },
          h("span", { class: "dot dot-lg" }),
          h("span", { class: "font-display text-2xl", text: "QRIP" })),
        h("p", { class: "text-sm text-inkfaint",
                 text: "Qualitative Research Intelligence Platform" })),
      children));
}

function submitState(button, busy, idleLabel, busyLabel) {
  button.disabled = busy;
  button.textContent = busy ? busyLabel : idleLabel;
}

export function loginView() {
  const email = h("input", { class: "input", type: "email", required: true,
                             autocomplete: "email" });
  const password = h("input", { class: "input", type: "password", required: true,
                                autocomplete: "current-password" });
  const error = h("p", { class: "text-sm text-warn" });
  const button = h("button", { class: "btn btn-primary w-full", type: "submit" }, "Sign in");

  const form = h("form", { class: "card p-6 space-y-4", onSubmit: async (event) => {
    event.preventDefault();
    error.textContent = "";
    submitState(button, true, "Sign in", "Signing in…");
    try {
      const result = await api.post("/auth/login",
        { email: email.value.trim(), password: password.value });
      setToken(result.access_token);
      navigate("/projects");
    } catch (err) {
      error.textContent = err.message || "Something went wrong.";
    } finally {
      submitState(button, false, "Sign in", "Signing in…");
    }
  } },
    h("h1", { class: "font-display text-xl mb-1", text: "Sign in" }),
    field("Email", email),
    field("Password", password),
    error,
    button);

  return shell([
    form,
    h("p", { class: "text-sm text-inkfaint text-center mt-4" },
      "No account? ", link("/register", { class: "text-ledger" }, "Create one")),
    h("p", { class: "text-xs text-inkfaint text-center mt-6",
             text: "Demo account: demo@qrip.local / demo-password" }),
  ]);
}

export function registerView() {
  const name = h("input", { class: "input", required: true, autocomplete: "name" });
  const email = h("input", { class: "input", type: "email", required: true,
                             autocomplete: "email" });
  const password = h("input", { class: "input", type: "password", required: true,
                                minlength: "8", autocomplete: "new-password" });
  const error = h("p", { class: "text-sm text-warn" });
  const button = h("button", { class: "btn btn-primary w-full", type: "submit" },
                   "Create account");

  const form = h("form", { class: "card p-6 space-y-4", onSubmit: async (event) => {
    event.preventDefault();
    error.textContent = "";
    submitState(button, true, "Create account", "Creating…");
    try {
      const result = await api.post("/auth/register", {
        name: name.value.trim(), email: email.value.trim(), password: password.value,
      });
      setToken(result.access_token);
      toast("Welcome to QRIP.");
      navigate("/projects");
    } catch (err) {
      error.textContent = err.message || "Something went wrong.";
    } finally {
      submitState(button, false, "Create account", "Creating…");
    }
  } },
    h("h1", { class: "font-display text-xl mb-1", text: "Create account" }),
    field("Name", name),
    field("Email", email),
    field("Password", password, "At least 8 characters."),
    error,
    button);

  return shell([
    form,
    h("p", { class: "text-sm text-inkfaint text-center mt-4" },
      "Already registered? ", link("/login", { class: "text-ledger" }, "Sign in")),
  ]);
}
