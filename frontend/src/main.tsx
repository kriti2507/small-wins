import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { browserStorage, rememberSource } from "./lib/source";
import "./styles/style.css";

rememberSource(browserStorage(), location.search, document.referrer, location.hostname);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
