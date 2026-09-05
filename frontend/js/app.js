// Router and session bootstrap.

import { api, clearToken, getToken } from "./api.js";
import { clear, navigate, toast } from "./ui.js";
import { loginView, registerView } from "./views/auth.js";
import { landingView } from "./views/landing.js";
import { projectsView } from "./views/projects.js";
import { reviewsView } from "./views/reviews.js";
import { projectView } from "./views/project.js";
import { usageView } from "./views/usage.js";

const root = document.getElementById("app");

export const session = {
  user: null,
  signOut() {
    clearToken();
    session.user = null;
    navigate("/");
  },
};

const ROUTES = [
  [/^\/$/, () => (getToken() ? navigate("/projects") : landingView())],
  [/^\/login\/?$/, () => loginView()],
  [/^\/register\/?$/, () => registerView()],
  [/^\/projects\/?$/, () => projectsView(), true],
  [/^\/projects\/([^/]+)\/?$/, (id) => projectView(id), true],
  [/^\/reviews\/?$/, () => reviewsView(), true],
  [/^\/reviews\/([^/]+)\/?$/, (id) => reviewsView(id), true],
  [/^\/usage\/?$/, () => usageView(), true],
];

async function render() {
  const path = location.pathname;
  for (const [pattern, view, requiresAuth] of ROUTES) {
    const match = path.match(pattern);
    if (!match) continue;
    if (requiresAuth && !session.user) {
      if (!getToken()) return navigate("/login");
      const ok = await loadUser();
      if (!ok) return navigate("/login");
    }
    const node = await view(...match.slice(1));
    if (node) {
      clear(root);
      root.appendChild(node);
      window.scrollTo(0, 0);
    }
    return;
  }
  navigate(getToken() ? "/projects" : "/login");
}

async function loadUser() {
  if (!getToken()) return false;
  try {
    session.user = await api.get("/auth/me");
    return true;
  } catch (error) {
    clearToken();
    session.user = null;
    if (error.status && error.status !== 401) toast(error.message, "error");
    return false;
  }
}

window.addEventListener("popstate", () => { render(); });

(async function boot() {
  await loadUser();
  render();
})();
