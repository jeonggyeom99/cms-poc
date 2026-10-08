// Give collapsed navigation the same accessible names as its expanded labels.
const navigation = document.querySelectorAll(
  "[data-cms-operations] :is(.side, .workspace-sidebar, .history2-side, .dashboard2-side) nav a",
);
const primaryNavigation = document.querySelector(
  "[data-cms-operations] :is(.side, .workspace-sidebar, .history2-side, .dashboard2-side) nav",
);
const activePath = document.body.classList.contains("dashboard2") || location.pathname === "/"
  ? "/equipment-status2" : location.pathname;
for (const link of navigation) {
  const label = link.querySelector("b, span:last-child")?.textContent.trim();
  if (label) link.setAttribute("aria-label", label);
  if (primaryNavigation?.contains(link) && link.getAttribute("href") === activePath) {
    link.classList.add("active");
    link.setAttribute("aria-current", "page");
  }
}

// Keep the shared header date current instead of displaying a fixed demo date.
const headerDate = document.querySelector(
  "[data-cms-operations] :is(.top .eyebrow, .history-kicker)",
);
if (headerDate) {
  headerDate.textContent = new Intl.DateTimeFormat("ko-KR", { dateStyle: "full" }).format(new Date());
}
