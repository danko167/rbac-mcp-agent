import { Routes, Route } from "react-router";
import LoginPage from "./pages/LoginPage";
import AgentPage from "./pages/AgentPage";
import TracesPage from "./pages/TracesPage";
import AdminTracesPage from "./pages/AdminTracesPage";
import { RequireAuth } from "./auth/RequireAuth";
import AppLayout from "./layout/AppLayout";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />

      <Route
        element={
          <RequireAuth>
            <AppLayout />
          </RequireAuth>
        }
      >
        <Route index element={<AgentPage />} />
        <Route path="traces" element={<TracesPage />} />
        <Route path="admin/traces" element={<AdminTracesPage />} />
      </Route>
    </Routes>
  );
}
