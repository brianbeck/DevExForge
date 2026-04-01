import { Routes, Route, Navigate } from "react-router-dom";
import Layout from "@/components/Layout";
import ProtectedRoute from "@/components/ProtectedRoute";
import TeamsListPage from "@/pages/TeamsListPage";
import TeamDetailPage from "@/pages/TeamDetailPage";
import MembersPage from "@/pages/MembersPage";
import EnvironmentsPage from "@/pages/EnvironmentsPage";
import EnvironmentDetailPage from "@/pages/EnvironmentDetailPage";
import SecurityPage from "@/pages/SecurityPage";
import MetricsPage from "@/pages/MetricsPage";
import CatalogPage from "@/pages/CatalogPage";
import AdminPage from "@/pages/AdminPage";
import AuditLogPage from "@/pages/AuditLogPage";
import "./App.css";

export default function App() {
  return (
    <ProtectedRoute>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Navigate to="/teams" replace />} />
          <Route path="/teams" element={<TeamsListPage />} />
          <Route path="/teams/:slug" element={<TeamDetailPage />}>
            <Route path="members" element={<MembersPage />} />
            <Route path="environments" element={<EnvironmentsPage />} />
            <Route
              path="environments/:tier"
              element={<EnvironmentDetailPage />}
            />
            <Route
              path="environments/:tier/security"
              element={<SecurityPage />}
            />
            <Route
              path="environments/:tier/metrics"
              element={<MetricsPage />}
            />
          </Route>
          <Route path="/teams/:slug/audit" element={<AuditLogPage />} />
          <Route path="/catalog" element={<CatalogPage />} />
          <Route path="/admin" element={<AdminPage />} />
          <Route path="/audit" element={<AuditLogPage />} />
        </Route>
      </Routes>
    </ProtectedRoute>
  );
}
