export const endpoints = {
  auth: {
    login: "/login",
    me: "/me",
    meTimezone: "/me/timezone",
    timezones: "/timezones",
  },
  agent: {
    run: "/agent/run",
    transcribe: "/agent/transcribe",
    conversations: "/agent/conversations",
    approvalsConversation: "/agent/conversations/approvals",
    conversationById: (id: number | string) => `/agent/conversations/${id}`,
    runs: "/agent/runs",
    runById: (id: number | string) => `/agent/runs/${id}`,
  },
  admin: {
    agentRuns: "/admin/agent/runs",
    agentRunById: (id: number | string) => `/admin/agent/runs/${id}`,
    rbacRoles: "/admin/rbac/roles",
    rbacPermissions: "/admin/rbac/permissions",
    rbacUsers: "/admin/rbac/users",
    rbacDelegations: "/admin/rbac/delegations",
    permissionRequests: "/admin/permission-requests",
    assignRolePermission: (roleId: number | string, permissionId: number | string) =>
      `/admin/rbac/roles/${roleId}/permissions/${permissionId}`,
    assignUserRole: (userId: number | string, roleId: number | string) =>
      `/admin/rbac/users/${userId}/roles/${roleId}`,
    revokeDelegation: (delegationId: number | string) => `/admin/rbac/delegations/${delegationId}`,
    approvePermissionRequest: (requestId: number | string) =>
      `/admin/permission-requests/${requestId}/approve`,
    rejectPermissionRequest: (requestId: number | string) =>
      `/admin/permission-requests/${requestId}/reject`,
  },
  notifications: {
    list: "/notifications",
    readById: (id: number | string) => `/notifications/${id}/read`,
    stream: "/api/events/stream",
  },
} as const;
