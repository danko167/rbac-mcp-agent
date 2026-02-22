import type { UserNotification } from "../../auth/AuthContext";
import { displayNameFromEmail } from "../../utils/displayName";

export function buildNoticePrompt(noticeValue: string): string | null {
  if (noticeValue.startsWith("permission_request_result:")) {
    return "I received an update on my permission request. Check my latest request status and explain clearly whether it was approved or rejected and what I can do now.";
  }
  return null;
}

function extractNoticeNotificationId(noticeValue: string): number | null {
  const firstColon = noticeValue.indexOf(":");
  if (firstColon < 0) {
    return null;
  }
  const secondColon = noticeValue.indexOf(":", firstColon + 1);
  const idPart = secondColon < 0
    ? noticeValue.slice(firstColon + 1)
    : noticeValue.slice(firstColon + 1, secondColon);
  const parsed = Number(idPart);
  return Number.isFinite(parsed) ? parsed : null;
}

export function buildNoticeAssistantMessage(
  noticeValue: string,
  notifications: UserNotification[],
  currentUserId?: number | null,
): string | null {
  const notificationId = extractNoticeNotificationId(noticeValue);
  if (notificationId == null) {
    if (noticeValue.startsWith("approval_request_created:")) {
      return "A new delegated access request arrived. Please reply with \"approve\" or \"reject\", and include a reason if you want.";
    }
    if (noticeValue.startsWith("permission_request_result:")) {
      return "Your permission request status changed. I can summarize the latest result if you want.";
    }
    return null;
  }

  const notification = notifications.find((item) => item.id === notificationId);
  if (!notification) {
    if (noticeValue.startsWith("approval_request_created:")) {
      return "A new delegated access request arrived. Please reply with \"approve\" or \"reject\", and include a reason if you want.";
    }
    if (noticeValue.startsWith("permission_request_result:")) {
      return "Your permission request status changed. I can summarize the latest result if you want.";
    }
    return null;
  }

  const payload = notification.payload ?? {};
  const permissionName = typeof payload.permission_name === "string" ? payload.permission_name : "requested permission";

  if (noticeValue.startsWith("approval_request_created:")) {
    const requestId = typeof payload.request_id === "number" ? payload.request_id : null;
    const requesterUserId = payload.requester_user_id;
    const requesterEmail = typeof payload.requester_email === "string" ? payload.requester_email : null;
    const requesterLabel = requesterEmail
      ? displayNameFromEmail(requesterEmail)
      : typeof requesterUserId === "number"
        ? `User ${requesterUserId}`
        : "another user";
    if (requestId != null) {
      return `${requesterLabel} is asking for delegated access: ${permissionName}. Request ID: ${requestId}. Please reply with "approve ${requestId}" or "reject ${requestId}", and include a reason if you want.`;
    }
    return `${requesterLabel} is asking for delegated access: ${permissionName}. Please reply with "approve" or "reject", and include a reason if you want.`;
  }

  if (noticeValue.startsWith("permission_request_result:")) {
    const requesterUserId = typeof payload.requester_user_id === "number" ? payload.requester_user_id : null;
    const requesterEmail = typeof payload.requester_email === "string" ? payload.requester_email : null;
    const decidedByUserId = typeof payload.decided_by_user_id === "number" ? payload.decided_by_user_id : null;
    const isRequester = currentUserId != null && requesterUserId != null && currentUserId === requesterUserId;
    const isDecider = currentUserId != null && decidedByUserId != null && currentUserId === decidedByUserId;
    const requesterLabel = requesterEmail
      ? displayNameFromEmail(requesterEmail)
      : requesterUserId != null
        ? `User ${requesterUserId}`
        : "The requester";

    if (notification.event_type === "permission.request.approved") {
      if (isDecider && !isRequester) {
        return `You approved ${requesterLabel}'s request for ${permissionName}. They were notified and can proceed.`;
      }
      return `Your request for ${permissionName} was approved. You can proceed with the delegated action now.`;
    }
    if (notification.event_type === "permission.request.rejected") {
      if (isDecider && !isRequester) {
        return `You rejected ${requesterLabel}'s request for ${permissionName}. They were notified and can submit a new request with more context.`;
      }
      return `Your request for ${permissionName} was rejected. You can ask for a different scope or provide more context and request again.`;
    }
  }

  return null;
}
