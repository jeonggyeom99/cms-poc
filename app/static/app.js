import { initializeDashboardApplication } from "./modules/dashboard/controller.js?v=dashboard-chat-v1";
import { initializeDashboardChat } from "./modules/chat/controller.js?v=dashboard-chat-v1";

window.addEventListener("DOMContentLoaded", () => {
  initializeDashboardChat();
  initializeDashboardApplication();
});
