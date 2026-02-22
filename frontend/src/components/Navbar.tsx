import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router";
import {
  ActionIcon,
  Badge,
  Box,
  Button,
  Group,
  Menu,
  ScrollArea,
  Stack,
  Text,
  Tooltip,
  Divider,
  SimpleGrid
} from "@mantine/core";
import {
  IconBell,
  IconCheckupList,
  IconChevronDown,
  IconDoorExit,
  IconHome,
  IconInfoCircle,
  IconMessage2Check,
  IconMessageCircle,
  IconMessagePlus,
  IconShieldCog,
  IconTrash,
  IconUser,
} from "@tabler/icons-react";
import api from "../api/client";
import { endpoints } from "../api/endpoints";
import {
  createConversation,
  deleteConversation,
  fetchConversations,
  openApprovalsConversation,
  type ConversationListItem,
} from "../api/conversations";
import { useAuth } from "../auth/useAuth";
import type { TokenUsageSummary } from "../auth/AuthContext";
import NotificationsModal from "./modals/NotificationsModal";
import AlarmModal from "./modals/AlarmModal";

type PendingNotice = {
  type: "approval_request_created" | "permission_request_result";
  notificationKey: string;
  noticeValue: string;
};

const tealMenuStyles = {
  dropdown: {
    backgroundColor: "var(--mantine-color-teal-7)",
    borderColor: "rgba(255, 255, 255, 0.18)",
    borderRadius: "var(--mantine-radius-md)",
  },
  label: {
    color: "white",
  },
  item: {
    color: "white",
    borderRadius: "var(--mantine-radius-md)",
    "&:hover": {
      backgroundColor: "var(--mantine-color-teal-6) !important",
    },
    "&[data-hovered]": {
      backgroundColor: "var(--mantine-color-teal-6) !important",
    },
    "&[data-active]": {
      backgroundColor: "var(--mantine-color-teal-5) !important",
    },
  },
  divider: {
    borderColor: "rgba(255, 255, 255, 0.25)",
  },
} as const;

function UsageTooltipLabel({ usage }: { usage: TokenUsageSummary }) {
  return (
    <Stack gap={2}>
      <Text size="xs" c="white">
        Total: {usage.all_total_tokens}
      </Text>
      <Text size="xs" c="white">
        LLM in/out: {usage.llm_input_tokens}/{usage.llm_output_tokens}
      </Text>
      <Text size="xs" c="white">
        STT in/out: {usage.stt_input_tokens}/{usage.stt_output_tokens}
      </Text>
    </Stack>
  );
}

