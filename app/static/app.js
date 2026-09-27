import { initializeDashboardApplication } from "./modules/dashboard/controller.js?v=fft-current-history-v1";
import { initializeDashboardChat } from "./modules/chat/controller.js?v=fft-current-history-v1";

window.addEventListener("DOMContentLoaded", () => {
  initializeDashboardChat();
  initializeDashboardApplication();
});
