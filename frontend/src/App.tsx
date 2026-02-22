import { Routes, Route } from "react-router";
import LoginPage from "./pages/LoginPage";
import AgentPage from "./pages/AgentPage";
import TracesPage from "./pages/TracesPage";
import AdminPage from "./pages/AdminPage";
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
        <Route path="admin" element={<AdminPage />} />
      </Route>
    </Routes>
  );
}
