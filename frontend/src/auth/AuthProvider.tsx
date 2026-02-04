import { useCallback, useEffect, useState, type ReactNode } from "react";
import { useNavigate } from "react-router";
import { AuthContext, type Me } from "./AuthContext";
import api, { setApiToken } from "../api/client";

export function AuthProvider({ children }: { children: ReactNode }) {
  const navigate = useNavigate();

  // Read localStorage once on initial mount
  const [token, setToken] = useState<string | null>(() => localStorage.getItem("token"));

  const [me, setMe] = useState<Me | null>(null);
  const [meLoading, setMeLoading] = useState(false);
  const [meError, setMeError] = useState<string | null>(null);

  // If token read is synchronous, we're ready immediately
  const isReady = true;

  const refreshMe = useCallback(async () => {
    if (!token) {
      setMe(null);
      setMeError(null);
      setMeLoading(false);
      return;
    }

    setMeLoading(true);
    setMeError(null);

    try {
      const res = await api.get<Me>("/me");
      setMe(res.data);
    } catch (e: unknown) {
      const maybeErr = e as { response?: { data?: { detail?: string } } };
      setMe(null);
      setMeError(maybeErr?.response?.data?.detail ?? "Failed to load user info");
    } finally {
      setMeLoading(false);
    }
  }, [token]);

  // Auto-refresh whenever token changes
  useEffect(() => {
    let cancelled = false;

    if (!token) {
      setMe(null);
      setMeError(null);
      setMeLoading(false);
      return;
    }

    void (async () => {
      setMeLoading(true);
      setMeError(null);

      try {
        const res = await api.get<Me>("/me");
        if (cancelled) return;
        setMe(res.data);
      } catch (e: unknown) {
        if (cancelled) return;
        const maybeErr = e as { response?: { data?: { detail?: string } } };
        setMe(null);
        setMeError(maybeErr?.response?.data?.detail ?? "Failed to load user info");
      } finally {
        if (!cancelled) setMeLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [token]);

  const login = useCallback(
    (t: string) => {
      localStorage.setItem("token", t);
      setApiToken(t);
      setToken(t);
      navigate("/", { replace: true });
    },
    [navigate]
  );

  const logout = useCallback(() => {
    localStorage.removeItem("token");
    setApiToken(null);
    setToken(null);
    setMe(null);
    setMeError(null);
    setMeLoading(false);
    navigate("/login", { replace: true });
  }, [navigate]);

  return (
    <AuthContext.Provider
      value={{
        token,
        isReady,
        me,
        meLoading,
        meError,
        refreshMe,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}
