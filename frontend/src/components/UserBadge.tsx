import { useState } from "react";
import {
  Badge,
  Button,
  Group,
  Modal,
  Paper,
  ScrollArea,
  Stack,
  Text,
  Title,
} from "@mantine/core";
import { IconLock, IconUser, IconCrown, IconShield, type TablerIcon } from "@tabler/icons-react";
import { useAuth } from "../auth/useAuth";


type RoleConfig = {
  color: string;
  icon?: TablerIcon;
  label?: string;
};

const ROLE_CONFIG: Record<string, RoleConfig> = {
  basic: { color: "orange", icon: IconUser, label: "Basic" },
  pro: { color: "violet", icon: IconCrown, label: "Pro" },
  admin: { color: "red", icon: IconShield, label: "Admin" },
};



export default function UserBadge() {
  const { me, meLoading, meError } = useAuth();
  const [permsOpen, setPermsOpen] = useState(false);

  if (meLoading) {
    return (
      <Paper withBorder radius="md" p="sm">
        <Text size="sm" c="dimmed">
          Loading user…
        </Text>
      </Paper>
    );
  }

  if (meError) {
    return (
      <Paper withBorder radius="md" p="sm">
        <Text size="sm" c="red">
          {meError}
        </Text>
      </Paper>
    );
  }

  if (!me) return null;

  return (
    <>
      <Paper withBorder radius="md" p="xs">
        <Group justify="space-between" align="center" wrap="nowrap">
          {/* LEFT: identity */}
          <Stack gap={2}>
            <Text size="xs" c="dimmed">
              Signed in as
            </Text>
            <Text size="sm" fw={600} style={{ wordBreak: "break-word" }}>
              {me.email}
            </Text>
          </Stack>

          {/* MIDDLE: roles */}
          <Group gap={4} wrap="wrap" align="center">
            {me.roles.length ? (
              me.roles.map((r) => {
                const cfg = ROLE_CONFIG[r];
                const Icon = cfg?.icon;

                return (
                  <Badge
                    key={r}
                    variant="light"
                    color={cfg?.color ?? "gray"}
                    leftSection={Icon ? <Icon size={16} /> : undefined}
                  >
                    {cfg?.label ?? r}
                  </Badge>
                );
              })

            ) : (
              <Badge variant="light" color="gray">
                no roles
              </Badge>
            )}
          </Group>

          {/* RIGHT: permissions */}
          <Button
            variant="subtle"
            size="xs"
            color="teal"
            leftSection={<IconLock size={16} />}
            onClick={() => setPermsOpen(true)}
            px={0}
          >
            Permissions ({me.permissions.length})
          </Button>
        </Group>
      </Paper>

      <Modal
        opened={permsOpen}
        onClose={() => setPermsOpen(false)}
        title={<Title order={4}>Permissions</Title>}
        radius="md"
        size="md"
      >
        <ScrollArea h={320} offsetScrollbars type="auto">
          <Stack gap={6}>
            {me.permissions.length ? (
              me.permissions.map((p) => (
                <Paper key={p} withBorder radius="md" p="xs">
                  <Text size="sm">{p}</Text>
                </Paper>
              ))
            ) : (
              <Text size="sm" c="dimmed">
                No permissions.
              </Text>
            )}
          </Stack>
        </ScrollArea>
      </Modal>
    </>
  );
}
