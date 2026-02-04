import { Link } from "react-router";
import { Button, Group, Paper, Tooltip, ActionIcon } from "@mantine/core";
import { IconCheckupList, IconArrowBackUp, IconClipboardList, IconDoorExit } from "@tabler/icons-react";

type AgentNavProps = {
  onLogout: () => void;
  backTo?: string;
  backLabel?: string;
};

export default function AgentNav({
  onLogout,
  backTo,
  backLabel = "Back",
}: AgentNavProps) {
  return (
    <Paper withBorder radius="md" p="sm">
      <Group justify="space-between" wrap="wrap">
        <Group gap="xs">
          {backTo && (
            <Button size="xs" variant="light" color="teal" radius="md" component={Link} to={backTo} leftSection={<IconArrowBackUp size={18} />}>
              {backLabel}
            </Button>
          )}
          <Button size="xs" variant="light" color="teal" radius="md" component={Link} to="/traces" leftSection={<IconCheckupList size={18} />}>
            My traces
          </Button>
          <Button size="xs" variant="light" color="teal" radius="md" component={Link} to="/admin/traces" leftSection={<IconClipboardList size={18} />} >
            Admin
          </Button>
        </Group>

        <Group gap="xs">
          <Tooltip label="Logout" withArrow>
            <ActionIcon color="red" radius="md" onClick={onLogout}>
              <IconDoorExit size={18} />
            </ActionIcon>
          </Tooltip>
        </Group>
      </Group>
    </Paper>
  );
}
