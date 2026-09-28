import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import VitalApp from "./VitalApp";
import "../../roller-terminal/src/styles.css";
import "./vital.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <VitalApp />
  </StrictMode>,
);
