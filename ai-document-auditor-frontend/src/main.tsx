import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import "./index.css";
import AppShell from "./components/AppShell.tsx";
import LandingPage from "./pages/LandingPage.tsx";
import DashboardPage from "./pages/DashboardPage.tsx";
import UploadPage from "./pages/UploadPage.tsx";
import ResultsPage from "./pages/ResultsPage.tsx";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        {/* Standalone, no sidebar -- a first-time visitor's entry point
            (e.g. from a CV/portfolio link), not a working view of the app. */}
        <Route path="/" element={<LandingPage />} />
        <Route element={<AppShell />}>
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/new" element={<UploadPage />} />
          <Route path="/audits/:jobId" element={<ResultsPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </StrictMode>
);
