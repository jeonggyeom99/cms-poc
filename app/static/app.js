import { initializeDashboardApplication } from "./modules/dashboard/controller.js?v=dashboard-chat-v2";
import { initializeDashboardChat } from "./modules/chat/controller.js?v=dashboard-chat-v2";

window.addEventListener("DOMContentLoaded", () => {
  initializeDashboardChat();
  initializeDashboardApplication();
});
