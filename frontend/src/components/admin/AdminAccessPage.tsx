import { useEffect, useState } from "react";
import { Button, Checkbox, Grid, Group, Paper, ScrollArea, Select, Stack, Text, TextInput, Title } from "@mantine/core";
import {
  assignPermissionToRole,
  assignRoleToUser,
  createDelegation,
  fetchRbacDelegations,
  fetchRbacPermissions,
  fetchRbacRoles,
  fetchRbacUsers,
  revokeDelegation,
  unassignPermissionFromRole,
  unassignRoleFromUser,
} from "../../api/rbac";
import type { RbacDelegation, RbacPermission, RbacRole, RbacUser } from "../../types/rbac";
import { fullHeightPaperStyle } from "../../layout/pageStyles";

type ApiErrorShape = {
  response?: {
    data?: {
      detail?: string | { explanation?: string };
    };
  };
};

function getErrorMessage(error: unknown, fallback: string): string {
  const detail = (error as ApiErrorShape)?.response?.data?.detail;
  if (typeof detail === "string") {
    return detail;
  }
  if (detail && typeof detail === "object" && typeof detail.explanation === "string") {
    return detail.explanation;
  }
  return fallback;
}

export function AdminAccessContent() {
  const [roles, setRoles] = useState<RbacRole[]>([]);
  const [permissions, setPermissions] = useState<RbacPermission[]>([]);
  const [users, setUsers] = useState<RbacUser[]>([]);
  const [delegations, setDelegations] = useState<RbacDelegation[]>([]);
  const [selectedRoleId, setSelectedRoleId] = useState<string | null>(null);
  const [selectedUserId, setSelectedUserId] = useState<string | null>(null);
  const [selectedGrantorId, setSelectedGrantorId] = useState<string | null>(null);
  const [selectedGranteeId, setSelectedGranteeId] = useState<string | null>(null);
  const [selectedDelegationPermission, setSelectedDelegationPermission] = useState<string | null>(null);
  const [selectedDelegationExpiresAt, setSelectedDelegationExpiresAt] = useState<string>("");

  const [loading, setLoading] = useState(true);
  const [pendingKeys, setPendingKeys] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);

  async function reloadAll() {
    const [nextRoles, nextPermissions, nextUsers, nextDelegations] = await Promise.all([
      fetchRbacRoles(),
      fetchRbacPermissions(),
      fetchRbacUsers(),
      fetchRbacDelegations(),
    ]);
    setRoles(nextRoles);
    setPermissions(nextPermissions);
    setUsers(nextUsers);
    setDelegations(nextDelegations);
  }

  useEffect(() => {
    void (async () => {
      setLoading(true);
      setError(null);
      try {
        await reloadAll();
      } catch (e: unknown) {
        setError(getErrorMessage(e, "Failed to load RBAC data"));
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  useEffect(() => {
    if (!roles.length) {
      setSelectedRoleId(null);
      return;
    }

    const exists = roles.some((role) => String(role.id) === selectedRoleId);
    if (!exists) {
      setSelectedRoleId(String(roles[0].id));
    }
  }, [roles, selectedRoleId]);

  useEffect(() => {
    if (!users.length) {
      setSelectedUserId(null);
      return;
    }

    const exists = users.some((user) => String(user.id) === selectedUserId);
    if (!exists) {
      setSelectedUserId(String(users[0].id));
    }
  }, [users, selectedUserId]);

  useEffect(() => {
    if (!users.length) {
      setSelectedGrantorId(null);
      setSelectedGranteeId(null);
      return;
    }

    const grantorExists = users.some((user) => String(user.id) === selectedGrantorId);
    if (!grantorExists) {
      setSelectedGrantorId(String(users[0].id));
    }

    const granteeExists = users.some((user) => String(user.id) === selectedGranteeId);
    if (!granteeExists) {
      const fallback = users.length > 1 ? users[1] : users[0];
      setSelectedGranteeId(String(fallback.id));
    }
  }, [users, selectedGrantorId, selectedGranteeId]);

  async function withPending(key: string, action: () => Promise<void>) {
    setPendingKeys((prev) => {
      const next = new Set(prev);
      next.add(key);
      return next;
    });
    setError(null);
    try {
      await action();
      await reloadAll();
    } catch (e: unknown) {
      setError(getErrorMessage(e, "RBAC update failed"));
    } finally {
      setPendingKeys((prev) => {
        const next = new Set(prev);
        next.delete(key);
        return next;
      });
    }
  }

  const selectedRole = roles.find((role) => String(role.id) === selectedRoleId) ?? null;
  const selectedUser = users.find((user) => String(user.id) === selectedUserId) ?? null;

  const roleOptions = roles.map((role) => ({
    value: String(role.id),
    label: role.name,
  }));

  const userOptions = users.map((user) => ({
    value: String(user.id),
    label: user.email,
  }));

  const permissionGroups = permissions.reduce<Record<string, RbacPermission[]>>((acc, permission) => {
    const toolKey = permission.name.split(":")[0] || "other";
    if (!acc[toolKey]) {
      acc[toolKey] = [];
    }
    acc[toolKey].push(permission);
    return acc;
  }, {});

  const sortedPermissionGroupKeys = Object.keys(permissionGroups).sort((a, b) => a.localeCompare(b));

  const delegationPermissionOptions = permissions
    .filter((permission) => permission.name.endsWith(".for_others"))
    .map((permission) => ({ value: permission.name, label: permission.name }));

  const canCreateDelegation =
    !!selectedGrantorId &&
    !!selectedGranteeId &&
    !!selectedDelegationPermission &&
    selectedGrantorId !== selectedGranteeId;

  return (
    <Paper radius="md" p="sm" style={fullHeightPaperStyle}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <Title order={3}>Admin access management</Title>
        <Text size="sm" c="dimmed">
          {users.length} users · {roles.length} roles
        </Text>
      </div>

      {error ? (
        <Text c="red">{error}</Text>
      ) : loading ? (
        <Text size="sm">Loading...</Text>
      ) : (
        <ScrollArea h={480} type="auto" offsetScrollbars>

          <Grid gutter="md">
            <Grid.Col span={4}>
              <Paper withBorder radius="md" p="md">
                <Stack gap="sm">
                  <Title order={5}>User ↔ Role</Title>
                  <Select
                    radius="md"
                    label="User"
                    placeholder="Select user"
                    searchable
                    data={userOptions}
                    value={selectedUserId}
                    onChange={setSelectedUserId}
                  />

                  {selectedUser ? (
                    <Grid gutter="sm">
                      {roles.map((role) => {
                        const isChecked = selectedUser.roles.includes(role.name);
                        const key = `user:${selectedUser.id}:role:${role.id}`;
                        const isPending = pendingKeys.has(key);

                        return (
                          <Grid.Col key={role.id} span={{ base: 12, sm: 6 }}>
                            <Checkbox
                              color="violet"
                              label={role.name}
                              checked={isChecked}
                              disabled={isPending}
                              onChange={(event) => {
                                const nextChecked = event.currentTarget.checked;
                                if (nextChecked === isChecked) {
                                  return;
                                }

                                void withPending(key, async () => {
                                  if (nextChecked) {
                                    await assignRoleToUser(selectedUser.id, role.id);
                                  } else {
                                    await unassignRoleFromUser(selectedUser.id, role.id);
                                  }
                                });
                              }}
                            />
                          </Grid.Col>
                        );
                      })}
                    </Grid>
                  ) : (
                    <Text size="sm" c="dimmed">No user selected.</Text>
                  )}
                </Stack>
              </Paper>
            </Grid.Col>

            <Grid.Col span={8}>
              <Paper withBorder radius="md" p="md">
                <Stack gap="sm">
                  <Title order={5}>Delegation (act on someone else’s behalf)</Title>

                  <Grid gutter="sm">
                    <Grid.Col span={{ base: 12, md: 4 }}>
                      <Select
                        radius="md"
                        label="Whose account/action is this for?"
                        placeholder="Select the account owner (on whose behalf)"
                        searchable
                        data={userOptions}
                        value={selectedGrantorId}
                        onChange={setSelectedGrantorId}
                      />
                    </Grid.Col>
                    <Grid.Col span={{ base: 12, md: 4 }}>
                      <Select
                        radius="md"
                        label="Who can act on their behalf?"
                        placeholder="Select the acting user"
                        searchable
                        data={userOptions}
                        value={selectedGranteeId}
                        onChange={setSelectedGranteeId}
                      />
                    </Grid.Col>
                    <Grid.Col span={{ base: 12, md: 4 }}>
                      <Select
                        radius="md"
                        label="What can they do on that account’s behalf?"
                        placeholder="Select delegated action"
                        searchable
                        data={delegationPermissionOptions}
                        value={selectedDelegationPermission}
                        onChange={setSelectedDelegationPermission}
                      />
                    </Grid.Col>
                    <Grid.Col span={{ base: 12, md: 4 }}>
                      <TextInput
                        radius="md"
                        label="Expires at (optional)"
                        type="datetime-local"
                        value={selectedDelegationExpiresAt}
                        onChange={(event) => setSelectedDelegationExpiresAt(event.currentTarget.value)}
                      />
                    </Grid.Col>
                  </Grid>

                  <Text size="xs" c="dimmed">
                    Example: If owner = Admin, actor = Alice, permission = alarms.set.for_others, then Alice can set alarms for Admin.
                  </Text>

                  <Group>
                    <Button
                      size="xs"
                      color="teal"
                      radius="md"
                      disabled={!canCreateDelegation}
                      onClick={() => {
                        if (!canCreateDelegation) {
                          return;
                        }

                        const key = `delegation:create:${selectedGrantorId}:${selectedGranteeId}:${selectedDelegationPermission}`;
                        void withPending(key, async () => {
                          const expiresAtIso = selectedDelegationExpiresAt
                            ? new Date(selectedDelegationExpiresAt).toISOString()
                            : null;

                          await createDelegation({
                            grantor_user_id: Number(selectedGrantorId),
                            grantee_user_id: Number(selectedGranteeId),
                            permission_name: selectedDelegationPermission,
                            expires_at: expiresAtIso,
                          });
                        });
                      }}
                    >
                      Save delegation
                    </Button>
                    {selectedGrantorId === selectedGranteeId ? (
                      <Text size="xs" c="dimmed">Owner and acting user must be different people.</Text>
                    ) : null}
                  </Group>

                  {delegations.length ? (
                    <Stack gap={6}>
                      {delegations.map((delegation) => {
                        const key = `delegation:revoke:${delegation.id}`;
                        const isPending = pendingKeys.has(key);
                        return (
                          <Group key={delegation.id} justify="space-between" align="center" wrap="wrap">
                            <Text size="sm">
                              <strong>{delegation.grantee_email ?? delegation.grantee_user_id}</strong>
                              {" can perform "}
                              {delegation.permission_name}
                              {" on behalf of "}
                              <strong>{delegation.grantor_email ?? delegation.grantor_user_id}</strong>
                              {delegation.expires_at ? ` · expires ${new Date(delegation.expires_at).toLocaleString()}` : ""}
                            </Text>
                            <Button
                              size="xs"
                              color="red"
                              variant="light"
                              radius="md"
                              disabled={isPending}
                              onClick={() => {
                                void withPending(key, async () => {
                                  await revokeDelegation(delegation.id);
                                });
                              }}
                            >
                              Revoke
                            </Button>
                          </Group>
                        );
                      })}
                    </Stack>
                  ) : (
                    <Text size="sm" c="dimmed">No active delegations.</Text>
                  )}
                </Stack>
              </Paper>
            </Grid.Col>

            <Grid.Col span={12}>
              <Paper withBorder radius="md" p="md">
                <Stack gap="sm">
                  <Title order={5}>Role ↔ Permission</Title>
                  <Select
                    radius="md"
                    label="Role"
                    placeholder="Select role"
                    searchable
                    data={roleOptions}
                    value={selectedRoleId}
                    onChange={setSelectedRoleId}
                  />

                  {selectedRole ? (
                    <Grid gutter="sm">
                      {sortedPermissionGroupKeys.map((groupKey) => (
                        <Grid.Col key={groupKey} span={{ base: 12, sm: 3 }}>
                          <Paper withBorder radius="sm" p="xs">
                            <Stack gap={6}>
                              <Text fw={600} size="xs" tt="uppercase" c="dimmed">
                                {groupKey}
                              </Text>
                              {permissionGroups[groupKey]
                                .slice()
                                .sort((a, b) => a.name.localeCompare(b.name))
                                .map((permission) => {
                                  const isChecked = selectedRole.permissions.includes(permission.name);
                                  const key = `role:${selectedRole.id}:perm:${permission.id}`;
                                  const isPending = pendingKeys.has(key);

                                  return (
                                    <Checkbox
                                      color="violet"
                                      key={permission.id}
                                      label={permission.name}
                                      checked={isChecked}
                                      disabled={isPending}
                                      onChange={(event) => {
                                        const nextChecked = event.currentTarget.checked;
                                        if (nextChecked === isChecked) {
                                          return;
                                        }

                                        void withPending(key, async () => {
                                          if (nextChecked) {
                                            await assignPermissionToRole(selectedRole.id, permission.id);
                                          } else {
                                            await unassignPermissionFromRole(selectedRole.id, permission.id);
                                          }
                                        });
                                      }}
                                    />
                                  );
                                })}
                            </Stack>
                          </Paper>
                        </Grid.Col>
                      ))}
                    </Grid>
                  ) : (
                    <Text size="sm" c="dimmed">No role selected.</Text>
                  )}
                </Stack>
              </Paper>
            </Grid.Col>
          </Grid>
        </ScrollArea>
      )}
    </Paper>
  );
}

export default function AdminAccessPage() {
  return <AdminAccessContent />;
}
