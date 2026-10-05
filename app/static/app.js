import { initializeDashboardApplication } from "./modules/dashboard/controller.js?v=related-history-always-visible-v1";
import { initializeDashboardChat } from "./modules/chat/controller.js?v=fft-current-history-v2";

window.addEventListener("DOMContentLoaded", () => {
  initializeDashboardChat();
  initializeDashboardApplication();
});
