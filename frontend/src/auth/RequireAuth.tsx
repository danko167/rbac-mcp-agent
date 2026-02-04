import { Navigate } from "react-router";
import type { ReactNode } from "react";
import { useAuth } from "./useAuth";

export function RequireAuth({ children }: { children: ReactNode }) {
  const { token, isReady } = useAuth();

  if (!isReady) return null; // or a loader

  if (!token) return <Navigate to="/login" replace />;
  return <>{children}</>;
}
