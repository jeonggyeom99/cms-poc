import { initializeDashboardApplication } from "./modules/dashboard/controller.js?v=demo-related-v3";
import { initializeDashboardChat } from "./modules/chat/controller.js?v=fft-current-history-v2";

window.addEventListener("DOMContentLoaded", () => {
  initializeDashboardChat();
  initializeDashboardApplication();
});
