import { useCallback, useEffect, useMemo, useState } from "react";
import api from "../api/client";
import { endpoints } from "../api/endpoints";
import type { Me, UserNotification } from "./AuthContext";
import { startNotificationStream } from "./notificationStream";

type ErrorShape = { response?: { data?: { detail?: string } } };

function getErrorDetail(error: unknown, fallback: string): string {
  const maybeError = error as ErrorShape;
  return maybeError?.response?.data?.detail ?? fallback;
}

export function useAuthUser(token: string | null) {
  const [me, setMe] = useState<Me | null>(null);
  const [meLoading, setMeLoading] = useState(false);
  const [meError, setMeError] = useState<string | null>(null);

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
      const res = await api.get<Me>(endpoints.auth.me);
      setMe(res.data);
    } catch (error: unknown) {
      setMe(null);
      setMeError(getErrorDetail(error, "Failed to load user info"));
    } finally {
      setMeLoading(false);
    }
  }, [token]);

  useEffect(() => {
    void refreshMe();
  }, [refreshMe]);

  const setTimezone = useCallback(async (nextTimezone: string) => {
    const normalized = nextTimezone.trim();
    const res = await api.put<Me>(endpoints.auth.meTimezone, { timezone: normalized });
    setMe(res.data);
    setMeError(null);
  }, []);

  const clearUserState = useCallback(() => {
    setMe(null);
    setMeError(null);
    setMeLoading(false);
  }, []);

  return {
    me,
    meLoading,
    meError,
    timezone: me?.timezone || "UTC",
    refreshMe,
    setTimezone,
    clearUserState,
  };
}

export function useNotifications(token: string | null) {
  const [notifications, setNotifications] = useState<UserNotification[]>([]);

  const fetchNotifications = useCallback(async () => {
    try {
      const res = await api.get<UserNotification[]>(endpoints.notifications.list, { params: { limit: 100 } });
      setNotifications(res.data);
    } catch {
      setNotifications([]);
    }
  }, []);

  useEffect(() => {
    if (!token) {
      setNotifications([]);
      return;
    }

    const stop = startNotificationStream({
      token,
      onReplace: (next) => setNotifications(next),
      onUpsert: (next) => {
        setNotifications((prev) => {
          const existing = prev.find((n) => n.id === next.id);
          if (existing) {
            const isSameEvent =
              existing.created_at === next.created_at
              && existing.event_type === next.event_type
              && existing.is_read === next.is_read;
            if (isSameEvent) {
              return prev;
            }

            const withoutOld = prev.filter((n) => n.id !== next.id);
            return [next, ...withoutOld].slice(0, 100);
          }
          return [next, ...prev].slice(0, 100);
        });
      },
    });

    return stop;
  }, [token]);

  const markNotificationRead = useCallback(async (id: number) => {
    await api.post(endpoints.notifications.readById(id));
    setNotifications((prev) => prev.map((n) => (n.id === id ? { ...n, is_read: true } : n)));
  }, []);

  const unreadCount = useMemo(
    () => notifications.reduce((sum, notification) => (notification.is_read ? sum : sum + 1), 0),
    [notifications],
  );

  return {
    notifications,
    unreadCount,
    markNotificationRead,
    refreshNotifications: fetchNotifications,
    clearNotifications: () => setNotifications([]),
  };
}
