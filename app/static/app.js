import { initializeDashboardApplication } from "./modules/dashboard/controller.js?v=equipment-toggle-v11";
import { initializeDashboardChat } from "./modules/chat/controller.js?v=fft-current-history-v2";

window.addEventListener("DOMContentLoaded", () => {
  initializeDashboardChat();
  initializeDashboardApplication();
});
