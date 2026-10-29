const storageKey = "cms.sidebar.expanded";
const initializedRoots = new WeakSet();
let shellRoot;

function applySidebarState(root, expanded, notify) {
  const body = root.body;
  const toggle = root.querySelector("#cms-sidebar-toggle");
  if (!body || !toggle) return;
  const state = expanded ? "expanded" : "collapsed";
  const changed = body.dataset.cmsNav !== state;
  body.dataset.cmsNav = state;
  toggle.setAttribute("aria-expanded", String(expanded));
  const label = expanded ? "메뉴 접기" : "메뉴 펼치기";
  toggle.setAttribute("aria-label", label);
  toggle.title = label;
  if (!changed || !notify) return;
  try {
    root.defaultView.localStorage.setItem(storageKey, String(expanded));
  } catch {}
  root.dispatchEvent(new root.defaultView.CustomEvent("cms:layout-change", {
    bubbles: true, detail: { expanded },
  }));
}

export function setSidebarExpanded(expanded) {
  if (shellRoot) applySidebarState(shellRoot, Boolean(expanded), true);
}

function initDetailScroll(root) {
  if (!root.body.classList.contains("dashboard2")) return;
  const view = root.defaultView;
  view.history.scrollRestoration = "manual";
  const scrollTop = () => view.scrollTo({ top: 0, left: 0, behavior: "auto" });
  scrollTop();
  root.addEventListener("DOMContentLoaded", scrollTop, { once: true });
  view.addEventListener("load", scrollTop, { once: true });
  view.addEventListener("pageshow", scrollTop);
  for (const delay of [50, 300, 1000]) view.setTimeout(scrollTop, delay);
  root.addEventListener("change", (event) => {
    if (event.target.id === "dataset-select") view.setTimeout(scrollTop, 0);
  });
}

export function initCmsShell(root = document) {
  if (!root.body?.hasAttribute("data-cms-operations")) return;
  shellRoot = root;
  if (initializedRoots.has(root)) return;
  const toggle = root.querySelector("#cms-sidebar-toggle");
  if (!toggle) return;
  initializedRoots.add(root);
  let expanded = true;
  try {
    expanded = root.defaultView.localStorage.getItem(storageKey) !== "false";
  } catch {}
  applySidebarState(root, expanded, false);
  toggle.addEventListener("click", () => {
    setSidebarExpanded(root.body.dataset.cmsNav !== "expanded");
  });
  root.addEventListener("cms:layout-change", () => {
    root.defaultView.requestAnimationFrame(() => {
      const plotly = root.defaultView.Plotly;
      if (!plotly?.Plots?.resize) return;
      for (const plot of root.querySelectorAll(".js-plotly-plot")) {
        if (plot.data?.length && plot._fullLayout && plot.clientWidth && plot.clientHeight) {
          plotly.Plots.resize(plot);
        }
      }
    });
  });
  const headerDate = root.querySelector(".top .eyebrow, .history-kicker");
  if (headerDate) {
    headerDate.textContent = new Intl.DateTimeFormat("ko-KR", { dateStyle: "full" }).format(new Date());
  }
  initDetailScroll(root);
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => initCmsShell(), { once: true });
} else {
  initCmsShell();
}
