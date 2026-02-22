import { useState } from "react";
import { Paper, Tabs, Stack } from "@mantine/core";
import AdminTracesPage from "../components/admin/AdminTracesPage";
import { AdminAccessContent } from "../components/admin/AdminAccessPage";
import { fullHeightFlexStyle, fullHeightStackStyle } from "../layout/pageStyles";

export default function AdminPage() {
  const [activeTab, setActiveTab] = useState<string | null>("traces");

  return (
    <Stack gap="xs" style={fullHeightStackStyle}>
      <Paper withBorder radius="md" p="sm" style={fullHeightFlexStyle}>
        <Tabs value={activeTab} onChange={setActiveTab} style={fullHeightFlexStyle}>
          <Tabs.List>
            <Tabs.Tab value="traces">Traces</Tabs.Tab>
            <Tabs.Tab value="access">Access Control</Tabs.Tab>
          </Tabs.List>

          <Tabs.Panel value="traces" pt="md" style={{ flex: 1, minHeight: 0 }}>
            <AdminTracesPage />
          </Tabs.Panel>

          <Tabs.Panel value="access" pt="md" style={{ flex: 1, minHeight: 0 }}>
            <AdminAccessContent />
          </Tabs.Panel>
        </Tabs>
      </Paper>
    </Stack>
  );
}
