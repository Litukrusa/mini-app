import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { ErrorBoundary } from "./ErrorBoundary";
import "@vkontakte/vkui/dist/vkui.css";
import "./theme.css";

const root = document.getElementById("root");
if (!root) {
  document.body.innerHTML = "<p style='padding:16px'>#root не найден</p>";
} else {
  createRoot(root).render(
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  );
}
