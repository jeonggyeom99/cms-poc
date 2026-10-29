import { fetchDatasetSummaries } from "../api/dashboard.js";
import { fetchHistory } from "../api/history.js";
const safe = (v) => String(v || "미지정"),
  state = (i) =>
    i.status === "caution"
      ? "attention"
      : i.status === "normal"
        ? "normal"
        : "critical";
let all = [];
function drawStatusCanvas(canvas) {
  const box = canvas.getBoundingClientRect();
  if (!box.width || !box.height) return;
  const scale = window.devicePixelRatio || 1;
  canvas.width = Math.round(box.width * scale);
  canvas.height = Math.round(box.height * scale);
  const context = canvas.getContext("2d");
  context.scale(scale, scale);
  const styles = getComputedStyle(document.documentElement);
  const values = JSON.parse(canvas.dataset.values);
  const total = values.reduce((sum, value) => sum + value, 0);
  const colors = [
    "--cms-color-normal",
    "--cms-color-caution",
    "--cms-color-danger",
  ];
  context.font = `${styles.getPropertyValue("--cms-type-chart").trim()} ${styles.getPropertyValue("--cms-font-family").trim()}`;
  context.textAlign = "center";
  context.textBaseline = "middle";
  let bottom = box.height;
  values.forEach((value, index) => {
    const height = total ? (value / total) * box.height : 0;
    bottom -= height;
    context.fillStyle = styles.getPropertyValue(colors[index]).trim();
    context.fillRect(0, bottom, box.width, height);
    if (height >= 18) {
      context.fillStyle = "#fff";
      context.fillText(String(value), box.width / 2, bottom + height / 2);
    }
  });
}
const statusCanvasObserver = new ResizeObserver((entries) => {
  entries.forEach(({ target }) => drawStatusCanvas(target));
});
function render(items, history) {
  const c = { normal: 0, attention: 0, critical: 0 };
  items.forEach((i) => c[state(i)]++);
  document.querySelector("#canvas-scope").textContent =
    items.length === all.length ? "ALL PLANTS" : "FILTERED VIEW";
  document.querySelector("#canvas-time").textContent =
    new Date().toLocaleTimeString("ko-KR", {
      hour: "2-digit",
      minute: "2-digit",
    });
  document.querySelector("#canvas-summary").textContent =
    `전체 ${items.length}개 설비 중 ${c.attention + c.critical}개가 주의 이상 상태입니다.`;
  document.querySelector("#total-count").textContent = items.length;
  document.querySelector("#risk-count").textContent = c.attention + c.critical;
  document.querySelector("#normal-rate").textContent =
    `${Math.round((c.normal / Math.max(items.length, 1)) * 100)}%`;
  const groups = new Map();
  items.forEach((i) => {
    const g = groups.get(i.plant) || { normal: 0, attention: 0, critical: 0 };
    g[state(i)]++;
    groups.set(i.plant, g);
  });
  statusCanvasObserver.disconnect();
  document.querySelector("#canvas-bars").innerHTML = [...groups.entries()]
    .map(([name, g]) => {
      return `<div class="canvas-bar"><label>${safe(name)}</label><em>${g.attention + g.critical}</em><canvas class="canvas-track" data-values='${JSON.stringify([g.normal, g.attention, g.critical])}' role="img" aria-label="정상 ${g.normal}, 주의 ${g.attention}, 심각 ${g.critical}"></canvas></div>`;
    })
    .join("");
  document.querySelectorAll("canvas.canvas-track").forEach((canvas) => {
    drawStatusCanvas(canvas);
    statusCanvasObserver.observe(canvas);
  });
  document.querySelector("#plant-list").innerHTML = [
    ...new Set(all.map((i) => i.plant).filter(Boolean)),
  ]
    .map(
      (p) =>
        `<a class="${items.some((i) => i.plant === p) ? "active" : ""}" data-plant="${safe(p)}" href="#">${safe(p)}</a>`,
    )
    .join("");
  document.querySelectorAll("[data-plant]").forEach(
    (a) =>
      (a.onclick = (e) => {
        e.preventDefault();
        render(
          all.filter((i) => i.plant === a.dataset.plant),
          history,
        );
      }),
  );
  const risk = items
    .filter((i) => ["caution", "critical"].includes(i.status))
    .slice(0, 8);
  document.querySelector("#register-count").textContent =
    `${risk.length}개 우선 대상`;
  document.querySelector("#register-body").innerHTML =
    risk
      .map(
        (i) =>
          `<a class="register-row" href="/dashboard?dataset=${i.id}"><i class="${i.status === "critical" ? "critical" : ""}"></i><strong>${safe(i.displayName || i.name)}</strong><span>${safe(i.plant)}</span><span>${safe(i.line)}</span><em>${safe(i.statusLabel)}</em></a>`,
      )
      .join("") || "<p>현재 우선 대상 없음</p>";
  document.querySelector("#canvas-history").innerHTML =
    history
      .slice(0, 7)
      .map(
        (h) =>
          `<div class="stream"><time>${safe(h.date)}</time><i></i><span><strong>${safe(h.equipmentName)}</strong><small>${safe(h.process)} · ${safe(h.faultType || h.fault || "진단 기록")}</small></span></div>`,
      )
      .join("") || "<p>최근 진단 활동 없음</p>";
}
Promise.all([fetchDatasetSummaries(), fetchHistory()]).then(([items, h]) => {
  all = items;
  render(items, h.items || []);
});
new MutationObserver(() => {
  const list = document.querySelector("#plant-list");
  if (
    list &&
    !list.querySelector("[data-plant='__all__']") &&
    list.children.length
  ) {
    const allLink = document.createElement("a");
    allLink.href = "#";
    allLink.dataset.plant = "__all__";
    allLink.textContent = "전체 공장";
    allLink.className = "active";
    allLink.onclick = (e) => {
      e.preventDefault();
      location.reload();
    };
    list.prepend(allLink);
  }
}).observe(document.body, { childList: true, subtree: true });
new MutationObserver(() => {
  const list = document.querySelector("#plant-list");
  if (!list || list.dataset.treeBuilt || !list.children.length) return;
  list.dataset.treeBuilt = "true";
  [...list.querySelectorAll("a[data-plant]")].forEach((link) => {
    if (link.dataset.plant === "__all__") return;
    const processes = [
      ...new Set(
        all
          .filter((i) => i.plant === link.dataset.plant)
          .map((i) => i.line)
          .filter(Boolean),
      ),
    ];
    const wrap = document.createElement("div");
    wrap.className = "plant-tree-node";
    link.parentNode.insertBefore(wrap, link);
    wrap.append(link);
    const children = document.createElement("div");
    children.className = "plant-tree-children";
    processes.forEach((p) => {
      const node = document.createElement("span");
      node.textContent = p;
      children.append(node);
    });
    wrap.append(children);
  });
}).observe(document.querySelector("#plant-list") || document.body, {
  childList: true,
  subtree: true,
});
new MutationObserver(() => {
  const list = document.querySelector("#plant-list");
  const allLink = list?.querySelector("[data-plant='__all__']");
  if (!list || !allLink || list.dataset.rootBuilt) return;
  const root = document.createElement("div");
  root.className = "plant-tree-root";
  const children = document.createElement("div");
  children.className = "plant-tree-root-children";
  [...list.children]
    .filter((node) => node !== allLink)
    .forEach((node) => children.append(node));
  root.append(allLink, children);
  list.replaceChildren(root);
  list.dataset.rootBuilt = "true";
}).observe(document.body, { childList: true, subtree: true });
new MutationObserver(() => {
  const list = document.querySelector("#plant-list");
  if (!list || list.dataset.cleanTree || !all.length) return;
  list.dataset.cleanTree = "true";
  const tree = document.createElement("div");
  tree.className = "clean-tree";
  const root = document.createElement("button");
  root.type = "button";
  root.className = "clean-tree-root";
  root.innerHTML = "<span>⌂</span> 전체 공장";
  root.onclick = () => location.reload();
  tree.append(root);
  const factories = [...new Set(all.map((i) => i.plant).filter(Boolean))];
  factories.forEach((factory) => {
    const details = document.createElement("details");
    details.open = true;
    const summary = document.createElement("summary");
    summary.innerHTML = `<span class="tree-caret">⌄</span><span class="tree-factory">${safe(factory)}</span>`;
    details.append(summary);
    const processWrap = document.createElement("div");
    processWrap.className = "clean-processes";
    [
      ...new Set(
        all
          .filter((i) => i.plant === factory)
          .map((i) => i.line)
          .filter(Boolean),
      ),
    ].forEach((process) => {
      const item = document.createElement("button");
      item.type = "button";
      item.textContent = process;
      item.onclick = () =>
        (location.href = `/?factory=${encodeURIComponent(factory)}`);
      processWrap.append(item);
    });
    details.append(processWrap);
    tree.append(details);
  });
  list.replaceChildren(tree);
}).observe(document.body, { childList: true, subtree: true });
new MutationObserver(() => {
  const root = document.querySelector(".clean-tree-root");
  if (!root || root.dataset.toggleBound) return;
  root.dataset.toggleBound = "true";
  root.textContent = "⌂ 전체 공장";
  root.onclick = () => {
    const nodes = [...document.querySelectorAll(".clean-tree details")];
    const shouldOpen = nodes.some((node) => !node.open);
    nodes.forEach((node) => {
      node.open = shouldOpen;
    });
  };
}).observe(document.body, { childList: true, subtree: true });
new MutationObserver(() => {
  const rail = document.querySelector(".plant-rail"),
    layout = document.querySelector(".canvas-layout");
  if (!rail || rail.dataset.collapseBound) return;
  rail.dataset.collapseBound = "true";
  const toggle = document.createElement("button");
  toggle.type = "button";
  toggle.className = "rail-toggle";
  toggle.setAttribute("aria-label", "공장 목록 숨기기");
  toggle.textContent = "‹";
  toggle.onclick = () => {
    layout.classList.toggle("rail-collapsed");
    const collapsed = layout.classList.contains("rail-collapsed");
    toggle.textContent = collapsed ? "›" : "‹";
    toggle.setAttribute(
      "aria-label",
      collapsed ? "공장 목록 펼치기" : "공장 목록 숨기기",
    );
  };
  rail.prepend(toggle);
}).observe(document.body, { childList: true, subtree: true });
window.addEventListener("DOMContentLoaded", () => {
  const meta = document.querySelector(".canvas-meta");
  if (meta && !meta.querySelector(".canvas-versions")) {
    const nav = document.createElement("nav");
    nav.className = "canvas-versions";
    nav.innerHTML =
      '<a href="/dashboard_ui1">01</a><a href="/dashboard_ui2">02</a><a href="/dashboard_ui3">03</a><a href="/dashboard_ui4">04</a><a href="/dashboard_ui5">05</a>';
    meta.prepend(nav);
  }
});