function UserBadgeSection() {
  const navigate = useNavigate();
  const location = useLocation();
  const {
    me,
    logout,
    meLoading,
    meError,
    timezone,
    notifications,
    unreadCount,
    markNotificationRead,
  } = useAuth();

  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [alarmOpen, setAlarmOpen] = useState(false);
  const [activeAlarmId, setActiveAlarmId] = useState<number | null>(null);
  const [alarmSoundReady, setAlarmSoundReady] = useState(false);
  const [audioError, setAudioError] = useState<string | null>(null);
  const [decisionBusy, setDecisionBusy] = useState<Set<number>>(new Set());
  const [decisionError, setDecisionError] = useState<string | null>(null);
  const [localDecisions, setLocalDecisions] = useState<
    Record<number, "approved" | "rejected">
  >({});

  const [conversations, setConversations] = useState<ConversationListItem[]>([]);
  const [conversationsOpen, setConversationsOpen] = useState(false);
  const [conversationBusy, setConversationBusy] = useState(false);
  const [hoveredConversationKey, setHoveredConversationKey] = useState<string | null>(null);
  const [deletingConversationId, setDeletingConversationId] = useState<number | null>(null);
  const [pendingNotices, setPendingNotices] = useState<PendingNotice[]>([]);

  const alarmAudioRef = useRef<HTMLAudioElement | null>(null);
  const handledAlarmIdRef = useRef<number | null>(null);
  const handledApprovalNotificationKeysRef = useRef<Set<string>>(new Set());
  const handledPermissionResultNotificationKeysRef = useRef<Set<string>>(new Set());
  const processingPendingNoticeRef = useRef(false);

  const isAgentInteractionBusy = useCallback((): boolean => {
    try {
      return sessionStorage.getItem("agent:interaction_busy") === "1";
    } catch {
      return false;
    }
  }, []);

  const getNotificationKey = useCallback(
    (notification: { id: number; event_type: string; created_at: string }): string =>
      `${notification.event_type}:${notification.id}:${notification.created_at}`,
    [],
  );

  const getNoticeValue = useCallback(
    (type: PendingNotice["type"], notification: { id: number; created_at: string }): string =>
      `${type}:${notification.id}:${notification.created_at}`,
    [],
  );

  const isAdminApprover = me?.permissions.includes("permissions:approve") ?? false;

  const canAutoRouteToApprovals = useCallback(
    (notification: { payload: Record<string, unknown> }): boolean => {
      if (isAdminApprover) {
        return true;
      }

      const targetUserId = notification.payload.target_user_id;
      const requestKind = notification.payload.request_kind;
      return (
        requestKind === "delegation" &&
        typeof targetUserId === "number" &&
        targetUserId === me?.id
      );
    },
    [isAdminApprover, me?.id],
  );

  const activeAlarm = useMemo(() => {
    if (activeAlarmId == null) return null;
    return notifications.find((n) => n.id === activeAlarmId) ?? null;
  }, [activeAlarmId, notifications]);

  const stopAlarmSound = useCallback(() => {
    if (!alarmAudioRef.current) return;
    alarmAudioRef.current.pause();
    alarmAudioRef.current.currentTime = 0;
  }, []);

  const primeAlarmSound = useCallback(async () => {
    const src = "/alarm1.wav";
    if (!alarmAudioRef.current) {
      alarmAudioRef.current = new Audio(src);
      alarmAudioRef.current.loop = true;
    }
    alarmAudioRef.current.src = src;
    try {
      await alarmAudioRef.current.play();
      alarmAudioRef.current.pause();
      alarmAudioRef.current.currentTime = 0;
      setAlarmSoundReady(true);
      setAudioError(null);
    } catch {
      setAlarmSoundReady(false);
    }
  }, []);

  const playAlarmSound = useCallback(async () => {
    const src = "/alarm1.wav";

    if (!alarmAudioRef.current) {
      alarmAudioRef.current = new Audio(src);
      alarmAudioRef.current.loop = true;
    }

    alarmAudioRef.current.src = src;
    alarmAudioRef.current.currentTime = 0;
    setAudioError(null);
    try {
      await alarmAudioRef.current.play();
    } catch {
      setAudioError("Could not autoplay alarm sound. Press Play to start it.");
    }
  }, []);

  const openConversation = useCallback(
    (conversationId: number, extraParams?: Record<string, string>) => {
      const params = new URLSearchParams();
      params.set("conversation", String(conversationId));
      if (extraParams) {
        Object.entries(extraParams).forEach(([key, value]) => {
          if (value) params.set(key, value);
        });
      }
      navigate({ pathname: "/", search: params.toString() });
      setConversationsOpen(false);
    },
    [navigate],
  );

  const processPendingNotice = useCallback(
    async (notice: PendingNotice) => {
      if (notice.type === "approval_request_created") {
        const conversation = await openApprovalsConversation();
        handledApprovalNotificationKeysRef.current.add(notice.notificationKey);
        openConversation(conversation.id, { notice: notice.noticeValue });
        return;
      }

      const activeConversationIdRaw = new URLSearchParams(location.search).get("conversation");
      const activeConversationId = activeConversationIdRaw ? Number(activeConversationIdRaw) : NaN;

      const conversationId =
        location.pathname === "/" && Number.isFinite(activeConversationId) && activeConversationId > 0
          ? activeConversationId
          : (await createConversation("default")).id;

      handledPermissionResultNotificationKeysRef.current.add(notice.notificationKey);
      openConversation(conversationId, { notice: notice.noticeValue });
    },
    [location.pathname, location.search, openConversation],
  );

  const decidePermissionRequest = useCallback(
    async (notificationId: number, requestId: number, decision: "approve" | "reject") => {
      setDecisionError(null);
      setDecisionBusy((prev) => {
        const next = new Set(prev);
        next.add(notificationId);
        return next;
      });

      try {
        const url =
          decision === "approve"
            ? endpoints.admin.approvePermissionRequest(requestId)
            : endpoints.admin.rejectPermissionRequest(requestId);

        await api.post(url, { reason: null });
        setLocalDecisions((prev) => ({
          ...prev,
          [requestId]: decision === "approve" ? "approved" : "rejected",
        }));

        try {
          await markNotificationRead(notificationId);
        } catch {
          // Ignore: marking read is best-effort; decision already persisted server-side.
        }
      } catch (e: unknown) {
        const maybeErr = e as { response?: { data?: { detail?: string } } };
        setDecisionError(maybeErr?.response?.data?.detail ?? `Failed to ${decision} request`);
      } finally {
        setDecisionBusy((prev) => {
          const next = new Set(prev);
          next.delete(notificationId);
          return next;
        });
      }
    },
    [markNotificationRead],
  );

  const openApprovalsAssistant = useCallback(async () => {
    if (conversationBusy) return;

    setConversationBusy(true);
    try {
      const conversation = await openApprovalsConversation();
      openConversation(conversation.id);
    } finally {
      setConversationBusy(false);
    }
  }, [conversationBusy, openConversation]);

  const startConversation = useCallback(async () => {
    if (conversationBusy) return;

    setConversationBusy(true);
    try {
      const created = await createConversation();
      openConversation(created.id);
    } finally {
      setConversationBusy(false);
    }
  }, [conversationBusy, openConversation]);

  const removeConversation = useCallback(
    async (conversationId: number) => {
      if (deletingConversationId === conversationId) return;

      setDeletingConversationId(conversationId);
      try {
        await deleteConversation(conversationId);

        setConversations((prev) => prev.filter((c) => c.id !== conversationId));

        const params = new URLSearchParams(location.search);
        const activeConversationId = params.get("conversation");
        if (activeConversationId === String(conversationId)) {
          params.delete("conversation");
          navigate({ pathname: "/", search: params.toString() }, { replace: true });
        }
      } finally {
        setDeletingConversationId(null);
      }
    },
    [deletingConversationId, location.search, navigate],
  );

  useEffect(() => {
    if (alarmSoundReady) return;

    const onFirstInteraction = () => {
      void primeAlarmSound();
      window.removeEventListener("pointerdown", onFirstInteraction);
      window.removeEventListener("keydown", onFirstInteraction);
    };

    window.addEventListener("pointerdown", onFirstInteraction, { once: true });
    window.addEventListener("keydown", onFirstInteraction, { once: true });

    return () => {
      window.removeEventListener("pointerdown", onFirstInteraction);
      window.removeEventListener("keydown", onFirstInteraction);
    };
  }, [alarmSoundReady, primeAlarmSound]);

  useEffect(() => {
    const unreadAlarm = notifications.find(
      (notification) => !notification.is_read && notification.event_type === "alarm.fired",
    );
    if (!unreadAlarm) return;
    if (handledAlarmIdRef.current === unreadAlarm.id) return;

    handledAlarmIdRef.current = unreadAlarm.id;
    setActiveAlarmId(unreadAlarm.id);
    setAlarmOpen(true);
    void playAlarmSound();
  }, [notifications, playAlarmSound]);

  useEffect(() => {
    if (!me || conversationBusy) return;

    const actionableRequest = notifications.find(
      (notification) =>
        !notification.is_read &&
        notification.event_type === "permission.request.created" &&
        !handledApprovalNotificationKeysRef.current.has(getNotificationKey(notification)) &&
        canAutoRouteToApprovals(notification),
    );

    if (!actionableRequest) return;

    const notificationKey = getNotificationKey(actionableRequest);
    const pendingNotice: PendingNotice = {
      type: "approval_request_created",
      notificationKey,
      noticeValue: getNoticeValue("approval_request_created", actionableRequest),
    };

    setPendingNotices((prev) =>
      prev.some((notice) => notice.notificationKey === notificationKey) ? prev : [...prev, pendingNotice],
    );
  }, [
    conversationBusy,
    me,
    notifications,
    canAutoRouteToApprovals,
    getNotificationKey,
    getNoticeValue,
  ]);

  useEffect(() => {
    if (!me || conversationBusy) return;

    const resultNotification = notifications.find(
      (notification) =>
        !notification.is_read &&
        !handledPermissionResultNotificationKeysRef.current.has(getNotificationKey(notification)) &&
        (notification.event_type === "permission.request.approved" ||
          notification.event_type === "permission.request.rejected"),
    );

    if (!resultNotification) return;

    const notificationKey = getNotificationKey(resultNotification);
    const pendingNotice: PendingNotice = {
      type: "permission_request_result",
      notificationKey,
      noticeValue: getNoticeValue("permission_request_result", resultNotification),
    };

    setPendingNotices((prev) =>
      prev.some((notice) => notice.notificationKey === notificationKey) ? prev : [...prev, pendingNotice],
    );
  }, [
    conversationBusy,
    location.pathname,
    location.search,
    me,
    notifications,
    getNotificationKey,
    getNoticeValue,
  ]);

  useEffect(() => {
    if (!me || conversationBusy || processingPendingNoticeRef.current) return;
    if (isAgentInteractionBusy()) return;
    if (pendingNotices.length === 0) return;

    const [nextNotice] = pendingNotices;
    setPendingNotices((prev) => prev.slice(1));

    let cancelled = false;
    processingPendingNoticeRef.current = true;

    void (async () => {
      try {
        await processPendingNotice(nextNotice);
      } catch {
        if (!cancelled) {
          setPendingNotices((prev) => [nextNotice, ...prev]);
        }
      } finally {
        processingPendingNoticeRef.current = false;
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [
    conversationBusy,
    me,
    pendingNotices,
    location.pathname,
    location.search,
    isAgentInteractionBusy,
    processPendingNotice,
  ]);

  useEffect(() => {
    const onInteractionBusyChanged = () => {
      // Force re-render so the "queue processor" effect re-evaluates.
      setPendingNotices((prev) => [...prev]);
    };

    window.addEventListener(
      "agent:interaction_busy_changed",
      onInteractionBusyChanged as EventListener,
    );
    return () => {
      window.removeEventListener(
        "agent:interaction_busy_changed",
        onInteractionBusyChanged as EventListener,
      );
    };
  }, []);

  useEffect(() => {
    return () => {
      stopAlarmSound();
    };
  }, [stopAlarmSound]);

  useEffect(() => {
    if (!conversationsOpen) return;

    let cancelled = false;
    void (async () => {
      setConversationBusy(true);
      try {
        const data = await fetchConversations();
        if (!cancelled) {
          setConversations(data);
        }
      } finally {
        if (!cancelled) {
          setConversationBusy(false);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [conversationsOpen]);

  if (meLoading) {
    return (
      <Text size="sm" c="dimmed">
        Loading…
      </Text>
    );
  }

  if (meError) {
    return (
      <Text size="sm" c="red">
        {meError}
      </Text>
    );
  }

  if (!me) {
    return null;
  }

  return (
    <>
      <Group gap="xs" wrap="nowrap" align="center" justify="flex-end">
        <Menu
          opened={conversationsOpen}
          onChange={setConversationsOpen}
          position="bottom-end"
          width={320}
          withinPortal
          withArrow
          arrowSize={10}
          styles={tealMenuStyles}
        >
          <Menu.Target>
            <Button
              variant="subtle"
              size="xs"
              color="teal"
              radius="md"
              leftSection={<IconMessageCircle size={18} />}
              rightSection={<IconChevronDown size={14} />}
              px={4}
            >
              Chats
            </Button>
          </Menu.Target>

          <Menu.Dropdown bg="teal.7">
            <Menu.Label c="white">Conversations</Menu.Label>
            <Menu.Item
              leftSection={<IconMessagePlus size={16} />}
              onClick={() => {
                void startConversation();
              }}
              disabled={conversationBusy}
              onMouseEnter={() => setHoveredConversationKey("new")}
              onMouseLeave={() => setHoveredConversationKey(null)}
              style={{
                borderRadius: "var(--mantine-radius-md)",
                color: "white",
                backgroundColor:
                  hoveredConversationKey === "new"
                    ? "var(--mantine-color-teal-6)"
                    : "transparent",
              }}
            >
              <Text size="sm" c="white">
                New conversation
              </Text>
            </Menu.Item>
            <Menu.Item
              leftSection={<IconMessage2Check size={16} />}
              onClick={() => {
                void openApprovalsAssistant();
              }}
              disabled={conversationBusy}
              onMouseEnter={() => setHoveredConversationKey("approvals")}
              onMouseLeave={() => setHoveredConversationKey(null)}
              style={{
                borderRadius: "var(--mantine-radius-md)",
                color: "white",
                backgroundColor:
                  hoveredConversationKey === "approvals"
                    ? "var(--mantine-color-teal-6)"
                    : "transparent",
              }}
            >
              <Text size="sm" c="white">
                Approvals assistant
              </Text>
            </Menu.Item>
            <Menu.Divider />
            <ScrollArea.Autosize mah={280} type="auto">
              {conversations.length === 0 ? (
                <Text size="sm" c="white" px="sm" py="xs">
                  {conversationBusy ? "Loading conversations..." : "No conversations yet"}
                </Text>
              ) : (
                conversations.map((conversation) => {
                  const params = new URLSearchParams(location.search);
                  const activeConversationId = params.get("conversation");
                  const isActive =
                    activeConversationId === String(conversation.id) && location.pathname === "/";

                  return (
                    <Menu.Item
                      key={conversation.id}
                      onClick={() => openConversation(conversation.id)}
                      onMouseEnter={() => setHoveredConversationKey(String(conversation.id))}
                      onMouseLeave={() => setHoveredConversationKey(null)}
                      style={{
                        borderRadius: "var(--mantine-radius-md)",
                        color: "white",
                        backgroundColor: isActive
                          ? "var(--mantine-color-teal-5)"
                          : hoveredConversationKey === String(conversation.id)
                            ? "var(--mantine-color-teal-6)"
                            : "transparent",
                      }}
                    >
                      <Group justify="space-between" wrap="nowrap" gap="xs">
                        <Text size="sm" c="white" truncate>
                          {conversation.kind === "approvals"
                            ? "Approvals assistant"
                            : conversation.title}
                        </Text>
                        <Group gap={10} wrap="nowrap">
                          <Text size="xs" c="white">
                            {conversation.run_count}
                          </Text>
                          <Tooltip
                            multiline
                            withArrow
                            label={
                              <Box px={4} py={2}>
                                <UsageTooltipLabel usage={conversation.token_usage} />
                              </Box>
                            }
                            w={220}
                          >
                            <ActionIcon
                              variant="subtle"
                              color="white"
                              size="sm"
                              radius="md"
                              onMouseDown={(event) => {
                                event.preventDefault();
                                event.stopPropagation();
                              }}
                            >
                              <IconInfoCircle size={16} />
                            </ActionIcon>
                          </Tooltip>
                          {conversation.kind !== "approvals" ? (
                            <ActionIcon
                              variant="subtle"
                              color="white"
                              size="sm"
                              radius="md"
                              loading={deletingConversationId === conversation.id}
                              aria-label="Delete conversation"
                              onMouseDown={(event) => {
                                event.preventDefault();
                                event.stopPropagation();
                              }}
                              onClick={(event) => {
                                event.preventDefault();
                                event.stopPropagation();
                                void removeConversation(conversation.id);
                              }}
                            >
                              <IconTrash size={16} />
                            </ActionIcon>
                          ) : null}
                        </Group>
                      </Group>
                    </Menu.Item>
                  );
                })
              )}
            </ScrollArea.Autosize>
          </Menu.Dropdown>
        </Menu>

        <Button
          variant={unreadCount > 0 ? "outline" : "subtle"}
          size="xs"
          radius={unreadCount > 0 ? "xl" : "md"}
          color={unreadCount > 0 ? "orange" : "teal"}
          leftSection={<IconBell size={18} />}
          onClick={() => setNotificationsOpen(true)}
          px={4}
        >
          <span style={{ marginRight: unreadCount > 0 ? "5px" : "0" }}>{unreadCount}</span>
        </Button>

        <Menu
          position="bottom-end"
          width={280}
          offset={8}
          withinPortal
          withArrow
          arrowSize={10}
          styles={tealMenuStyles}
        >
          <Menu.Target>
            <Button
              size="xs"
              color="teal"
              variant="subtle"
              radius="md"
              px={4}
              rightSection={<IconChevronDown size={14} />}
              aria-label="Account menu"
            >
              <IconUser size={18} />
            </Button>
          </Menu.Target>

          <Menu.Dropdown bg="teal.7">
            <Menu.Label c="white">Account</Menu.Label>

            <Menu.Item
              disabled
              style={{
                borderRadius: "var(--mantine-radius-md)",
                opacity: 1,
                cursor: "default",
              }}
            >
              <Text size="sm" c="white" truncate ff="monospace">
                {me.email}
              </Text>
            </Menu.Item>

            <Menu.Item
              disabled
              style={{
                borderRadius: "var(--mantine-radius-md)",
                opacity: 1,
                cursor: "default",
              }}
            >
              <Group gap="xs" wrap="nowrap" justify="space-between">
                <Text size="sm" c="white">
                  Role:
                </Text>
                <Box
                  style={{
                    backgroundColor: "white",
                    borderRadius: "var(--mantine-radius-md)",
                    padding: "3px 20px",
                    display: "inline-flex",
                  }}
                >
                  <Badge
                    variant="outline"
                    color={
                      me.roles?.includes("admin")
                        ? "red"
                        : me.roles?.includes("pro")
                          ? "violet"
                          : "orange"
                    }
                  >
                    {me.roles?.length ? me.roles.join(", ") : "basic"}
                  </Badge>
                </Box>
              </Group>
            </Menu.Item>

            <Menu.Item
              disabled
              style={{
                borderRadius: "var(--mantine-radius-md)",
                opacity: 1,
                cursor: "default",
              }}
            >
              <Box
                style={{
                  background: "rgba(255, 255, 255, 0.10)",
                  border: "1px solid rgba(255, 255, 255, 0.18)",
                  borderRadius: "var(--mantine-radius-md)",
                  padding: "6px 8px",
                }}
              >
                <Stack gap={6}>
                  {/* Header */}
                  <Group justify="space-between" align="baseline" wrap="nowrap">
                    <Text size="xs" c="rgba(255,255,255,0.85)" fw={600}>
                      Token usage
                    </Text>
                    <Text
                      size="sm"
                      c="white"
                      fw={700}
                      ff="monospace"
                      style={{ fontVariantNumeric: "tabular-nums" }}
                    >
                      {me.token_usage.all_total_tokens}
                    </Text>
                  </Group>

                  <Divider color="rgba(255,255,255,0.22)" />

                  <SimpleGrid cols={4} spacing="xs" verticalSpacing={6}>
                    {/* Column headers */}
                    <Text size="xs" c="rgba(255,255,255,0.70)" fw={600}>
                      Type
                    </Text>
                    <Text size="xs" c="rgba(255,255,255,0.70)" fw={600} ta="right">
                      In
                    </Text>
                    <Text size="xs" c="rgba(255,255,255,0.70)" fw={600} ta="right">
                      Out
                    </Text>
                    <Text size="xs" c="rgba(255,255,255,0.70)" fw={600} ta="right">
                      Total
                    </Text>

                    {/* LLM */}
                    <Text size="xs" c="rgba(255,255,255,0.90)" fw={600}>
                      LLM
                    </Text>
                    <Text size="xs" c="white" ta="right" ff="monospace" style={{ fontVariantNumeric: "tabular-nums" }}>
                      {me.token_usage.llm_input_tokens}
                    </Text>
                    <Text size="xs" c="white" ta="right" ff="monospace" style={{ fontVariantNumeric: "tabular-nums" }}>
                      {me.token_usage.llm_output_tokens}
                    </Text>
                    <Text size="xs" c="white" ta="right" ff="monospace" fw={600} style={{ fontVariantNumeric: "tabular-nums" }}>
                      {me.token_usage.llm_input_tokens + me.token_usage.llm_output_tokens}
                    </Text>

                    {/* STT */}
                    <Text size="xs" c="rgba(255,255,255,0.90)" fw={600}>
                      STT
                    </Text>
                    <Text size="xs" c="white" ta="right" ff="monospace" style={{ fontVariantNumeric: "tabular-nums" }}>
                      {me.token_usage.stt_input_tokens}
                    </Text>
                    <Text size="xs" c="white" ta="right" ff="monospace" style={{ fontVariantNumeric: "tabular-nums" }}>
                      {me.token_usage.stt_output_tokens}
                    </Text>
                    <Text size="xs" c="white" ta="right" ff="monospace" fw={600} style={{ fontVariantNumeric: "tabular-nums" }}>
                      {me.token_usage.stt_input_tokens + me.token_usage.stt_output_tokens}
                    </Text>
                  </SimpleGrid>
                </Stack>
              </Box>
            </Menu.Item>
          </Menu.Dropdown>
        </Menu>

        <ActionIcon color="red" radius="md" onClick={() => { void logout(); }}>
          <IconDoorExit size={16} />
        </ActionIcon>
      </Group>

      <NotificationsModal
        opened={notificationsOpen}
        onClose={() => setNotificationsOpen(false)}
        notifications={notifications}
        timezone={timezone}
        currentUserId={me?.id ?? null}
        isAdminApprover={isAdminApprover}
        decisionBusy={decisionBusy}
        decisionError={decisionError}
        localDecisions={localDecisions}
        onMarkRead={markNotificationRead}
        onApprove={(notificationId, requestId) =>
          decidePermissionRequest(notificationId, requestId, "approve")
        }
        onReject={(notificationId, requestId) =>
          decidePermissionRequest(notificationId, requestId, "reject")
        }
      />

      <AlarmModal
        opened={alarmOpen}
        onClose={() => {
          setAlarmOpen(false);
          stopAlarmSound();
        }}
        activeAlarm={activeAlarm}
        timezone={timezone}
        audioError={audioError}
        alarmSoundReady={alarmSoundReady}
        onPlay={playAlarmSound}
        onStop={stopAlarmSound}
        onMarkRead={markNotificationRead}
      />
    </>
  );
}

export default function Navbar() {
  const { pathname } = useLocation();
  const { me } = useAuth();

  const isActive = (path: string) => {
    if (path === "/") {
      return pathname === "/";
    }
    return pathname === path || pathname.startsWith(`${path}/`);
  };

  const canAccessAdmin =
    (me?.permissions.includes("agent:trace:view_all") ?? false) ||
    (me?.permissions.includes("permissions:approve") ?? false);

  return (
    <Group justify="space-between" align="center" wrap="nowrap">
      <Group gap="xs">
        <Button
          size="xs"
          variant={isActive("/") ? "light" : "subtle"}
          color="teal"
          radius="md"
          component={Link}
          to="/"
          leftSection={<IconHome size={18} />}
        >
          Agent home
        </Button>
        <Button
          size="xs"
          variant={isActive("/traces") ? "light" : "subtle"}
          color="teal"
          radius="md"
          component={Link}
          to="/traces"
          leftSection={<IconCheckupList size={18} />}
        >
          Traces
        </Button>
        {canAccessAdmin ? (
          <Button
            size="xs"
            variant={isActive("/admin") ? "light" : "subtle"}
            color="teal"
            radius="md"
            component={Link}
            to="/admin"
            leftSection={<IconShieldCog size={18} />}
          >
            Admin
          </Button>
        ) : null}
      </Group>
      <UserBadgeSection />
    </Group>
  );
}