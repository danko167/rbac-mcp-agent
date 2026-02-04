import { Outlet, useLocation, Link } from "react-router";
import { Box, Group, Text } from "@mantine/core";
import { IconRobot } from "@tabler/icons-react";
import { useAuth } from "../auth/useAuth";
import AgentNav from "../components/Navbar";
import UserBadge from "../components/UserBadge";
import classes from "../assets/styles/AppLayout.module.css";

import { LayoutSlotsProvider } from "./LayoutSlotsProvider";
import { useLayoutSlots } from "./useLayoutSlots";


function AppLayoutInner() {
  const { logout } = useAuth();
  const location = useLocation();
  const { left } = useLayoutSlots();

  const isTraces =
    location.pathname === "/traces" || location.pathname === "/admin/traces";

  return (
    <Box className={classes.root}>
      <Box className={classes.left} p="md">
        <Group gap="md" wrap="nowrap">
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
        </Group>

        <AgentNav
          onLogout={logout}
          {...(isTraces ? { backTo: "/", backLabel: "Back" } : {})}
        />
        <UserBadge />
        {left}
      </Box>

      <Box className={classes.right} p="sm">
        <Outlet />
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
