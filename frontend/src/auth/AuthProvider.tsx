import { useCallback, useState, type ReactNode } from "react";
import { useNavigate } from "react-router";
import { AuthContext } from "./AuthContext";
import { setApiToken } from "../api/client";
import { useAuthUser, useNotifications } from "./hooks";

export function AuthProvider({ children }: { children: ReactNode }) {
  const navigate = useNavigate();

  // Read localStorage once on initial mount
  const [token, setToken] = useState<string | null>(() => localStorage.getItem("token"));

  const { me, meLoading, meError, timezone, refreshMe, setTimezone, clearUserState } = useAuthUser(token);
  const { notifications, unreadCount, markNotificationRead, clearNotifications } = useNotifications(token);

  // If token read is synchronous, we're ready immediately
  const isReady = true;

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
    clearUserState();
    clearNotifications();
    navigate("/login", { replace: true });
  }, [clearNotifications, clearUserState, navigate]);

  return (
    <AuthContext.Provider
      value={{
        token,
        isReady,
        me,
        meLoading,
        meError,
        timezone,
        refreshMe,
        setTimezone,
        notifications,
        unreadCount,
        markNotificationRead,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}
