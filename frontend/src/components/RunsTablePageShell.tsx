import type { ReactNode } from "react";
import { Paper, ScrollArea, Group, Stack, Text, Title } from "@mantine/core";

type Props = {
  title: string;
  count: number;
  children: ReactNode;
};

export default function RunsTablePageShell({ title, count, children }: Props) {
  return (
    <Paper
      withBorder
      radius="md"
      p="xs"
      style={{
        height: "calc(100vh - 35px)",
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
      }}
    >
      <Stack
        gap="xs"
        style={{
          flex: 1,
          minHeight: 0,
        }}
      >
        <Group justify="space-between" align="center" px="sm">
          <Title order={3}>{title}</Title>
          <Text size="sm" c="dimmed">
            {count} runs
          </Text>
        </Group>

        <ScrollArea
          type="auto"
          offsetScrollbars
          style={{
            flex: 1,
            minHeight: 0,
          }}
        >
          {children}
        </ScrollArea>
      </Stack>
    </Paper>
  );
}
