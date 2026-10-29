import { initializeDashboardApplication } from "./modules/dashboard/controller.js?v=ai-paragraphs-v1";
import { initializeDashboardChat } from "./modules/chat/controller.js?v=demo-chat-v1";

window.addEventListener("DOMContentLoaded", () => {
  initializeDashboardChat();
  initializeDashboardApplication();
});
