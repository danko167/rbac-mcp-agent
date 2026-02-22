import { Accordion, Grid, Modal, Paper, ScrollArea, Stack, Text } from "@mantine/core";

type PermissionCategory = "user_features" | "system_access" | "other";

type PermissionDetailView = {
  permission: string;
  tool: string;
  tool_label: string;
  category: string;
  category_label: string;
  title: string;
  description: string;
};

type Props = {
  opened: boolean;
  onClose: () => void;
  permissionDetails: PermissionDetailView[];
};

function mergeToolGroups(
  ...groups: Array<Record<string, PermissionDetailView[]>>
): Record<string, PermissionDetailView[]> {
  const merged: Record<string, PermissionDetailView[]> = {};
  groups.forEach((group) => {
    Object.entries(group).forEach(([tool, details]) => {
      if (!merged[tool]) {
        merged[tool] = [];
      }
      merged[tool].push(...details);
    });
  });
  return merged;
}

function renderToolRows(toolGroups: Record<string, PermissionDetailView[]>) {
  const tools = Object.keys(toolGroups).sort((a, b) => a.localeCompare(b));
  if (!tools.length) {
    return (
      <Text size="sm" c="dimmed">
        No permissions in this section.
      </Text>
    );
  }

  return tools.map((tool) => (
    <Stack key={tool} gap={4}>
      <Text size="sm" fw={600}>{toolGroups[tool][0]?.tool_label || tool}</Text>

      <Grid gutter="sm">
        {toolGroups[tool]
          .slice()
          .sort((a, b) => a.permission.localeCompare(b.permission))
          .map((permissionDetail) => {
            return (
              <Grid.Col key={permissionDetail.permission} span={{ base: 12, sm: 6, lg: 3 }}>
                <Paper
                  withBorder
                  radius="md"
                  p="xs"
                  h="100%"
                >
                  <Stack gap={2}>
                    <Text size="sm" fw={500}>{permissionDetail.title}</Text>
                    <Text size="xs" c="dimmed">{permissionDetail.description}</Text>
                    <Text size="xs" c="dimmed">{permissionDetail.permission}</Text>
                  </Stack>
                </Paper>
              </Grid.Col>
            );
          })}
      </Grid>
    </Stack>
  ));
}

export default function PermissionsModal({ opened, onClose, permissionDetails }: Props) {
  const groupedByCategoryAndTool = permissionDetails.reduce<
    Record<PermissionCategory, Record<string, PermissionDetailView[]>>
  >(
    (acc, permissionDetail) => {
      const category = (permissionDetail.category as PermissionCategory) || "other";
      if (!acc[category]) {
        acc[category] = {};
      }
      if (!acc[category][permissionDetail.tool]) {
        acc[category][permissionDetail.tool] = [];
      }
      acc[category][permissionDetail.tool].push(permissionDetail);
      return acc;
    },
    {
      user_features: {},
      system_access: {},
      other: {},
    }
  );

  const userTools = groupedByCategoryAndTool.user_features;
  const systemTools = mergeToolGroups(groupedByCategoryAndTool.system_access, groupedByCategoryAndTool.other);

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title={<Text fw={600}>Permissions</Text>}
      radius="md"
      size="80%"
    >
      <ScrollArea h={570} offsetScrollbars type="auto">
        <Stack gap={6}>
          {permissionDetails.length ? (
            <Accordion variant="contained" radius="md">
              <Accordion.Item value="user_features">
                <Accordion.Control>What You Can Use</Accordion.Control>
                <Accordion.Panel>
                  <Stack gap={6}>{renderToolRows(userTools)}</Stack>
                </Accordion.Panel>
              </Accordion.Item>

              <Accordion.Item value="system_access">
                <Accordion.Control>System &amp; Admin Access</Accordion.Control>
                <Accordion.Panel>
                  <Stack gap={6}>{renderToolRows(systemTools)}</Stack>
                </Accordion.Panel>
              </Accordion.Item>
            </Accordion>
          ) : (
            <Text size="sm" c="dimmed">
              Permission details are unavailable.
            </Text>
          )}
        </Stack>
      </ScrollArea>
    </Modal>
  );
}
