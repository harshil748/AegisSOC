import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/layout/AppShell";
import { ProtectedRoute } from "./components/layout/ProtectedRoute";
import { AlertQueuePage } from "./pages/AlertQueuePage";
import { AuditPage } from "./pages/AuditPage";
import { CaseDetailPage } from "./pages/CaseDetailPage";
import { CasesPage } from "./pages/CasesPage";
import { InvestigationWorkspacePage } from "./pages/InvestigationWorkspacePage";
import { LoginPage } from "./pages/LoginPage";
import { MetricsPage } from "./pages/MetricsPage";
import { DemoPage } from "./pages/DemoPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { ResponsePage } from "./pages/ResponsePage";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />

      <Route
        element={
          <ProtectedRoute>
            <AppShell />
          </ProtectedRoute>
        }
      >
        <Route path="/" element={<Navigate to="/alerts" replace />} />
        <Route path="/alerts" element={<AlertQueuePage />} />
        <Route path="/cases" element={<CasesPage />} />
        <Route path="/cases/:caseId" element={<CaseDetailPage />} />
        <Route path="/investigate/:caseId" element={<InvestigationWorkspacePage />} />
        <Route path="/response" element={<ResponsePage />} />
        <Route path="/audit" element={<AuditPage />} />
        <Route path="/metrics" element={<MetricsPage />} />
        <Route path="/demo" element={<DemoPage />} />
      </Route>

      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
