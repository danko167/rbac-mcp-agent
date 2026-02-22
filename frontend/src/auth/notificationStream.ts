import api from "../api/client";
import { endpoints } from "../api/endpoints";
import type { UserNotification } from "./AuthContext";

type StartNotificationStreamParams = {
  token: string;
  onReplace: (next: UserNotification[]) => void;
  onUpsert: (next: UserNotification) => void;
};

const FALLBACK_POLL_MS = 15000;
const RECONCILE_MS = 10000;
const RECONNECT_BASE_MS = 1000;
const RECONNECT_MAX_MS = 60000;

export function startNotificationStream({ token, onReplace, onUpsert }: StartNotificationStreamParams): () => void {
  let cancelled = false;
  let source: EventSource | null = null;
  let fallbackPollTimerId: number | null = null;
  let reconcileTimerId: number | null = null;
  let reconnectTimerId: number | null = null;
  let reconnectAttempt = 0;

  const loadAndSet = async () => {
    try {
      const res = await api.get<UserNotification[]>(endpoints.notifications.list, { params: { limit: 100 } });
      if (!cancelled) {
        console.info("[notifications] loadAndSet", { count: res.data.length });
        onReplace(res.data);
      }
    } catch {
      // keep current notifications on transient errors
    }
  };

  const stopFallbackPolling = () => {
    if (fallbackPollTimerId !== null) {
      window.clearInterval(fallbackPollTimerId);
      fallbackPollTimerId = null;
    }
  };

  const startFallbackPolling = () => {
    if (fallbackPollTimerId !== null) {
      return;
    }
    fallbackPollTimerId = window.setInterval(() => {
      void loadAndSet();
    }, FALLBACK_POLL_MS);
  };

  const scheduleReconnect = () => {
    if (cancelled || reconnectTimerId !== null) {
      return;
    }

    const exponential = Math.min(RECONNECT_BASE_MS * (2 ** reconnectAttempt), RECONNECT_MAX_MS);
    const jitter = Math.floor(Math.random() * 500);
    const delay = exponential + jitter;
    reconnectAttempt += 1;

    reconnectTimerId = window.setTimeout(() => {
      reconnectTimerId = null;
      connectSse();
    }, delay);
  };

  const handleVisibilityOrFocus = () => {
    if (cancelled) {
      return;
    }
    if (document.visibilityState === "visible") {
      void loadAndSet();
    }
  };

  const parseId = (value: unknown): number | null => {
    if (typeof value === "number" && Number.isFinite(value)) {
      return value;
    }
    if (typeof value === "string") {
      const parsed = Number(value);
      if (Number.isFinite(parsed)) {
        return parsed;
      }
    }
    return null;
  };

  const connectSse = () => {
    if (cancelled || typeof window === "undefined" || typeof EventSource === "undefined") {
      startFallbackPolling();
      return;
    }

    const base = (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");
    const streamUrl = `${base}${endpoints.notifications.stream}?token=${encodeURIComponent(token)}`;
    source = new EventSource(streamUrl);

    source.onopen = () => {
      console.info("[notifications] sse open", { streamUrl });
      reconnectAttempt = 0;
      stopFallbackPolling();
      void loadAndSet();
    };

    source.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as Record<string, unknown>;
        const notificationId = parseId(data.notification_id) ?? parseId(data.id);
        const eventType = typeof data.event_type === "string" ? data.event_type : "event";
        const createdAt = typeof data.created_at === "string" ? data.created_at : new Date().toISOString();
        const isRead = typeof data.is_read === "boolean" ? data.is_read : false;
        const payload = (data.payload && typeof data.payload === "object")
          ? (data.payload as Record<string, unknown>)
          : data;

        if (!notificationId) {
          console.warn("[notifications] sse payload missing notification id", data);
          void loadAndSet();
          return;
        }

        console.info("[notifications] sse message", { notificationId, eventType, createdAt });

        onUpsert({
          id: notificationId,
          event_type: eventType,
          payload,
          is_read: isRead,
          created_at: createdAt,
        });
      } catch {
        console.warn("[notifications] sse payload parse failed");
        void loadAndSet();
      }
    };

    source.onerror = () => {
      console.warn("[notifications] sse error; switching to fallback polling");
      if (source) {
        source.close();
        source = null;
      }
      startFallbackPolling();
      scheduleReconnect();
    };
  };

  void loadAndSet();
  reconcileTimerId = window.setInterval(() => {
    void loadAndSet();
  }, RECONCILE_MS);
  window.addEventListener("focus", handleVisibilityOrFocus);
  document.addEventListener("visibilitychange", handleVisibilityOrFocus);
  connectSse();

  return () => {
    cancelled = true;
    stopFallbackPolling();
    if (reconcileTimerId !== null) {
      window.clearInterval(reconcileTimerId);
    }
    if (reconnectTimerId !== null) {
      window.clearTimeout(reconnectTimerId);
    }
    window.removeEventListener("focus", handleVisibilityOrFocus);
    document.removeEventListener("visibilitychange", handleVisibilityOrFocus);
    if (source) {
      source.close();
    }
  };
}
