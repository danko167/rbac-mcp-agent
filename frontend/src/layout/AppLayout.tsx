import { Outlet, Link } from "react-router";
import { Box, Group, Text, Paper } from "@mantine/core";
import { IconRobot } from "@tabler/icons-react";
import Navbar from "../components/Navbar";
import classes from "../assets/styles/AppLayout.module.css";

import { LayoutSlotsProvider } from "./LayoutSlotsProvider";
import { useLayoutSlots } from "./useLayoutSlots";


function AppLayoutInner() {
  const { left } = useLayoutSlots();

  return (
    <Box className={classes.root}>
      {/* LEFT SIDEBAR */}
      <Box className={classes.left} p="md">
        {/* HEADER: Brand */}
        <Box
          component={Link}
          to="/"
          style={{ textDecoration: "none", color: "inherit" }}
        >
          <Group gap="sm" wrap="nowrap" className={classes.brand}>
            <Box className={classes.brandIcon}>
              <IconRobot size={24} color="white" />
            </Box>
            <Box>
              <Text fw={600} size="md" lh={1.1}>
                RBAC MCP Agent
              </Text>
              <Text size="xs" c="dimmed">
                Permission-aware LLM tool orchestration
              </Text>
            </Box>
          </Group>
        </Box>

        {/* CONTENT (dynamic layout slot) */}
        {left && <Box className={classes.dynamicContent}>{left}</Box>}
      </Box>

      {/* RIGHT CONTENT */}
      <Box className={classes.right}>
        {/* FLOATING NAV PANEL */}
        <Box className={classes.rightHeader} p="sm">
          <Paper radius="md" p="xs" withBorder bg="white">
            <Navbar />
          </Paper>
        </Box>
        {/* MAIN CONTENT */}
        <Box px="sm" pb="sm" className={classes.rightContent}>
          <Outlet />
        </Box>
      </Box>
    </Box>
  );
}

export default function AppLayout() {
  return (
    <LayoutSlotsProvider>
      <AppLayoutInner />
    </LayoutSlotsProvider>
  );
}
