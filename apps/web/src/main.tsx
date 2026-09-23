import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import { App } from "./App";
import "./styles.css";

const root = document.getElementById("root");
if (!root) {
  throw new Error("#root element is missing from index.html");
}

ReactDOM.createRoot(root).render(
  <React.StrictMode>
    {/* basename keeps routing correct under the GitLab Pages project path. */}
    <BrowserRouter basename={import.meta.env.BASE_URL}>
      <App />
    </BrowserRouter>
  </React.StrictMode>,
);
