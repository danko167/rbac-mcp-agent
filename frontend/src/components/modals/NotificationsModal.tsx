import { Badge, Button, Group, Modal, Paper, ScrollArea, Stack, Text } from "@mantine/core";
import type { UserNotification } from "../../auth/AuthContext";
import { displayNameFromEmail } from "../../utils/displayName";
import { formatTimestampInTimezone } from "../../utils/timezone";

type Props = {
  opened: boolean;
  onClose: () => void;
  notifications: UserNotification[];
  timezone: string;
  currentUserId: number | null;
  isAdminApprover: boolean;
  decisionBusy: Set<number>;
  decisionError: string | null;
  localDecisions: Record<number, "approved" | "rejected">;
  onMarkRead: (notificationId: number) => Promise<void>;
  onApprove: (notificationId: number, requestId: number) => Promise<void>;
  onReject: (notificationId: number, requestId: number) => Promise<void>;
};

function getPermissionRequestId(payload: Record<string, unknown>): number | null {
  const value = payload.request_id;
  return typeof value === "number" ? value : null;
}

function getDecisionForRequest(
  notifications: UserNotification[],
  requestId: number,
  localDecisions: Record<number, "approved" | "rejected">,
): "approved" | "rejected" | null {
  const localDecision = localDecisions[requestId];
  if (localDecision) {
    return localDecision;
  }

  for (const notification of notifications) {
    const id = getPermissionRequestId(notification.payload);
    if (id !== requestId) {
      continue;
    }
    if (notification.event_type === "permission.request.approved") {
      return "approved";
    }
    if (notification.event_type === "permission.request.rejected") {
      return "rejected";
    }
  }
  return null;
}

function canCurrentUserDecide(
  payload: Record<string, unknown>,
  currentUserId: number | null,
  isAdminApprover: boolean,
): boolean {
  if (isAdminApprover) {
    return true;
  }

  if (currentUserId == null) {
    return false;
  }

  const requestKind = payload.request_kind;
  const targetUserId = payload.target_user_id;
  return requestKind === "delegation" && typeof targetUserId === "number" && targetUserId === currentUserId;
}

function formatEventType(eventType: string): string {
  switch (eventType) {
    case "permission.request.created":
      return "Access request created";
    case "permission.request.approved":
      return "Access request approved";
    case "permission.request.rejected":
      return "Access request rejected";
    default:
      return eventType;
  }
}

function formatFallbackPayload(payload: Record<string, unknown>): string {
  const entries = Object.entries(payload);
  if (!entries.length) {
    return "No additional details.";
  }

  return entries
    .map(([key, value]) => `${key.replace(/_/g, " ")}: ${String(value)}`)
    .join("\n");
}

function formatNotificationMessage(notification: UserNotification): string {
  const payload = notification.payload ?? {};
  const permissionName = typeof payload.permission_name === "string" ? payload.permission_name : "requested permission";
  const requesterEmail = typeof payload.requester_email === "string" ? payload.requester_email : null;
  const requesterUserId = typeof payload.requester_user_id === "number" ? payload.requester_user_id : null;
  const requesterLabel = requesterEmail
    ? displayNameFromEmail(requesterEmail)
    : requesterUserId != null
      ? `User ${requesterUserId}`
      : "A user";

  if (notification.event_type === "permission.request.created") {
    return `${requesterLabel} requested delegated access for ${permissionName}.`;
  }

  if (notification.event_type === "permission.request.approved") {
    return `A request for ${permissionName} was approved.`;
  }

  if (notification.event_type === "permission.request.rejected") {
    return `A request for ${permissionName} was rejected.`;
  }

  return formatFallbackPayload(payload);
}

export default function NotificationsModal({
  opened,
  onClose,
  notifications,
  timezone,
  currentUserId,
  isAdminApprover,
  decisionBusy,
  decisionError,
  localDecisions,
  onMarkRead,
  onApprove,
  onReject,
}: Props) {
  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title={<Text fw={600}>Notifications</Text>}
      radius="md"
      size="xl"
    >
      <ScrollArea h={400} offsetScrollbars type="auto">
        <Stack gap={6}>
          {decisionError ? <Text size="xs" c="red">{decisionError}</Text> : null}
          {notifications.length ? (
            notifications.map((notification) => (
              <Paper key={notification.id} withBorder radius="md" p="xs">
                <Group justify="space-between" align="center" mb={4}>
                  <Badge variant="light" color={notification.is_read ? "gray" : "teal"}>
                    {formatEventType(notification.event_type)}
                  </Badge>
                  {!notification.is_read && (
                    <Button size="xs" radius="md" variant="light" onClick={() => void onMarkRead(notification.id)}>
                      Mark read
                    </Button>
                  )}
                </Group>
                <Text size="xs" c="dimmed" mb={4}>{formatTimestampInTimezone(notification.created_at, timezone)}</Text>
                <Text size="sm" style={{ whiteSpace: "pre-wrap" }}>
                  {formatNotificationMessage(notification)}
                </Text>
                {notification.event_type === "permission.request.created" ? (() => {
                  const requestId = getPermissionRequestId(notification.payload);
                  const canDecide = canCurrentUserDecide(notification.payload, currentUserId, isAdminApprover);
                  if (!requestId || notification.is_read || !canDecide) return null;
                  const requestDecision = getDecisionForRequest(notifications, requestId, localDecisions);
                  if (requestDecision) {
                    return (
                      <Text mt="xs" size="xs" c={requestDecision === "approved" ? "teal" : "red"}>
                        {requestDecision === "approved" ? "Already approved" : "Already rejected"}
                      </Text>
                    );
                  }
                  const busy = decisionBusy.has(notification.id);
                  return (
                    <Group mt="xs">
                      <Button
                        size="xs"
                        color="teal"
                        radius="md"
                        loading={busy}
                        disabled={busy}
                        onClick={() => void onApprove(notification.id, requestId)}
                      >
                        Approve
                      </Button>
                      <Button
                        size="xs"
                        variant="light"
                        radius="md"
                        color="red"
                        loading={busy}
                        disabled={busy}
                        onClick={() => void onReject(notification.id, requestId)}
                      >
                        Reject
                      </Button>
                    </Group>
                  );
                })() : null}
              </Paper>
            ))
          ) : (
            <Text size="sm" c="dimmed">
              No notifications.
            </Text>
          )}
        </Stack>
      </ScrollArea>
    </Modal>
  );
}
