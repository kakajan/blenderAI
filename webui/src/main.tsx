import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { postReport, reportClientLog } from "./api/client";
import "@fontsource/dm-sans/400.css";
import "@fontsource/dm-sans/500.css";
import "@fontsource/dm-sans/700.css";
import "@fontsource/instrument-serif/400.css";
import "@fontsource/vazirmatn/400.css";
import "@fontsource/vazirmatn/500.css";
import "@fontsource/vazirmatn/700.css";
import "./styles/global.css";

window.addEventListener("error", (ev) => {
  reportClientLog("error", ev.message || "window.error", {
    filename: ev.filename,
    lineno: ev.lineno,
    colno: ev.colno,
    stack: ev.error?.stack,
  });
});

window.addEventListener("unhandledrejection", (ev) => {
  const reason = ev.reason;
  const message =
    reason instanceof Error ? reason.message : String(reason || "unhandledrejection");
  const stack = reason instanceof Error ? reason.stack : undefined;
  reportClientLog("error", message, { stack, kind: "unhandledrejection" });
  void postReport({
    kind: "crash",
    summary: message,
    detail: { stack, kind: "unhandledrejection", url: window.location.href },
  }).catch(() => undefined);
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>
);
