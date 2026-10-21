import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import PortfolioDemoBadge from "./PortfolioDemoBadge.jsx";
import "./styles.css";
createRoot(document.getElementById("root")).render(
  <>
    <App />
    <PortfolioDemoBadge />
  </>,
);
